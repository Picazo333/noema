"""End-to-end canaries for the R1 execution-governance rework."""

from __future__ import annotations

from pathlib import Path

import pytest

from noema.cli import main
from noema.eg.plan import build_execution_envelope
from noema.eg.recovery import resume_check
from noema.eg.scan import scan_harvest
from noema.eg.trace import create_trace
from noema.loader import dump_yaml, load_yaml
from noema.schemas import validation_errors


ROOT = Path(__file__).resolve().parents[2]
WORK_ORDER_REF = "repo://tests/eg/work-order.yaml"


def work_order() -> dict:
    return {
        "work_order_id": "wo-r1-e2e",
        "project_id": "noema",
        "objective": "read a known protocol artifact",
        "scope": {"allowed": ["src/noema"], "excluded": []},
        "context_mode": "patch",
        "allowed_writes": [],
        "forbidden_effects": [],
        "expected_artifacts": [],
        "quality_claims": ["contract-conformance"],
        "inputs": [],
    }


def envelope(**kwargs) -> dict:
    return build_execution_envelope(ROOT, work_order(), work_order_ref=WORK_ORDER_REF, **kwargs)


def trace_for(envelope: dict, actual: dict | None = None) -> dict:
    trace = create_trace(envelope, actual or {})
    assert not validation_errors("execution-trace", trace, ROOT)
    return trace


def complete_state(envelope: dict, **overrides) -> dict:
    state = {
        "project_id": envelope["project_id"],
        "role_id": "builder",
        "executor_id": None,
        "branch": "r1",
        "workspace": "noema-r1",
        "sha": "r1-baseline",
        "frontier_ref": {"scheme": "git", "locator": "frontier-r1"},
        "closed_claims": ["contract-conformance"],
        "closed_evidence_refs": [{"scheme": "repo", "locator": "validation/evidence.md"}],
        "active_blockers": [],
        "outstanding_human_gates": [],
        "prohibited_scope": [],
        "next_action": "verify artifact",
        "next_action_kind": "VERIFY",
    }
    state.update(overrides)
    return state


def test_e2e_01_cli_valid_work_order_direct_to_trace(tmp_path):
    work_order_path = tmp_path / "work-order.yaml"
    envelope_path = tmp_path / "envelope.yaml"
    actual_path = tmp_path / "actual.yaml"
    trace_path = tmp_path / "trace.yaml"
    work_order_path.write_text(dump_yaml(work_order()), encoding="utf-8")
    actual_path.write_text(dump_yaml({"metrics": {"provider_tokens": {"status": "UNAVAILABLE", "value": None}}}), encoding="utf-8")

    assert main(["eg", "plan", str(work_order_path), "--root", str(ROOT), "--out", str(envelope_path)]) == 0
    planned = load_yaml(envelope_path)
    assert planned["disposition"] == "DIRECT_EXECUTION"
    assert main(["eg", "record", str(envelope_path), str(actual_path), "--out", str(trace_path)]) == 0
    assert not validation_errors("execution-trace", load_yaml(trace_path), ROOT)


def test_e2e_02_routed_tool_and_model_to_trace():
    order = work_order()
    order["capability_requirements"] = [{"id": "resolver-required"}]
    planned = build_execution_envelope(
        ROOT,
        order,
        work_order_ref=WORK_ORDER_REF,
        task_metadata={
            "tool_requirements": {"capabilities": ["read"]},
            "model_requirements": {"modalities": ["text"]},
        },
        candidate_snapshot={
            "tools": [{"id": "allowed", "capabilities": ["read"], "source_relation": "DIRECT"}],
            "models": [{"id": "text-model", "modalities": ["text"]}],
        },
    )
    assert planned["disposition"] == "ROUTED"
    assert planned["model"]["selected_model"] == "text-model"
    trace_for(planned, {"tool_events": [{"candidate": "allowed", "action": "CALL", "result": "SUCCESS", "reason_codes": [], "evidence_refs": []}]})


@pytest.mark.parametrize(
    "field",
    ["work_order_id", "project_id", "objective", "scope", "context_mode", "allowed_writes", "forbidden_effects", "expected_artifacts", "quality_claims"],
)
def test_e2e_03_cli_rejects_each_invalid_work_order_before_planning(tmp_path, field):
    invalid = work_order()
    invalid.pop(field)
    path = tmp_path / f"missing-{field}.yaml"
    path.write_text(dump_yaml(invalid), encoding="utf-8")
    assert main(["eg", "plan", str(path), "--root", str(ROOT)]) == 2


def test_e2e_04_runtime_blocked_required_resource_is_terminal():
    planned = envelope(
        runtime_pressure={"posture_hint": "BLOCKED", "blocked_resources": ["github"]},
        task_metadata={"required_resources": ["github"]},
    )
    assert planned["disposition"] == "BLOCKED"
    assert "REQUIRED_RESOURCE_BLOCKED" in planned["reason_codes"]
    optional = envelope(
        runtime_pressure={"posture_hint": "BLOCKED", "blocked_resources": ["github"]},
        candidate_snapshot={"tools": [{"id": "github", "interfaces": ["github"], "required": False}]},
    )
    assert optional["disposition"] == "DIRECT_EXECUTION"


def test_e2e_05_resolver_blocked_is_terminal():
    order = work_order()
    order["capability_requirements"] = [{"id": "external-resolution"}]
    planned = build_execution_envelope(
        ROOT, order, work_order_ref=WORK_ORDER_REF,
        resolver_receipts=[{"resolver": "project:resolver", "status": "BLOCKED"}],
    )
    assert planned["disposition"] == "BLOCKED"
    assert "RESOLVER_BLOCKED" in planned["reason_codes"]


def test_e2e_06_missing_verified_executor_is_rc0_blocked():
    planned = envelope(task_metadata={"executor_requirements": {"capabilities": ["repository-work"]}})
    assert planned["disposition"] == "BLOCKED"
    assert planned["executor"]["status"] == "BLOCKED_NO_VERIFIED_EXECUTOR"


def test_e2e_07_denied_authoritative_tool_leaves_allowed_fallback():
    planned = envelope(
        task_metadata={"tool_requirements": {"capabilities": ["read"]}},
        candidate_snapshot={"tools": [
            {"id": "denied", "allowed": False, "capabilities": ["read"], "source_relation": "AUTHORITATIVE"},
            {"id": "fallback", "capabilities": ["read"], "source_relation": "BROAD"},
        ]},
    )
    assert planned["disposition"] == "ROUTED"
    assert [item["decision"] for item in planned["tool_decisions"]] == ["HARD_DENY", "CALL"]


def test_e2e_08_parallel_overlap_rejects_envelope():
    with pytest.raises(ValueError, match="overlap"):
        envelope(task_metadata={
            "parallel_isolated": True,
            "write_scopes": ["src", "src/noema"],
            "serialized_publication": True,
        })


def test_e2e_09_context_promotion_and_read_set_suppression_reach_trace():
    planned = envelope(task_metadata={"context_hints": {
        "cold_refs": ["repo://history.md"],
        "promotions": [{"ref": "repo://history.md", "reason_code": "RECOVERY_REQUIRED"}],
    }})
    assert planned["context"]["tier_transitions"]
    trace = trace_for(planned, {"context_reads": [
        {"ref": {"scheme": "repo", "locator": "history.md"}, "freshness": "sha-r1"},
        {"ref": {"scheme": "repo", "locator": "history.md"}, "freshness": "sha-r1"},
    ]})
    assert trace["actual"]["context_events"][-1]["result"] == "DUPLICATE_READ_SUPPRESSED"


def test_e2e_10_resume_success():
    planned = envelope(
        baseline_sha="r1-baseline",
        task_metadata={"role_id": "builder", "branch": "r1", "workspace": "noema-r1", "frontier_ref": {"scheme": "git", "locator": "frontier-r1"}},
    )
    report = resume_check(planned, {"work_order_ref": WORK_ORDER_REF, "status": "partial"}, complete_state(planned))
    assert report["status"] == "PASS"


@pytest.mark.parametrize("override", [
    {"sha": "stale"},
    {"role_id": "reviewer"},
    {"project_id": "foreign"},
    {"branch": "wrong-branch"},
    {"outstanding_human_gates": ["approval"], "next_action_kind": "EXECUTE"},
])
def test_e2e_11_resume_wrong_state_rejects(override):
    planned = envelope(
        baseline_sha="r1-baseline",
        task_metadata={"role_id": "builder", "branch": "r1", "workspace": "noema-r1", "frontier_ref": {"scheme": "git", "locator": "frontier-r1"}},
    )
    assert resume_check(planned, {"work_order_ref": WORK_ORDER_REF, "status": "partial"}, complete_state(planned, **override))["status"] == "FAIL"


@pytest.mark.parametrize("actual", [
    {"authorization": "cleartext"},
    {"tool_events": [{"candidate": "tool", "action": "CALL", "result": "SUCCESS", "reason_codes": [], "evidence_refs": [], "headers": {"Authorization": "cleartext"}}]},
    {"artifact_refs": [{"scheme": "repo", "locator": "safe", "access_token": "cleartext"}]},
    {"role_bindings": [{"role_id": "runner", "provenance_refs": [{"scheme": "repo", "locator": "safe", "x-api-key": "cleartext"}]}]},
])
def test_e2e_12_secret_bearing_trace_is_rejected(actual):
    with pytest.raises(ValueError):
        create_trace(envelope(), actual)


def test_e2e_13_metrics_unavailable_is_explicit_not_omitted():
    trace = trace_for(envelope(), {"metrics": {"provider_tokens": {"status": "UNAVAILABLE", "value": None}}})
    assert set(trace["metrics"]) == {
        "context_units", "tool_calls", "suppressed_calls", "retries", "rework",
        "human_interventions", "wall_time_ms", "provider_tokens", "monetary_cost",
    }
    assert trace["metrics"]["provider_tokens"] == {"status": "UNAVAILABLE", "value": None}


def test_e2e_14_harvest_remains_read_only():
    harvest = load_yaml(ROOT / "harvest" / "harvest-20260921-reference-authority-layering.yaml")
    manifest = load_yaml(ROOT / "noema.project.yaml")
    assert scan_harvest(harvest, [manifest], ROOT)["read_only"] is True
