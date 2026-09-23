"""Public R4 regressions for the adversarial R3 counterexamples."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from noema.cli import main
from noema.eg.economics import economics_vector
from noema.eg.plan import build_execution_envelope
from noema.eg.provenance import LoadedWorkOrder
from noema.eg.recovery import resume_check
from noema.eg.semantics import canonical_digest, contract_issues
from noema.eg.trace import create_trace
from noema.loader import dump_yaml, load_yaml


ROOT = Path(__file__).resolve().parents[2]


def order(**changes):
    value = {
        "work_order_id": "wo-r4", "project_id": "noema", "objective": "Verify R4",
        "scope": {"allowed": ["src/noema"], "excluded": ["secrets"]},
        "context_mode": "patch", "inputs": [], "capability_requirements": [],
        "allowed_writes": [], "forbidden_effects": [], "expected_artifacts": [],
        "quality_claims": [], "human_gates": [],
    }
    value.update(changes)
    return value


def public_validate(tmp_path, envelope):
    path = tmp_path / "envelope.yaml"
    path.write_text(dump_yaml(envelope), encoding="utf-8")
    return main(["eg", "validate", str(path), "--root", str(ROOT)])


def qualified(ident="reader"):
    return {"id": ident, "capabilities": ["read"], "allowed": True,
            "available": True, "availability": "AVAILABLE", "qualification": "VERIFIED"}


def test_v1_direct_public_validation_and_legacy_label(tmp_path, capsys):
    env = build_execution_envelope(ROOT, order())
    assert public_validate(tmp_path, env) == 0
    assert "LEGACY_V1_UNVERIFIED" in capsys.readouterr().out
    legacy = {key: value for key, value in env.items()
              if key not in {"contract_version", "effective_needs", "input_bindings"}}
    legacy["policy_version"] = "eg-policy-v0"
    assert public_validate(tmp_path, legacy) == 0
    assert "LEGACY_VALID" in capsys.readouterr().out


def test_control_bypass_and_replay_tampering_fail_publicly(tmp_path):
    env = build_execution_envelope(ROOT, order())
    forged = deepcopy(env)
    forged["decision"]["control"] = "DENY"
    forged["disposition"] = "ROUTED"
    forged["tool_decisions"] = [{"candidate": "x", "decision": "CALL", "reason_codes": [],
                                 "source_relation": "DIRECT", "availability": "AVAILABLE",
                                 "qualification": "VERIFIED"}]
    assert public_validate(tmp_path, forged) == 1
    forged = deepcopy(env)
    forged["disposition"] = "ROUTED"
    assert public_validate(tmp_path, forged) == 1


def test_required_interface_never_goes_direct_and_needs_witness():
    metadata = {"tool_requirements": {"interfaces": ["github-api"]}}
    missing = build_execution_envelope(ROOT, order(), task_metadata=metadata,
                                       runtime_pressure={"posture_hint": "NORMAL"})
    assert missing["disposition"] == "DEFER"
    assert missing["effective_needs"]["required_interfaces"] == ["github-api"]
    verified = build_execution_envelope(ROOT, order(), task_metadata=metadata,
        candidate_snapshot={"interfaces": [qualified("github-api")],
                            "tools": [qualified("github-reader")]},
        runtime_pressure={"posture_hint": "NORMAL"})
    assert verified["disposition"] == "ROUTED"


def test_partial_resolver_required_capability_defers():
    env = build_execution_envelope(ROOT, order(capability_requirements=[{"id": "cap-a"}]),
        resolver_receipts=[{"resolver": "resolver", "status": "PARTIAL",
            "resolution_ref": {"scheme": "repo", "locator": "resolution.yaml"},
            "unresolved_capabilities": ["cap-a"]}])
    assert env["disposition"] == "DEFER"


def test_public_plan_defers_unverified_interface_and_partial_resolver(tmp_path):
    order_path = tmp_path / "order.yaml"
    metadata_path = tmp_path / "metadata.yaml"
    receipt_path = tmp_path / "receipt.yaml"
    envelope_path = tmp_path / "envelope.yaml"
    order_path.write_text(dump_yaml(order()), encoding="utf-8")
    metadata_path.write_text(dump_yaml({"tool_requirements": {"interfaces": ["github-api"]}}), encoding="utf-8")
    assert main(["eg", "plan", str(order_path), "--root", str(ROOT),
                 "--task-metadata", str(metadata_path), "--out", str(envelope_path)]) == 0
    assert load_yaml(envelope_path)["disposition"] == "DEFER"
    order_path.write_text(dump_yaml(order(capability_requirements=[{"id": "cap-a"}])), encoding="utf-8")
    receipt_path.write_text(dump_yaml({"resolver": "resolver", "status": "PARTIAL",
        "resolution_ref": {"scheme": "repo", "locator": "resolution.yaml"},
        "unresolved_capabilities": ["cap-a"]}), encoding="utf-8")
    # Revision 2 rejects a nominal PARTIAL receipt without an explicit
    # satisfied set; it cannot be treated as a usable partial result.
    assert main(["eg", "plan", str(order_path), "--root", str(ROOT),
                 "--resolver-receipt", str(receipt_path), "--out", str(envelope_path)]) != 0


def test_caller_forged_loaded_work_order_is_rejected(tmp_path):
    value = order()
    path = tmp_path / "order.yaml"
    path.write_text(dump_yaml(value), encoding="utf-8")
    forged = LoadedWorkOrder(value, {"scheme": "file", "locator": str(path),
                                     "integrity": "sha256:forged"}, "sha256:forged")
    with pytest.raises(ValueError, match="source does not match"):
        build_execution_envelope(ROOT, value, loaded_work_order=forged)
    env = build_execution_envelope(ROOT, value)
    env["input_bindings"]["work_order"]["digest"] = canonical_digest({"other": True})
    assert contract_issues("execution-envelope", env, ROOT)


def test_file_source_drift_and_missing_source_never_pass(tmp_path, capsys):
    value = order()
    path = tmp_path / "order.yaml"
    path.write_text(dump_yaml(value), encoding="utf-8")
    from noema.eg.provenance import load_work_order

    env = build_execution_envelope(ROOT, value, loaded_work_order=load_work_order(path))
    assert public_validate(tmp_path, env) == 0
    path.write_text(dump_yaml(order(objective="changed")), encoding="utf-8")
    assert public_validate(tmp_path, env) == 1
    path.unlink()
    assert public_validate(tmp_path, env) == 1
    assert "UNVERIFIED" in capsys.readouterr().out


def test_duplicate_parallel_actor_rejected_publicly(tmp_path):
    env = build_execution_envelope(ROOT, order())
    env["topology"] = {"mode": "PARALLEL_ISOLATED", "max_parallelism": 2,
        "write_scopes": ["src/a", "src/b"], "role_bindings": [
            {"role_id": "same", "scope": ["src/a"]},
            {"role_id": "same", "scope": ["src/b"]}]}
    assert public_validate(tmp_path, env) == 1


def test_resume_cannot_silently_drop_human_gate():
    env = build_execution_envelope(ROOT, order(human_gates=["approval"]))
    state = {"project_id": "noema", "role_id": "builder", "branch": "topic",
        "workspace": "work", "sha": "baseline", "frontier_ref": None,
        "closed_claims": [], "closed_evidence_refs": [], "active_blockers": [],
        "outstanding_human_gates": [], "prohibited_scope": ["secrets"],
        "effective_allowed_writes": [], "next_action": "execute", "next_action_kind": "EXECUTE"}
    report = resume_check(env, {"work_order_ref": env["work_order_ref"], "status": "partial"}, state)
    assert report["status"] == "FAIL"
    assert "HUMAN_GATE_DROPPED_WITHOUT_EVIDENCE" in report["reason_codes"]


def test_public_resume_gate_requires_handoff_bound_approval(tmp_path):
    env = build_execution_envelope(ROOT, order(human_gates=["approval"]))
    state = {"project_id": "noema", "role_id": "builder", "branch": "topic",
        "workspace": "work", "sha": "baseline", "frontier_ref": None,
        "closed_claims": [], "closed_evidence_refs": [], "active_blockers": [],
        "outstanding_human_gates": [], "prohibited_scope": ["secrets"],
        "effective_allowed_writes": [], "next_action": "execute", "next_action_kind": "EXECUTE"}
    handoff = {"work_order_ref": env["work_order_ref"], "status": "partial", "evidence": []}
    envelope_path, handoff_path, state_path = (tmp_path / name for name in
        ("envelope.yaml", "handoff.yaml", "state.yaml"))
    envelope_path.write_text(dump_yaml(env), encoding="utf-8")
    handoff_path.write_text(dump_yaml(handoff), encoding="utf-8")
    state_path.write_text(dump_yaml(state), encoding="utf-8")
    assert main(["eg", "resume-check", str(envelope_path), str(handoff_path),
                 "--state", str(state_path)]) == 1
    approval = {"gate_id": "approval", "work_order_id": "wo-r4",
                "decision": "APPROVED", "approved_by": "human-reviewer"}
    approval_path = tmp_path / "approval.yaml"
    approval_path.write_text(dump_yaml(approval), encoding="utf-8")
    ref = {"scheme": "file", "locator": str(approval_path),
           "integrity": canonical_digest(approval)}
    state["gate_clearances"] = [{"gate_id": "approval", "evidence_ref": ref}]
    handoff["evidence"] = [ref]
    handoff_path.write_text(dump_yaml(handoff), encoding="utf-8")
    state_path.write_text(dump_yaml(state), encoding="utf-8")
    # Historical revision 1 remains readable but cannot certify R5 resume.
    assert main(["eg", "resume-check", str(envelope_path), str(handoff_path),
                 "--state", str(state_path)]) == 1
    assert resume_check(env, handoff, state)["status"] == "PASS"


def test_unqualified_tool_cannot_call_and_secret_ref_cannot_record():
    env = build_execution_envelope(ROOT, order(),
        task_metadata={"tool_requirements": {"capabilities": ["read"]}},
        candidate_snapshot={"tools": [{"id": "unqualified", "capabilities": ["read"]}]})
    assert env["disposition"] == "DEFER"
    assert all(item["decision"] != "CALL" for item in env["tool_decisions"])
    with pytest.raises(ValueError, match="credential-like"):
        create_trace(env, {"tool_events": [{"candidate": "reader", "action": "CALL",
            "result": "SUCCESS", "reason_codes": [], "evidence_refs": [
                {"scheme": "https", "locator": "example.invalid/evidence?access_token=CLEARTEXT"}]}]})


def test_public_record_and_trace_validate_reject_secret_locator(tmp_path):
    env = build_execution_envelope(ROOT, order())
    actual = {"tool_events": [{"candidate": "reader", "action": "CALL",
        "result": "SUCCESS", "reason_codes": [], "evidence_refs": [
            {"scheme": "https", "locator": "example.invalid/evidence?access_token=CLEARTEXT"}]}]}
    envelope_path, actual_path = tmp_path / "envelope.yaml", tmp_path / "actual.yaml"
    envelope_path.write_text(dump_yaml(env), encoding="utf-8")
    actual_path.write_text(dump_yaml(actual), encoding="utf-8")
    assert main(["eg", "record", str(envelope_path), str(actual_path)]) == 2
    trace = create_trace(env, {})
    trace["actual"]["artifact_refs"] = [
        {"scheme": "https", "locator": "example.invalid/evidence?access_token=CLEARTEXT"}]
    trace_path = tmp_path / "trace.yaml"
    trace_path.write_text(dump_yaml(trace), encoding="utf-8")
    assert main(["eg", "validate", str(trace_path), "--root", str(ROOT)]) == 1


def test_public_trace_validate_rejects_false_metric_and_read_suppression(tmp_path):
    env = build_execution_envelope(ROOT, order())
    trace = create_trace(env, {"context_reads": [
        {"ref": {"scheme": "repo", "locator": "a.md"}}]})
    trace_path = tmp_path / "trace.yaml"
    trace["metrics"]["tool_calls"] = {"status": "UNAVAILABLE", "value": 0}
    trace_path.write_text(dump_yaml(trace), encoding="utf-8")
    assert main(["eg", "validate", str(trace_path), "--root", str(ROOT)]) == 1
    trace["metrics"]["tool_calls"] = {"status": "UNAVAILABLE", "value": None}
    trace["actual"]["context_events"][0]["result"] = "DUPLICATE_READ_SUPPRESSED"
    trace_path.write_text(dump_yaml(trace), encoding="utf-8")
    assert main(["eg", "validate", str(trace_path), "--root", str(ROOT)]) == 1


def test_unverified_freshness_does_not_suppress_and_unavailable_stays_null():
    env = build_execution_envelope(ROOT, order())
    trace = create_trace(env, {"context_reads": [
        {"ref": {"scheme": "repo", "locator": "a.md"}, "freshness": "etag-a"},
        {"ref": {"scheme": "repo", "locator": "a.md"}, "freshness": "etag-a"}]})
    assert all(event["result"] == "READ_REQUIRED" for event in trace["actual"]["context_events"])
    vector = economics_vector(trace)
    assert vector["tool_calls"] == {"status": "UNAVAILABLE", "value": None}
    assert vector["retries"] is None
