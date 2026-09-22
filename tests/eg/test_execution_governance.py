from pathlib import Path

from noema.eg.context_plan import ReadSet
from noema.eg.context_plan import build_context_plan
from noema.eg.classification import classify_deliberation
from noema.eg.decision import decide_disposition
from noema.eg.executor import filter_model_candidates, select_existing_executor
from noema.eg.interop import validate_resolver_receipt
from noema.eg.plan import build_execution_envelope
from noema.eg.permissions import evaluate_control
from noema.eg.recovery import resume_check
from noema.eg.runtime import classify_runtime_posture, derive_resource_policy
from noema.eg.scan import scan_harvest
from noema.eg.topology import derive_topology
from noema.eg.tooling import decide_tools
from noema.eg.trace import create_trace
from noema.eg.enums import ActionEffect, AuthorityScope, DataSensitivity
from noema.loader import load_yaml
from noema.schemas import validation_errors


ROOT = Path(__file__).resolve().parents[2]


def work_order():
    return {
        "work_order_id": "wo-eg-read", "project_id": "noema", "objective": "read known file",
        "scope": {"allowed": ["src/noema"], "excluded": []}, "context_mode": "patch",
        "allowed_writes": [], "forbidden_effects": [], "expected_artifacts": [],
        "quality_claims": ["contract-conformance"], "inputs": [],
    }


def test_direct_envelope_is_valid_and_skips_tool_routing():
    envelope = build_execution_envelope(
        ROOT, work_order(), work_order_ref="repo://tests/eg/work-order.yaml",
        candidate_snapshot={"tools": [{"id": "crawler", "capabilities": ["read"]}]},
    )
    assert envelope["disposition"] == "DIRECT_EXECUTION"
    assert envelope["tool_decisions"] == []
    assert not validation_errors("execution-envelope", envelope, ROOT)


def test_tool_selector_suppresses_broader_duplicate_source():
    decisions = decide_tools([
        {"id": "repo", "capabilities": ["read"], "source_relation": "DIRECT"},
        {"id": "crawler", "capabilities": ["read"], "source_relation": "BROAD"},
    ], {"capabilities": ["read"]})
    assert decisions[0]["decision"] == "CALL"
    assert decisions[1]["decision"] == "SOFT_SUPPRESS"


def test_read_set_and_runtime_pressure_are_conservative():
    read_set = ReadSet()
    ref = {"scheme": "repo", "locator": "PROTOCOL.md", "integrity": "sha-protocol"}
    assert read_set.record(ref)["read"]
    assert read_set.record(ref)["reason_code"] == "DUPLICATE_READ_SUPPRESSED"
    posture = classify_runtime_posture({"posture_hint": "CONSERVE"})
    assert derive_resource_policy(posture)["optional_external_calls"] == "CONSERVE"


def test_resume_rejects_stale_sha():
    envelope = build_execution_envelope(
        ROOT,
        work_order(),
        work_order_ref="repo://tests/eg/work-order.yaml",
        baseline_sha="old",
        task_metadata={"role_id": "builder", "branch": "topic", "workspace": "work", "frontier_ref": {"scheme": "git", "locator": "node"}},
    )
    state = {
        "project_id": "noema", "role_id": "builder", "branch": "topic", "workspace": "work",
        "sha": "new", "frontier_ref": {"scheme": "git", "locator": "node"},
        "closed_claims": ["contract-conformance"], "closed_evidence_refs": [{"scheme": "repo", "locator": "evidence.md"}],
        "active_blockers": [], "outstanding_human_gates": [], "prohibited_scope": [], "effective_allowed_writes": [],
        "next_action": "continue", "next_action_kind": "EXECUTE",
    }
    report = resume_check(envelope, {"work_order_ref": envelope["work_order_ref"], "status": "partial"}, state)
    assert report["status"] == "FAIL"
    assert "STALE_SHA" in report["reason_codes"]


def test_trace_marks_missing_telemetry_unavailable():
    envelope = build_execution_envelope(ROOT, work_order(), work_order_ref="repo://tests/eg/work-order.yaml")
    trace = create_trace(envelope, {"metrics": {"context_units": 12}})
    assert trace["metrics"]["context_units"]["status"] == "MEASURED"
    assert trace["metrics"]["provider_tokens"] == {"status": "UNAVAILABLE", "value": None}
    assert not validation_errors("execution-trace", trace, ROOT)


def test_security_controls_are_orthogonal_and_conservative():
    secret = evaluate_control(ActionEffect.READ, DataSensitivity.SECRET, AuthorityScope.LOCAL_PROJECT, work_order())
    canonical = evaluate_control(ActionEffect.CANONICAL_MUTATION, DataSensitivity.INTERNAL, AuthorityScope.LOCAL_PROJECT, work_order())
    foreign = evaluate_control(ActionEffect.WRITE_REVERSIBLE, DataSensitivity.INTERNAL, AuthorityScope.FOREIGN, work_order())
    assert secret["control"] == "DENY"
    assert canonical["control"] == "REQUIRE_HUMAN"
    assert foreign["control"] == "ROUTE_ELSEWHERE"


def test_receipt_topology_model_and_executor_boundaries():
    receipt = validate_resolver_receipt({"resolver": "project:skill-foundry", "status": "RESOLVED", "resolution_ref": {"scheme": "repo", "locator": "fixture.yaml"}})
    assert receipt["resolver"] == "project:skill-foundry"
    assert derive_topology({}, {"independent_review_required": True})["mode"] == "AUDITED_SINGLE"
    try:
        derive_topology({"parallel_isolated": True, "write_scopes": ["a", "a"]}, {})
    except ValueError:
        pass
    else:
        raise AssertionError("shared canonical writes must be rejected")
    assert filter_model_candidates([{"id": "m", "modalities": ["text"]}], {"modalities": ["text"]})["selected_model"] == "m"
    assert select_existing_executor(ROOT, {"capabilities": ["repository-work"]})["status"] == "BLOCKED_NO_VERIFIED_EXECUTOR"


def test_scan_is_read_only_and_trace_rejects_secrets():
    harvest = load_yaml(ROOT / "harvest" / "harvest-20260921-reference-authority-layering.yaml")
    manifest = load_yaml(ROOT / "noema.project.yaml")
    report = scan_harvest(harvest, [manifest], ROOT)
    assert report["read_only"] is True
    envelope = build_execution_envelope(ROOT, work_order(), work_order_ref="repo://tests/eg/work-order.yaml")
    try:
        create_trace(envelope, {"token": "not-allowed"})
    except ValueError:
        pass
    else:
        raise AssertionError("secret-like trace fields must be rejected")


def test_throttled_and_blocked_runtime_do_not_expand_work():
    for hint in ("THROTTLED", "BLOCKED"):
        posture = classify_runtime_posture({"posture_hint": hint})
        policy = derive_resource_policy(posture)
        assert policy["parallelism_ceiling"] == 1
        assert policy["optional_external_calls"] == "DEFER"


def test_remaining_direct_context_and_control_canaries():
    manifest = load_yaml(ROOT / "noema.project.yaml")
    scoped = evaluate_control(
        ActionEffect.WRITE_REVERSIBLE, DataSensitivity.INTERNAL, AuthorityScope.LOCAL_PROJECT,
        {**work_order(), "allowed_writes": ["src/noema"]}, {"repo_write_reversible": True},
    )
    assert scoped["control"] == "ALLOW_SCOPED"  # C02
    assert classify_deliberation({**work_order(), "objective": "architecture analysis"}).value == "DEEP"  # C03
    assert decide_disposition("ALLOW", already_complete=True)["disposition"] == "NO_ACTION"  # C05
    assert build_execution_envelope(ROOT, work_order(), work_order_ref="repo://tests/eg/work-order.yaml")["resolver_receipts"] == []  # C10
    patch = build_context_plan(ROOT, manifest, work_order())
    assert all(item["load_tier"] == "HOT" for item in patch["refs"])  # C17
    recover = build_context_plan(ROOT, manifest, {**work_order(), "context_mode": "recover"}, recovery_refs=[{"scheme": "repo", "locator": "handoff.yaml"}])
    assert any(item["ref"]["locator"] == "handoff.yaml" and item["load_tier"] == "HOT" for item in recover["refs"])  # C18
