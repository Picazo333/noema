"""R2 seam regressions: public contracts must agree with EG internals."""

from __future__ import annotations

from pathlib import Path

import pytest

from noema.cli import main
from noema.eg.context_plan import ReadSet
from noema.eg.plan import build_execution_envelope
from noema.eg.recovery import resume_check
from noema.eg.topology import derive_topology
from noema.eg.trace import create_trace
from noema.loader import dump_yaml, load_yaml
from noema.schemas import validation_errors


ROOT = Path(__file__).resolve().parents[2]
WORK_ORDER_REF = "repo://tests/eg/work-order.yaml"


def work_order(**overrides) -> dict:
    value = {
        "work_order_id": "wo-r2",
        "project_id": "noema",
        "objective": "verify execution governance contract seams",
        "scope": {"allowed": ["src/noema"], "excluded": ["secrets"]},
        "context_mode": "patch",
        "inputs": [],
        "capability_requirements": [],
        "allowed_writes": [],
        "forbidden_effects": [],
        "expected_artifacts": [],
        "quality_claims": ["contract-conformance"],
        "human_gates": [],
    }
    value.update(overrides)
    return value


def envelope(**kwargs) -> dict:
    return build_execution_envelope(ROOT, work_order(), work_order_ref=WORK_ORDER_REF, **kwargs)


def resume_state(env: dict, **overrides) -> dict:
    state = {
        "project_id": env["project_id"],
        "role_id": "builder",
        "executor_id": env["recovery"]["expected_executor"],
        "branch": "r2",
        "workspace": "noema-r2",
        "sha": "r2-sha",
        "frontier_ref": {"scheme": "git", "locator": "r2-frontier"},
        "closed_claims": ["contract-conformance"],
        "closed_evidence_refs": [{"scheme": "repo", "locator": "validation/r2-evidence.md"}],
        "active_blockers": [],
        "outstanding_human_gates": [],
        "prohibited_scope": ["secrets"],
        "effective_allowed_writes": [],
        "next_action": "verify",
        "next_action_kind": "VERIFY",
    }
    state.update(overrides)
    return state


def test_r2_01_resolver_participation_is_explicit_and_terminal(tmp_path):
    unexpected = envelope(resolver_receipts=[{"resolver": "project:resolver", "status": "BLOCKED"}])
    assert unexpected["disposition"] == "DIRECT_EXECUTION"
    assert "RESOLVER_RECEIPT_NOT_REQUIRED" in unexpected["reason_codes"]

    required = work_order(capability_requirements=[{"id": "external-resolution"}])
    blocked = build_execution_envelope(
        ROOT, required, work_order_ref=WORK_ORDER_REF,
        resolver_receipts=[{"resolver": "project:resolver", "status": "BLOCKED"}],
    )
    assert blocked["disposition"] == "BLOCKED"
    resolved = build_execution_envelope(
        ROOT, required, work_order_ref=WORK_ORDER_REF,
        resolver_receipts=[{"resolver": "project:resolver", "status": "RESOLVED"}],
    )
    assert resolved["disposition"] == "ROUTED"
    with pytest.raises(ValueError):
        build_execution_envelope(
            ROOT, required, work_order_ref=WORK_ORDER_REF,
            resolver_receipts=[{"resolver": "project:resolver", "status": "BROKEN"}],
        )

    work_order_path = tmp_path / "resolver-work-order.yaml"
    receipt_path = tmp_path / "resolver-receipt.yaml"
    out = tmp_path / "resolver-envelope.yaml"
    work_order_path.write_text(dump_yaml(required), encoding="utf-8")
    receipt_path.write_text(dump_yaml({"resolver": "project:resolver", "status": "BLOCKED"}), encoding="utf-8")
    assert main(["eg", "plan", str(work_order_path), "--root", str(ROOT), "--resolver-receipt", str(receipt_path), "--out", str(out)]) == 0
    assert load_yaml(out)["disposition"] == "BLOCKED"


@pytest.mark.parametrize(
    ("pressure", "metadata", "expected"),
    [
        ({"posture_hint": "NORMAL"}, {}, "DIRECT_EXECUTION"),
        ({"posture_hint": "CONSERVE"}, {}, "DIRECT_EXECUTION"),
        ({"posture_hint": "THROTTLED", "blocked_resources": ["github"]}, {"required_resources": ["github"]}, "DEFER"),
        ({"posture_hint": "BLOCKED", "blocked_resources": ["github"]}, {"required_resources": ["github"]}, "BLOCKED"),
        ({"posture_hint": "BLOCKED", "blocked_interfaces": ["github-api"]}, {"executor_requirements": {"interfaces": ["github-api"]}}, "BLOCKED"),
        ({"posture_hint": "BLOCKED", "block_all_external": True}, {"requires_external": True}, "BLOCKED"),
    ],
)
def test_r2_02_runtime_pressure_public_contract_to_envelope(tmp_path, pressure, metadata, expected):
    work_order_path = tmp_path / "work-order.yaml"
    pressure_path = tmp_path / "runtime-pressure.yaml"
    metadata_path = tmp_path / "metadata.yaml"
    out = tmp_path / "envelope.yaml"
    work_order_path.write_text(dump_yaml(work_order()), encoding="utf-8")
    pressure_path.write_text(dump_yaml({
        "observed_at": "2026-09-21T00:00:00Z",
        "host_profile": "eg.repo-agent.v0",
        **pressure,
    }), encoding="utf-8")
    metadata_path.write_text(dump_yaml(metadata), encoding="utf-8")
    assert main(["eg", "plan", str(work_order_path), "--root", str(ROOT), "--runtime-pressure", str(pressure_path), "--task-metadata", str(metadata_path), "--out", str(out)]) == 0
    planned = load_yaml(out)
    assert planned["disposition"] == expected
    assert planned["runtime_resource_policy"]["posture"] == pressure["posture_hint"]


def test_r2_02_runtime_pressure_malformed_input_is_rejected_by_cli(tmp_path):
    work_order_path = tmp_path / "work-order.yaml"
    pressure_path = tmp_path / "bad-runtime-pressure.yaml"
    work_order_path.write_text(dump_yaml(work_order()), encoding="utf-8")
    pressure_path.write_text(dump_yaml({
        "observed_at": "2026-09-21T00:00:00Z",
        "host_profile": "eg.repo-agent.v0",
        "posture_hint": "BLOCKED",
        "blocked_resources": "github",
    }), encoding="utf-8")
    assert main(["eg", "plan", str(work_order_path), "--root", str(ROOT), "--runtime-pressure", str(pressure_path)]) == 2


def test_r2_03_readset_requires_evidence_and_trace_records_identity():
    reads = ReadSet()
    first = {"scheme": "repo", "locator": "doc.md", "integrity": "sha-a"}
    changed = {"scheme": "repo", "locator": "doc.md", "integrity": "sha-b"}
    unknown = {"scheme": "repo", "locator": "unknown.md"}
    assert reads.record(first)["reason_code"] == "READ_REQUIRED"
    assert reads.record(first)["reason_code"] == "DUPLICATE_READ_SUPPRESSED"
    assert reads.record(changed)["reason_code"] == "READ_REQUIRED"
    assert reads.record(unknown)["reason_code"] == "READ_REQUIRED"
    assert reads.record(unknown)["reason_code"] == "READ_REQUIRED"
    assert reads.record({"scheme": "repo", "locator": "other.md", "integrity": "sha-a"})["reason_code"] == "READ_REQUIRED"

    trace = create_trace(envelope(), {"context_reads": [
        {"ref": first}, {"ref": first}, {"ref": changed},
    ]})
    assert [event["identity_kind"] for event in trace["actual"]["context_events"]] == ["INTEGRITY"] * 3
    assert trace["actual"]["context_events"][1]["result"] == "DUPLICATE_READ_SUPPRESSED"


def test_r2_04_resume_preserves_constraints_and_uses_effective_executor(monkeypatch):
    def selected_executor(*_args, **_kwargs):
        return {"status": "ROUTED", "executor": "effective-executor", "eligible": ["effective-executor"]}

    monkeypatch.setattr("noema.eg.plan.select_existing_executor", selected_executor)
    planned = envelope(
        baseline_sha="r2-sha",
        task_metadata={
            "role_id": "builder", "branch": "r2", "workspace": "noema-r2",
            "frontier_ref": {"scheme": "git", "locator": "r2-frontier"},
            "expected_executor": "metadata-executor",
            "executor_requirements": {"capabilities": ["repository-work"]},
        },
    )
    assert planned["executor"]["selected_executor"] == "effective-executor"
    assert planned["recovery"]["expected_executor"] == "effective-executor"
    handoff = {"work_order_ref": WORK_ORDER_REF, "status": "partial"}
    assert resume_check(planned, handoff, resume_state(planned))["status"] == "PASS"
    assert resume_check(planned, handoff, resume_state(planned, prohibited_scope=[]))["status"] == "FAIL"
    assert resume_check(planned, handoff, resume_state(planned, prohibited_scope=["secrets", "private"]))["status"] == "PASS"
    assert resume_check(planned, handoff, resume_state(planned, executor_id="metadata-executor"))["status"] == "FAIL"
    assert resume_check(planned, handoff, resume_state(planned, effective_allowed_writes=["src"]))["status"] == "FAIL"


def test_r2_05_topology_runtime_and_schema_both_require_isolation_evidence():
    bindings = [
        {"role_id": "worker-a", "scope": ["src/a"]},
        {"role_id": "worker-b", "scope": ["src/b"]},
    ]
    topology = derive_topology({
        "parallel_isolated": True, "write_scopes": ["src/a", "src/b"],
        "role_bindings": bindings, "serialized_publication": True,
    })
    assert topology["mode"] == "PARALLEL_ISOLATED"
    for scopes in (["src/A", "src/a"], ["C:/one", "src/b"], ["src", "src/noema"]):
        with pytest.raises(ValueError):
            derive_topology({
                "parallel_isolated": True, "write_scopes": scopes,
                "role_bindings": bindings, "serialized_publication": True,
            })
    invalid = envelope()
    invalid["topology"] = {"mode": "PARALLEL_ISOLATED", "max_parallelism": 2, "role_bindings": []}
    assert validation_errors("execution-envelope", invalid, ROOT)


def test_r2_06_work_order_identity_is_preserved_through_cli(tmp_path):
    local = envelope()
    assert local["work_order_id"] == "wo-r2"
    assert local["project_id"] == "noema"
    foreign = work_order(work_order_id="wo-foreign", project_id="foreign-project")
    work_order_path = tmp_path / "foreign-work-order.yaml"
    out = tmp_path / "foreign-envelope.yaml"
    work_order_path.write_text(dump_yaml(foreign), encoding="utf-8")
    assert main(["eg", "plan", str(work_order_path), "--root", str(ROOT), "--out", str(out)]) == 0
    planned = load_yaml(out)
    assert planned["work_order_id"] == "wo-foreign"
    assert planned["project_id"] == "foreign-project"
    assert planned["disposition"] == "ROUTE_ELSEWHERE"


def test_r2_07_public_routed_tool_fallback_and_trace(tmp_path):
    work_order_path = tmp_path / "work-order.yaml"
    metadata_path = tmp_path / "metadata.yaml"
    candidates_path = tmp_path / "candidates.yaml"
    envelope_path = tmp_path / "envelope.yaml"
    actual_path = tmp_path / "actual.yaml"
    trace_path = tmp_path / "trace.yaml"
    work_order_path.write_text(dump_yaml(work_order()), encoding="utf-8")
    metadata_path.write_text(dump_yaml({
        "tool_requirements": {"capabilities": ["read"]},
        "model_requirements": {"modalities": ["text"]},
    }), encoding="utf-8")
    candidates_path.write_text(dump_yaml({
        "tools": [
            {"id": "denied-authoritative", "allowed": False, "capabilities": ["read"], "source_relation": "AUTHORITATIVE"},
            {"id": "allowed-fallback", "capabilities": ["read"], "source_relation": "BROAD"},
        ],
        "models": [{"id": "text-model", "modalities": ["text"]}],
    }), encoding="utf-8")
    actual_path.write_text(dump_yaml({"tool_events": [{
        "candidate": "allowed-fallback", "action": "CALL", "result": "SUCCESS",
        "reason_codes": [], "evidence_refs": [],
    }]}), encoding="utf-8")
    assert main(["eg", "plan", str(work_order_path), "--root", str(ROOT), "--task-metadata", str(metadata_path), "--candidate-snapshot", str(candidates_path), "--out", str(envelope_path)]) == 0
    planned = load_yaml(envelope_path)
    assert planned["disposition"] == "ROUTED"
    assert [item["decision"] for item in planned["tool_decisions"]] == ["HARD_DENY", "CALL"]
    assert main(["eg", "record", str(envelope_path), str(actual_path), "--out", str(trace_path)]) == 0
    assert not validation_errors("execution-trace", load_yaml(trace_path), ROOT)


def test_r2_07_public_no_verified_executor_and_topology_rejection(tmp_path):
    work_order_path = tmp_path / "work-order.yaml"
    metadata_path = tmp_path / "executor-metadata.yaml"
    envelope_path = tmp_path / "executor-envelope.yaml"
    work_order_path.write_text(dump_yaml(work_order()), encoding="utf-8")
    metadata_path.write_text(dump_yaml({"executor_requirements": {"capabilities": ["repository-work"]}}), encoding="utf-8")
    assert main(["eg", "plan", str(work_order_path), "--root", str(ROOT), "--task-metadata", str(metadata_path), "--out", str(envelope_path)]) == 0
    assert load_yaml(envelope_path)["executor"]["status"] == "BLOCKED_NO_VERIFIED_EXECUTOR"

    metadata_path.write_text(dump_yaml({
        "parallel_isolated": True,
        "write_scopes": ["src", "src/noema"],
        "role_bindings": [{"role_id": "a", "scope": ["src"]}, {"role_id": "b", "scope": ["src/noema"]}],
        "serialized_publication": True,
    }), encoding="utf-8")
    assert main(["eg", "plan", str(work_order_path), "--root", str(ROOT), "--task-metadata", str(metadata_path)]) == 2


def test_r2_07_public_context_trace_resume_secret_and_harvest(tmp_path):
    work_order_path = tmp_path / "work-order.yaml"
    metadata_path = tmp_path / "context-metadata.yaml"
    envelope_path = tmp_path / "envelope.yaml"
    actual_path = tmp_path / "actual.yaml"
    trace_path = tmp_path / "trace.yaml"
    handoff_path = tmp_path / "handoff.yaml"
    state_path = tmp_path / "state.yaml"
    harvest_out = tmp_path / "harvest-report.yaml"
    work_order_path.write_text(dump_yaml(work_order()), encoding="utf-8")
    metadata_path.write_text(dump_yaml({"context_hints": {
        "cold_refs": ["repo://history.md"],
        "promotions": [{"ref": "repo://history.md", "reason_code": "RECOVERY_REQUIRED"}],
    }}), encoding="utf-8")
    assert main(["eg", "plan", str(work_order_path), "--root", str(ROOT), "--task-metadata", str(metadata_path), "--out", str(envelope_path)]) == 0
    planned = load_yaml(envelope_path)
    assert planned["context"]["tier_transitions"]
    actual_path.write_text(dump_yaml({"context_reads": [
        {"ref": {"scheme": "repo", "locator": "history.md", "integrity": "sha-history"}},
        {"ref": {"scheme": "repo", "locator": "history.md", "integrity": "sha-history"}},
    ]}), encoding="utf-8")
    assert main(["eg", "record", str(envelope_path), str(actual_path), "--out", str(trace_path)]) == 0
    assert load_yaml(trace_path)["actual"]["context_events"][1]["result"] == "DUPLICATE_READ_SUPPRESSED"

    handoff_path.write_text(dump_yaml({"work_order_ref": {"scheme": "file", "locator": str(work_order_path)}, "status": "partial"}), encoding="utf-8")
    state = resume_state(
        planned,
        branch=None,
        workspace=None,
        sha=planned["recovery"]["expected_sha"],
        frontier_ref=None,
        role_id=None,
    )
    state_path.write_text(dump_yaml(state), encoding="utf-8")
    assert main(["eg", "resume-check", str(envelope_path), str(handoff_path), "--state", str(state_path)]) == 0
    state["prohibited_scope"] = []
    state_path.write_text(dump_yaml(state), encoding="utf-8")
    assert main(["eg", "resume-check", str(envelope_path), str(handoff_path), "--state", str(state_path)]) == 1

    actual_path.write_text(dump_yaml({"authorization": "cleartext"}), encoding="utf-8")
    assert main(["eg", "record", str(envelope_path), str(actual_path)]) == 2
    assert main(["eg", "scan-harvest", str(ROOT / "harvest" / "harvest-20260921-reference-authority-layering.yaml"), str(ROOT / "noema.project.yaml"), "--out", str(harvest_out)]) == 0
    assert load_yaml(harvest_out)["read_only"] is True


def test_r2_08_missing_metrics_stay_unavailable_through_public_record_cli(tmp_path):
    envelope_path = tmp_path / "envelope.yaml"
    actual_path = tmp_path / "actual.yaml"
    trace_path = tmp_path / "trace.yaml"
    envelope_path.write_text(dump_yaml(envelope()), encoding="utf-8")
    actual_path.write_text(dump_yaml({}), encoding="utf-8")
    assert main(["eg", "record", str(envelope_path), str(actual_path), "--out", str(trace_path)]) == 0
    trace = load_yaml(trace_path)
    assert trace["retries"] is None and trace["rework_cycles"] is None
    for name in ("tool_calls", "suppressed_calls", "retries", "rework"):
        assert trace["metrics"][name] == {"status": "UNAVAILABLE", "value": None}
    assert not validation_errors("execution-trace", trace, ROOT)
