from pathlib import Path

import pytest

from noema.eg.plan import build_execution_envelope
from noema.eg.recovery import resume_check
from noema.eg.topology import derive_topology
from noema.eg.trace import create_trace
from noema.eg.tooling import decide_tools
from noema.schemas import validation_errors


ROOT = Path(__file__).resolve().parents[2]


def work_order():
    return {
        "work_order_id": "wo-r1", "project_id": "noema", "objective": "read known file",
        "scope": {"allowed": ["src/noema"], "excluded": ["secrets"]}, "context_mode": "patch",
        "inputs": [], "capability_requirements": [], "allowed_writes": [], "forbidden_effects": [],
        "expected_artifacts": [], "quality_claims": ["contract-conformance"], "human_gates": [],
    }


def envelope(**kwargs):
    return build_execution_envelope(ROOT, work_order(), work_order_ref="repo://tests/eg/work-order.yaml", **kwargs)


def resume_state(env, **overrides):
    state = {
        "project_id": "noema", "role_id": "builder", "executor_id": None,
        "branch": "topic", "workspace": "work", "sha": "baseline",
        "frontier_ref": {"scheme": "git", "locator": "frontier"},
        "closed_claims": ["contract-conformance"],
        "closed_evidence_refs": [{"scheme": "repo", "locator": "evidence.md"}],
        "active_blockers": [], "outstanding_human_gates": [], "prohibited_scope": ["secrets"], "effective_allowed_writes": [],
        "next_action": "continue", "next_action_kind": "EXECUTE",
    }
    state.update(overrides)
    return state


@pytest.mark.parametrize(
    "field",
    ["work_order_id", "project_id", "objective", "scope", "context_mode", "allowed_writes", "forbidden_effects", "expected_artifacts", "quality_claims"],
)
def test_invalid_work_order_never_enters_planning(field):
    invalid = work_order()
    invalid.pop(field)
    with pytest.raises(ValueError, match="Invalid WorkOrder"):
        build_execution_envelope(ROOT, invalid, work_order_ref="repo://bad.yaml")


def test_routed_pipeline_uses_model_router_and_tool_fallback():
    metadata = {"tool_requirements": {"capabilities": ["read"]}, "model_requirements": {"modalities": ["text"]}}
    candidate_snapshot = {
        "tools": [
            {"id": "denied-direct", "allowed": False, "capabilities": ["read"], "source_relation": "AUTHORITATIVE"},
            {"id": "allowed-fallback", "capabilities": ["read"], "source_relation": "BROAD"},
        ],
        "models": [{"id": "runtime-model", "available": True, "modalities": ["text"]}],
    }
    routed_work_order = work_order()
    routed_work_order["capability_requirements"] = [{"id": "external-resolution"}]
    env = build_execution_envelope(ROOT, routed_work_order, work_order_ref="repo://tests/eg/work-order.yaml", task_metadata=metadata, candidate_snapshot=candidate_snapshot, resolver_receipts=[{"resolver": "project:resolver", "status": "RESOLVED"}])
    assert env["disposition"] == "ROUTED"
    assert [item["decision"] for item in env["tool_decisions"]] == ["HARD_DENY", "CALL"]
    assert env["model"]["selected_model"] == "runtime-model"
    assert not validation_errors("execution-envelope", env, ROOT)


def test_blocked_runtime_and_resolver_are_terminal_only_when_required():
    pure = envelope(runtime_pressure={"posture_hint": "BLOCKED", "blocked_resources": ["github"]})
    assert pure["disposition"] == "DIRECT_EXECUTION"
    blocked = envelope(
        runtime_pressure={"posture_hint": "BLOCKED", "blocked_resources": ["github"]},
        task_metadata={"required_resources": ["github"]},
    )
    assert blocked["disposition"] == "BLOCKED"
    resolver_work_order = work_order()
    resolver_work_order["capability_requirements"] = [{"id": "skill"}]
    resolver = build_execution_envelope(ROOT, resolver_work_order, work_order_ref="repo://tests/eg/work-order.yaml", resolver_receipts=[{"resolver": "project:skill-foundry", "status": "BLOCKED"}])
    assert resolver["disposition"] == "BLOCKED"


def test_no_verified_executor_blocks_integrated_pipeline():
    routed = work_order()
    routed["capability_requirements"] = [{"id": "route"}]
    env = build_execution_envelope(ROOT, routed, work_order_ref="repo://tests/eg/work-order.yaml", task_metadata={"executor_requirements": {"capabilities": ["repository-work"]}}, resolver_receipts=[{"resolver": "project:resolver", "status": "RESOLVED"}])
    assert env["disposition"] == "BLOCKED"
    assert env["executor"]["status"] == "BLOCKED_NO_VERIFIED_EXECUTOR"


@pytest.mark.parametrize(
    "key",
    ["authorization", "Authorization", "access_token", "refresh_token", "api_key", "x-api-key", "access_key", "client_secret", "password", "cookie"],
)
def test_trace_rejects_secret_variants_everywhere(key):
    env = envelope()
    event = {"candidate": "tool", "action": "CALL", "result": "SUCCESS", "reason_codes": [], "evidence_refs": [], key: "cleartext"}
    with pytest.raises(ValueError):
        create_trace(env, {"tool_events": [event]})
    with pytest.raises(ValueError):
        create_trace(env, {"context_reads": [{"ref": {"scheme": "repo", "locator": "a"}, "freshness": {key: "cleartext"}}]})


def test_trace_is_structured_and_explicit_about_unavailable_metrics():
    env = envelope()
    trace = create_trace(env, {
        "context_reads": [
            {"ref": {"scheme": "repo", "locator": "PROTOCOL.md"}, "freshness": "sha-a"},
            {"ref": {"scheme": "repo", "locator": "PROTOCOL.md"}, "freshness": "sha-a"},
        ],
        "tool_events": [{"candidate": "direct", "action": "CALL", "result": "SUCCESS", "reason_codes": [], "evidence_refs": []}],
        "metrics": {"context_units": 42},
    })
    assert trace["actual"]["context_events"][1]["result"] == "DUPLICATE_READ_SUPPRESSED"
    assert trace["metrics"]["provider_tokens"] == {"status": "UNAVAILABLE", "value": None}
    assert trace["metrics"]["tool_calls"] == {"status": "MEASURED", "value": 1}
    assert not validation_errors("execution-trace", trace, ROOT)


def test_estimated_metric_requires_methodology_evidence():
    env = envelope()
    with pytest.raises(ValueError, match="methodology_ref"):
        create_trace(env, {"metrics": {"monetary_cost": {"status": "ESTIMATED_LABELED", "value": 2}}})
    trace = create_trace(env, {"metrics": {"monetary_cost": {
        "status": "ESTIMATED_LABELED", "value": 2,
        "methodology_ref": {"scheme": "repo", "locator": "validation/cost-method.md"},
    }}})
    assert trace["metrics"]["monetary_cost"]["methodology_ref"]["locator"] == "validation/cost-method.md"


@pytest.mark.parametrize(
    "metadata",
    [
        {"parallel_isolated": True, "write_scopes": [], "serialized_publication": True},
        {"parallel_isolated": True, "write_scopes": ["src", "src/noema"], "serialized_publication": True},
        {"parallel_isolated": True, "write_scopes": ["src/a", "src\\a"], "serialized_publication": True},
    ],
)
def test_parallel_isolation_rejects_unprovable_scopes(metadata):
    with pytest.raises(ValueError):
        derive_topology(metadata, {})


def test_parallel_isolation_accepts_disjoint_scopes():
    topology = derive_topology({"parallel_isolated": True, "write_scopes": ["src/a", "src/b"], "serialized_publication": True, "role_bindings": [{"role_id": "worker-a", "scope": ["src/a"]}, {"role_id": "worker-b", "scope": ["src/b"]}]}, {})
    assert topology["mode"] == "PARALLEL_ISOLATED"


def test_context_promotion_and_resume_contract():
    env = envelope(task_metadata={
        "role_id": "builder", "branch": "topic", "workspace": "work", "frontier_ref": {"scheme": "git", "locator": "frontier"},
        "context_hints": {
            "cold_refs": ["repo://history.md"], "never_preload_refs": ["repo://raw-chat.md"],
            "promotions": [{"ref": "repo://history.md", "reason_code": "RECOVERY_REQUIRED"}],
        },
    }, baseline_sha="baseline")
    history = next(item for item in env["context"]["refs"] if item["ref"]["locator"] == "history.md")
    raw_chat = next(item for item in env["context"]["refs"] if item["ref"]["locator"] == "raw-chat.md")
    assert history["load_tier"] == "HOT"
    assert raw_chat["load_tier"] == "NEVER_PRELOAD"
    handoff = {"work_order_ref": "repo://tests/eg/work-order.yaml", "status": "partial"}
    assert resume_check(env, handoff, resume_state(env))["status"] == "PASS"
    assert resume_check(env, handoff, resume_state(env, branch="wrong"))["status"] == "FAIL"
    assert resume_check(env, handoff, {"project_id": "noema"})["status"] == "INCOMPLETE"


def test_denied_candidate_cannot_suppress_fallback():
    decisions = decide_tools([
        {"id": "denied", "allowed": False, "capabilities": ["read"], "source_relation": "AUTHORITATIVE"},
        {"id": "fallback", "capabilities": ["read"], "source_relation": "BROAD"},
    ], {"capabilities": ["read"]})
    assert [item["decision"] for item in decisions] == ["HARD_DENY", "CALL"]
