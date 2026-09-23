"""Public-entrypoint regressions for the seven adversarial R4 P1 families."""

from __future__ import annotations

from copy import deepcopy
import json
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

from noema.loader import dump_yaml, load_yaml
from noema.eg.bindings import (gate_fingerprint, material_digest, read_subject,
                               observation_projection, observation_subject)
from noema.eg.compare import expected_observations
from noema.eg.evidence import candidate_subject


ROOT = Path(__file__).resolve().parents[2]


def invoke(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "noema", "eg", *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def write(tmp_path: Path, name: str, value: object) -> Path:
    path = tmp_path / name
    path.write_text(dump_yaml(value), encoding="utf-8")
    return path


def trusted_source(tmp_path: Path, name: str, predicate: str, subject: str,
                   decision: str = "VERIFIED") -> dict:
    assertion = write(tmp_path, name + ".yaml", {
        "predicate": predicate, "subject": subject, "scope": "project:noema",
        "authority": "external-fixture", "decision": decision,
    })
    return {"ref": {"scheme": "file", "locator": str(assertion)},
            "digest": "sha256:" + sha256(assertion.read_bytes()).hexdigest(),
            "predicate": predicate, "subject": subject, "scope": "project:noema",
            "authority": "external-fixture", "valid_until": "2099-01-01T00:00:00Z"}


def order(**changes: object) -> dict:
    data = {
        "work_order_id": "wo-r5", "project_id": "noema", "objective": "Read project",
        "scope": {"allowed": ["src/noema"], "excluded": ["secrets"]},
        "context_mode": "patch", "inputs": [], "capability_requirements": [],
        "allowed_writes": [], "forbidden_effects": [], "expected_artifacts": [],
        "quality_claims": [], "human_gates": [],
    }
    data.update(changes)
    return data


def planned(tmp_path: Path, work_order: dict, *, metadata: dict | None = None,
            candidates: dict | None = None, receipts: list[dict] | None = None) -> tuple[Path, dict]:
    args: list[object] = ["plan", write(tmp_path, "work-order.yaml", work_order),
                          "--root", ROOT, "--out", tmp_path / "envelope.yaml"]
    if metadata is not None:
        args += ["--task-metadata", write(tmp_path, "metadata.yaml", metadata)]
    if candidates is not None:
        args += ["--candidate-snapshot", write(tmp_path, "candidates.yaml", candidates)]
    for index, receipt in enumerate(receipts or []):
        args += ["--resolver-receipt", write(tmp_path, f"receipt-{index}.yaml", receipt)]
    result = invoke(*args)
    assert result.returncode == 0, result.stderr
    path = tmp_path / "envelope.yaml"
    return path, load_yaml(path)


def test_explicit_human_gate_never_implicitly_authorizes_execution(tmp_path: Path) -> None:
    _, envelope = planned(tmp_path, order(human_gates=["approval"]))
    assert envelope["disposition"] not in {"DIRECT_EXECUTION", "ROUTED"}


def test_terminal_envelope_cannot_resume_into_execute(tmp_path: Path) -> None:
    envelope_path, envelope = planned(tmp_path, order(objective="Publish final artifact"))
    assert envelope["disposition"] == "DEFER"
    ref = envelope["work_order_ref"]
    handoff = {"handoff_id": "handoff-r5-terminal",
               "work_order_ref": ref["scheme"] + "://" + ref["locator"],
               "status": "partial", "summary": "Pending", "changes": [],
               "artifacts": [], "evidence": [], "remaining": [],
               "next_action": "publish", "intentionally_unchanged": []}
    state = {"project_id": "noema", "role_id": "builder", "branch": "topic",
             "workspace": "work", "sha": envelope["recovery"]["expected_sha"],
             "frontier_ref": None, "closed_claims": [], "closed_evidence_refs": [],
             "active_blockers": [], "outstanding_human_gates": [],
             "prohibited_scope": ["secrets"], "effective_allowed_writes": [],
             "next_action": "publish", "next_action_kind": "EXECUTE"}
    result = invoke("resume-check", envelope_path, write(tmp_path, "handoff.yaml", handoff),
                    "--state", write(tmp_path, "state.yaml", state), "--json")
    assert result.returncode != 0
    assert json.loads(result.stdout)["status"] != "PASS"


def test_trace_must_bind_exact_envelope_and_report_unplanned_tool(tmp_path: Path) -> None:
    envelope_path, _ = planned(tmp_path, order())
    actual = {"envelope_ref": {"scheme": "memory", "locator": "exec-wrong"},
              "model": "rogue-model", "executor": "rogue-executor",
              "tool_events": [{"candidate": "rogue-tool", "action": "CALL",
                               "result": "SUCCESS", "reason_codes": [], "evidence_refs": []}]}
    trace_path = tmp_path / "trace.yaml"
    recorded = invoke("record", envelope_path, write(tmp_path, "actual.yaml", actual),
                      "--out", trace_path)
    if recorded.returncode == 0:
        compared = invoke("compare", envelope_path, trace_path, "--json")
        assert compared.returncode != 0 or json.loads(compared.stdout)["deviations"]
    else:
        assert recorded.returncode != 0


def test_credential_variants_never_persist_in_trace(tmp_path: Path) -> None:
    envelope_path, _ = planned(tmp_path, order())
    marker = "R5_MARKER_DO_NOT_PERSIST"
    actual = {"tool_events": [{"candidate": "reader", "action": "CALL",
              "result": "SUCCESS", "reason_codes": ["Authorization: Bearer " + marker],
              "evidence_refs": [{"scheme": "https",
                                 "locator": "example.invalid/e?refresh_token=" + marker}]}]}
    trace_path = tmp_path / "trace.yaml"
    result = invoke("record", envelope_path, write(tmp_path, "actual.yaml", actual),
                    "--out", trace_path)
    assert result.returncode != 0
    assert not trace_path.exists()
    assert marker not in result.stdout + result.stderr


def test_replay_covers_context_and_baseline(tmp_path: Path) -> None:
    envelope_path, envelope = planned(tmp_path, order())
    envelope["context"]["refs"] = []
    envelope["context"]["noema_context_units"] = 0
    write(tmp_path, "tampered.yaml", envelope)
    result = invoke("validate", tmp_path / "tampered.yaml", "--root", ROOT)
    assert result.returncode != 0
    envelope = load_yaml(envelope_path)
    envelope["baseline_ref"] = {"scheme": "git", "locator": "b" * 40}
    envelope["recovery"]["expected_sha"] = "b" * 40
    write(tmp_path, "tampered.yaml", envelope)
    result = invoke("validate", tmp_path / "tampered.yaml", "--root", ROOT)
    assert result.returncode != 0


def test_nominal_resolver_and_model_are_not_proof(tmp_path: Path) -> None:
    receipt = {"resolver": "resolver", "status": "RESOLVED",
               "resolution_ref": {"scheme": "repo", "locator": "missing-r5-proof.yaml"}}
    _, envelope = planned(tmp_path, order(capability_requirements=[{"id": "cap-a"}]),
                          receipts=[receipt])
    assert envelope["disposition"] not in {"DIRECT_EXECUTION", "ROUTED"}
    metadata = {"model_requirements": {"modalities": ["text"]}}
    candidates = {"models": [{"id": "unverified-model", "modalities": ["text"]}]}
    _, envelope = planned(tmp_path, order(), metadata=metadata, candidates=candidates)
    assert envelope["disposition"] not in {"DIRECT_EXECUTION", "ROUTED"}


def test_parallel_isolation_requires_authority_and_workspace_separation(tmp_path: Path) -> None:
    metadata = {"parallel_isolated": True, "serialized_publication": True,
                "write_scopes": ["src/a", "src/b"], "role_bindings": [
                    {"role_id": "a", "scope": ["src/a"], "workspace": "shared", "branch": "shared"},
                    {"role_id": "b", "scope": ["src/b"], "workspace": "shared", "branch": "shared"}]}
    _, envelope = planned(tmp_path, order(), metadata=metadata,
                          candidates={"tools": [{"id": "reader"}]})
    assert envelope["disposition"] not in {"DIRECT_EXECUTION", "ROUTED"}


def test_claimed_hash_never_suppresses_a_read(tmp_path: Path) -> None:
    envelope_path, _ = planned(tmp_path, order())
    ref = {"scheme": "repo", "locator": "missing-r5-read.txt",
           "integrity": "sha256:" + "a" * 64}
    actual = {"context_reads": [{"ref": ref}, {"ref": ref}]}
    trace_path = tmp_path / "trace.yaml"
    recorded = invoke("record", envelope_path, write(tmp_path, "actual.yaml", actual),
                      "--out", trace_path)
    if recorded.returncode == 0:
        trace = load_yaml(trace_path)
        assert all(event["result"] != "DUPLICATE_READ_SUPPRESSED"
                   for event in trace["actual"]["context_events"])


def test_direct_ready_requires_host_context(tmp_path: Path) -> None:
    trust = write(tmp_path, "trust.yaml", {"sources": []})
    work = write(tmp_path, "direct-order.yaml", order())
    envelope_path = tmp_path / "direct-envelope.yaml"
    result = invoke("plan", work, "--root", ROOT, "--trust-context", trust,
                    "--require-ready", "--out", envelope_path)
    assert result.returncode == 0, result.stderr
    checked = invoke("validate", envelope_path, "--root", ROOT,
                     "--trust-context", trust, "--require-ready", "--json")
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert json.loads(checked.stdout)["readiness"] == "EXECUTION_READY"
    untrusted = invoke("validate", envelope_path, "--root", ROOT,
                       "--require-ready", "--json")
    assert untrusted.returncode != 0
    report = json.loads(untrusted.stdout)
    assert report["structural_valid"] is True
    assert report["semantic_valid"] is True
    assert report["readiness"] == "NOT_EXECUTION_READY"


def test_coordinated_material_tamper_fails_independent_replay(tmp_path: Path) -> None:
    trust = write(tmp_path, "trust.yaml", {"sources": []})
    envelope_path = tmp_path / "envelope.yaml"
    result = invoke("plan", write(tmp_path, "order.yaml", order()), "--root", ROOT,
                    "--trust-context", trust, "--out", envelope_path)
    assert result.returncode == 0, result.stderr
    envelope = load_yaml(envelope_path)
    envelope["decision"]["authority_scope"] = "FOREIGN"
    envelope["material_binding"]["digest"] = material_digest(envelope)
    tampered = write(tmp_path, "tampered.yaml", envelope)
    checked = invoke("validate", tampered, "--root", ROOT, "--trust-context", trust,
                     "--require-ready", "--json")
    assert checked.returncode != 0
    assert "MATERIAL_REPLAY_MISMATCH" in checked.stdout


def test_derived_control_tamper_cannot_escape_human_gate(tmp_path: Path) -> None:
    envelope_path, envelope = planned(tmp_path, order(objective="Publish final artifact"))
    assert envelope["decision"]["control"] == "REQUIRE_HUMAN"
    envelope["decision"]["control"] = "ALLOW"
    envelope["disposition"] = "DIRECT_EXECUTION"
    envelope["reason_codes"] = ["LOW_EFFECT_ALLOWED"]
    tampered = write(tmp_path, "forged-control.yaml", envelope)
    checked = invoke("validate", tampered, "--root", ROOT, "--json")
    assert checked.returncode != 0
    assert "DERIVED_REPLAY_MISMATCH" in checked.stdout or "FAIL:" in checked.stdout


def test_routed_ready_requires_candidate_specific_external_proof(tmp_path: Path) -> None:
    candidate = {"id": "reader", "allowed": True, "available": True,
                 "availability": "AVAILABLE", "qualification": "VERIFIED",
                 "capabilities": ["read"]}
    requirements = {"capabilities": ["read"]}
    subject = candidate_subject("tool", candidate, requirements)
    sources = [trusted_source(tmp_path, "qualification", "TOOL_QUALIFICATION", subject),
               trusted_source(tmp_path, "availability", "TOOL_AVAILABILITY", subject)]
    trust = write(tmp_path, "trust.yaml", {"sources": sources})
    work = write(tmp_path, "order.yaml", order())
    metadata = write(tmp_path, "metadata.yaml", {"tool_requirements": requirements})
    candidates = write(tmp_path, "candidates.yaml", {"tools": [candidate]})
    envelope_path = tmp_path / "routed-envelope.yaml"
    result = invoke("plan", work, "--root", ROOT, "--trust-context", trust,
                    "--task-metadata", metadata, "--candidate-snapshot", candidates,
                    "--require-ready", "--out", envelope_path)
    assert result.returncode == 0, result.stderr
    envelope = load_yaml(envelope_path)
    assert envelope["disposition"] == "ROUTED"
    checked = invoke("validate", envelope_path, "--root", ROOT,
                     "--trust-context", trust, "--require-ready", "--json")
    assert checked.returncode == 0, checked.stdout + checked.stderr


def test_resume_ready_rechecks_current_envelope_and_handoff(tmp_path: Path) -> None:
    trust = write(tmp_path, "trust.yaml", {"sources": []})
    envelope_path = tmp_path / "envelope.yaml"
    result = invoke("plan", write(tmp_path, "order.yaml", order()), "--root", ROOT,
                    "--trust-context", trust, "--require-ready", "--out", envelope_path)
    assert result.returncode == 0, result.stderr
    envelope = load_yaml(envelope_path)
    ref = envelope["work_order_ref"]
    handoff = write(tmp_path, "handoff.yaml", {
        "handoff_id": "handoff-r5", "work_order_ref": ref["scheme"] + "://" + ref["locator"],
        "status": "partial", "summary": "Continuing", "changes": [], "artifacts": [],
        "evidence": [], "remaining": [], "next_action": "Continue read",
        "intentionally_unchanged": [],
    })
    state = write(tmp_path, "state.yaml", {
        "project_id": "noema", "role_id": "builder", "branch": "topic",
        "workspace": "work", "sha": envelope["recovery"]["expected_sha"],
        "frontier_ref": None, "closed_claims": [], "closed_evidence_refs": [],
        "active_blockers": [], "outstanding_human_gates": [],
        "prohibited_scope": ["secrets"], "effective_allowed_writes": [],
        "next_action": "Continue read", "next_action_kind": "EXECUTE",
    })
    resume_sources = [{
        "ref": {"scheme": "file", "locator": str(state)},
        "digest": "sha256:" + sha256(state.read_bytes()).hexdigest(),
        "predicate": "RESUME_STATE", "subject": material_digest(envelope),
        "scope": "project:noema", "authority": "host-fixture",
        "valid_until": "2099-01-01T00:00:00Z",
    }, {
        "ref": {"scheme": "file", "locator": str(handoff)},
        "digest": "sha256:" + sha256(handoff.read_bytes()).hexdigest(),
        "predicate": "HANDOFF_STATE", "subject": material_digest(envelope),
        "scope": "project:noema", "authority": "host-fixture",
        "valid_until": "2099-01-01T00:00:00Z",
    }]
    resume_trust = write(tmp_path, "resume-trust.yaml", {"sources": resume_sources})
    resumed = invoke("resume-check", envelope_path, handoff, "--state", state,
                     "--root", ROOT, "--trust-context", resume_trust, "--json")
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert json.loads(resumed.stdout)["status"] == "PASS"
    unpinned = invoke("resume-check", envelope_path, handoff, "--state", state,
                      "--root", ROOT, "--trust-context", trust, "--json")
    assert unpinned.returncode != 0
    assert json.loads(unpinned.stdout)["status"] == "INCOMPLETE"


def test_human_approval_is_bound_to_exact_material_intent(tmp_path: Path) -> None:
    envelope_path = tmp_path / "gated-envelope.yaml"
    work = write(tmp_path, "gated-order.yaml", order(human_gates=["review"]))
    host_claim = {"profile": "eg.repo-agent.v0",
                  "capabilities": {"enforce_human_gate": True}}
    host = write(tmp_path, "host.yaml", host_claim)
    planned_result = invoke("plan", work, "--root", ROOT, "--host-capabilities", host,
                            "--out", envelope_path)
    assert planned_result.returncode == 0, planned_result.stderr
    envelope = load_yaml(envelope_path)
    subject = gate_fingerprint(envelope, "review")
    host_subject = candidate_subject("host", host_claim, {
        "work_order_id": envelope["work_order_id"],
        "action_id": envelope["intent"]["action_id"],
    })
    host_source = trusted_source(tmp_path, "host-proof", "HOST_GATE_ENFORCEMENT", host_subject)
    trust = write(tmp_path, "approval-trust.yaml", {"sources": [
        host_source, trusted_source(tmp_path, "approval", "HUMAN_APPROVAL", subject, "APPROVED")
    ]})
    approved = invoke("validate", envelope_path, "--root", ROOT,
                      "--trust-context", trust, "--require-ready", "--json")
    assert approved.returncode == 0, approved.stdout + approved.stderr
    other = write(tmp_path, "wrong-trust.yaml", {"sources": [host_source,
        trusted_source(tmp_path, "wrong-approval", "HUMAN_APPROVAL", "wrong-action", "APPROVED")
    ]})
    rejected = invoke("validate", envelope_path, "--root", ROOT,
                      "--trust-context", other, "--require-ready", "--json")
    assert rejected.returncode != 0
    assert "HUMAN_APPROVAL_UNVERIFIED" in rejected.stdout


def test_resolver_requires_usable_result_satisfied_set_and_external_proof(tmp_path: Path) -> None:
    content_digest = "sha256:" + sha256((ROOT / "PROTOCOL.md").read_bytes()).hexdigest()
    receipt = {"resolver": "external-resolver", "status": "RESOLVED",
               "resolution_ref": {"scheme": "repo", "locator": "PROTOCOL.md"},
               "unresolved_capabilities": [], "satisfied_capabilities": ["cap-a"],
               "integrity": content_digest, "observed_at": None}
    subject = candidate_subject("resolver", receipt, {"capability": "cap-a"})
    trust = write(tmp_path, "resolver-trust.yaml", {"sources": [
        trusted_source(tmp_path, "resolver-proof", "RESOLVER_SATISFACTION", subject)
    ]})
    work = write(tmp_path, "order.yaml", order(capability_requirements=[{"id": "cap-a"}]))
    receipt_path = write(tmp_path, "receipt.yaml", receipt)
    envelope_path = tmp_path / "resolver-envelope.yaml"
    result = invoke("plan", work, "--root", ROOT, "--trust-context", trust,
                    "--resolver-receipt", receipt_path, "--require-ready",
                    "--out", envelope_path)
    assert result.returncode == 0, result.stderr
    envelope = load_yaml(envelope_path)
    assert envelope["disposition"] == "ROUTED"
    assert invoke("validate", envelope_path, "--root", ROOT, "--trust-context", trust,
                  "--require-ready").returncode == 0


def test_trace_exact_binding_and_observation_coverage(tmp_path: Path) -> None:
    trust = write(tmp_path, "trust.yaml", {"sources": []})
    envelope_path = tmp_path / "envelope.yaml"
    assert invoke("plan", write(tmp_path, "order.yaml", order()), "--root", ROOT,
                  "--trust-context", trust, "--require-ready",
                  "--out", envelope_path).returncode == 0
    unknown_actual = write(tmp_path, "unknown-actual.yaml", {"context_reads": []})
    unknown_trace = tmp_path / "unknown-trace.yaml"
    assert invoke("record", envelope_path, unknown_actual, "--out", unknown_trace).returncode == 0
    incomplete = invoke("compare", envelope_path, unknown_trace, "--json")
    assert incomplete.returncode != 0
    assert json.loads(incomplete.stdout)["status"] == "INCOMPLETE"
    actual = write(tmp_path, "observed-actual.yaml", {
        "outcome": "SUCCESS", "context_reads": [], "tool_events": []})
    trace_path = tmp_path / "trace.yaml"
    assert invoke("record", envelope_path, actual, "--out", trace_path).returncode == 0
    compared = invoke("compare", envelope_path, trace_path, "--json")
    assert compared.returncode == 0, compared.stdout + compared.stderr
    assert json.loads(compared.stdout)["status"] == "PASS"
    certified = invoke("validate", trace_path, "--kind", "execution-trace",
                       "--envelope", envelope_path, "--root", ROOT,
                       "--trust-context", trust, "--require-ready", "--json")
    assert certified.returncode == 0, certified.stdout + certified.stderr


def test_resume_after_exact_human_approval(tmp_path: Path) -> None:
    work = write(tmp_path, "order.yaml", order(human_gates=["review"]))
    host_claim = {"profile": "eg.repo-agent.v0",
                  "capabilities": {"enforce_human_gate": True}}
    host = write(tmp_path, "host.yaml", host_claim)
    envelope_path = tmp_path / "envelope.yaml"
    assert invoke("plan", work, "--root", ROOT, "--host-capabilities", host,
                  "--out", envelope_path).returncode == 0
    envelope = load_yaml(envelope_path)
    ref = envelope["work_order_ref"]
    handoff = write(tmp_path, "handoff.yaml", {
        "handoff_id": "handoff-approved", "work_order_ref": ref["scheme"] + "://" + ref["locator"],
        "status": "partial", "summary": "Approved", "changes": [], "artifacts": [],
        "evidence": [], "remaining": [], "next_action": "Continue",
        "intentionally_unchanged": [],
    })
    state = write(tmp_path, "state.yaml", {
        "project_id": "noema", "role_id": "builder", "branch": "topic",
        "workspace": "work", "sha": envelope["recovery"]["expected_sha"],
        "frontier_ref": None, "closed_claims": [], "closed_evidence_refs": [],
        "active_blockers": [], "outstanding_human_gates": [],
        "prohibited_scope": ["secrets"], "effective_allowed_writes": [],
        "next_action": "Continue", "next_action_kind": "EXECUTE",
    })
    material = material_digest(envelope)
    host_subject = candidate_subject("host", host_claim, {
        "work_order_id": envelope["work_order_id"],
        "action_id": envelope["intent"]["action_id"],
    })
    sources = [
        trusted_source(tmp_path, "host-proof", "HOST_GATE_ENFORCEMENT", host_subject),
        trusted_source(tmp_path, "approval", "HUMAN_APPROVAL",
                       gate_fingerprint(envelope, "review"), "APPROVED"),
    ]
    for name, path in (("RESUME_STATE", state), ("HANDOFF_STATE", handoff)):
        sources.append({"ref": {"scheme": "file", "locator": str(path)},
                        "digest": "sha256:" + sha256(path.read_bytes()).hexdigest(),
                        "predicate": name, "subject": material,
                        "scope": "project:noema", "authority": "host-fixture",
                        "valid_until": "2099-01-01T00:00:00Z"})
    trust = write(tmp_path, "trust.yaml", {"sources": sources})
    resumed = invoke("resume-check", envelope_path, handoff, "--state", state,
                     "--root", ROOT, "--trust-context", trust, "--json")
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert json.loads(resumed.stdout)["status"] == "PASS"


def test_parallel_isolation_requires_host_bound_proof(tmp_path: Path) -> None:
    work = write(tmp_path, "order.yaml", order(allowed_writes=["src/a", "src/b"]))
    host = write(tmp_path, "host.yaml", {"profile": "eg.repo-agent.v0",
                 "capabilities": {"repo_write_reversible": True}})
    metadata = write(tmp_path, "metadata.yaml", {
        "parallel_isolated": True, "serialized_publication": True,
        "write_scopes": ["src/a", "src/b"],
        "role_bindings": [
            {"role_id": "a", "scope": ["src/a"], "workspace": "a-work", "branch": "a-branch"},
            {"role_id": "b", "scope": ["src/b"], "workspace": "b-work", "branch": "b-branch"},
        ],
    })
    envelope_path = tmp_path / "parallel-envelope.yaml"
    result = invoke("plan", work, "--root", ROOT, "--host-capabilities", host,
                    "--task-metadata", metadata, "--out", envelope_path)
    assert result.returncode == 0, result.stderr
    envelope = load_yaml(envelope_path)
    assert envelope["topology"]["mode"] == "PARALLEL_ISOLATED"
    no_proof = invoke("validate", envelope_path, "--root", ROOT, "--require-ready")
    assert no_proof.returncode != 0
    trust = write(tmp_path, "isolation-trust.yaml", {"sources": [
        trusted_source(tmp_path, "isolation-proof", "HOST_ISOLATION",
                       envelope["material_binding"]["digest"])
    ]})
    proved = invoke("validate", envelope_path, "--root", ROOT,
                    "--trust-context", trust, "--require-ready", "--json")
    assert proved.returncode == 0, proved.stdout + proved.stderr


def test_historical_read_suppression_needs_event_bound_host_observation(tmp_path: Path) -> None:
    envelope_path = tmp_path / "envelope.yaml"
    assert invoke("plan", write(tmp_path, "order.yaml", order()), "--root", ROOT,
                  "--out", envelope_path).returncode == 0
    envelope = load_yaml(envelope_path)
    ref = {"scheme": "repo", "locator": "PROTOCOL.md",
           "integrity": "sha256:" + sha256((ROOT / "PROTOCOL.md").read_bytes()).hexdigest()}
    trust = write(tmp_path, "read-trust.yaml", {"sources": [
        trusted_source(tmp_path, f"read-{index}", "HISTORICAL_READ_IDENTITY",
                       read_subject(envelope, index, ref))
        for index in range(2)
    ]})
    actual = write(tmp_path, "actual.yaml", {
        "outcome": "SUCCESS", "tool_events": [],
        "context_reads": [{"ref": ref}, {"ref": ref}],
    })
    trace_path = tmp_path / "trace.yaml"
    recorded = invoke("record", envelope_path, actual, "--root", ROOT,
                      "--trust-context", trust, "--out", trace_path)
    assert recorded.returncode == 0, recorded.stderr
    trace = load_yaml(trace_path)
    assert trace["actual"]["context_events"][1]["result"] == "DUPLICATE_READ_SUPPRESSED"
    assert len(trace["read_identity_bindings"]) == 2
    untrusted = invoke("compare", envelope_path, trace_path, "--json")
    assert untrusted.returncode != 0
    assert json.loads(untrusted.stdout)["status"] == "INCOMPLETE"
    trusted = invoke("compare", envelope_path, trace_path, "--root", ROOT,
                     "--trust-context", trust, "--json")
    assert trusted.returncode == 0, trusted.stdout + trusted.stderr


def test_trace_reports_unplanned_executor_model_and_tool(tmp_path: Path) -> None:
    envelope_path = tmp_path / "envelope.yaml"
    assert invoke("plan", write(tmp_path, "order.yaml", order()), "--root", ROOT,
                  "--out", envelope_path).returncode == 0
    actual = write(tmp_path, "actual.yaml", {
        "outcome": "SUCCESS", "executor": "rogue-executor", "model": "rogue-model",
        "context_reads": [], "tool_events": [{
            "candidate": "rogue-tool", "action": "CALL", "result": "SUCCESS",
            "reason_codes": [], "evidence_refs": [],
        }],
    })
    trace_path = tmp_path / "trace.yaml"
    assert invoke("record", envelope_path, actual, "--out", trace_path).returncode == 0
    compared = invoke("compare", envelope_path, trace_path, "--json")
    assert compared.returncode != 0
    assert set(json.loads(compared.stdout)["deviations"]) >= {
        "EXECUTOR_MISMATCH", "MODEL_MISMATCH", "UNPLANNED_TOOL_CALL"
    }


def test_approval_wrong_attempt_and_stale_source_never_ready(tmp_path: Path) -> None:
    work = write(tmp_path, "order.yaml", order(human_gates=["review"]))
    host_claim = {"profile": "eg.repo-agent.v0",
                  "capabilities": {"enforce_human_gate": True}}
    host = write(tmp_path, "host.yaml", host_claim)
    envelope_path = tmp_path / "envelope.yaml"
    assert invoke("plan", work, "--root", ROOT, "--host-capabilities", host,
                  "--out", envelope_path).returncode == 0
    envelope = load_yaml(envelope_path)
    host_subject = candidate_subject("host", host_claim, {
        "work_order_id": envelope["work_order_id"],
        "action_id": envelope["intent"]["action_id"],
    })
    host_source = trusted_source(tmp_path, "host-proof", "HOST_GATE_ENFORCEMENT", host_subject)
    wrong = load_yaml(envelope_path)
    wrong["intent"]["attempt_id"] = "another-attempt"
    wrong["material_binding"]["digest"] = material_digest(wrong)
    wrong_subject = gate_fingerprint(wrong, "review")
    wrong_trust = write(tmp_path, "wrong-attempt-trust.yaml", {"sources": [
        host_source,
        trusted_source(tmp_path, "wrong-attempt-proof", "HUMAN_APPROVAL",
                       wrong_subject, "APPROVED"),
    ]})
    rejected = invoke("validate", envelope_path, "--root", ROOT,
                      "--trust-context", wrong_trust, "--require-ready", "--json")
    assert rejected.returncode != 0
    assert "HUMAN_APPROVAL_UNVERIFIED" in rejected.stdout
    stale = trusted_source(tmp_path, "stale-proof", "HUMAN_APPROVAL",
                           gate_fingerprint(envelope, "review"), "APPROVED")
    stale["valid_until"] = "2000-01-01T00:00:00Z"
    stale_trust = write(tmp_path, "stale-trust.yaml", {"sources": [host_source, stale]})
    expired = invoke("validate", envelope_path, "--root", ROOT,
                     "--trust-context", stale_trust, "--require-ready", "--json")
    assert expired.returncode != 0
    assert "HUMAN_APPROVAL_UNVERIFIED" in expired.stdout


def test_qualification_wrong_candidate_and_stale_source_defer(tmp_path: Path) -> None:
    candidate = {"id": "reader", "allowed": True, "available": True,
                 "availability": "AVAILABLE", "qualification": "VERIFIED",
                 "capabilities": ["read"]}
    requirements = {"capabilities": ["read"]}
    work = write(tmp_path, "order.yaml", order())
    metadata = write(tmp_path, "metadata.yaml", {"tool_requirements": requirements})
    candidates = write(tmp_path, "candidates.yaml", {"tools": [candidate]})
    wrong = trusted_source(tmp_path, "wrong-candidate", "TOOL_QUALIFICATION",
                           candidate_subject("tool", {**candidate, "id": "other"}, requirements))
    correct_availability = trusted_source(tmp_path, "availability", "TOOL_AVAILABILITY",
                                          candidate_subject("tool", candidate, requirements))
    wrong_trust = write(tmp_path, "wrong-trust.yaml", {"sources": [wrong, correct_availability]})
    envelope_path = tmp_path / "envelope.yaml"
    wrong_result = invoke("plan", work, "--root", ROOT, "--task-metadata", metadata,
                          "--candidate-snapshot", candidates, "--trust-context", wrong_trust,
                          "--require-ready", "--out", envelope_path)
    assert wrong_result.returncode != 0
    assert load_yaml(envelope_path)["disposition"] == "DEFER"
    stale = trusted_source(tmp_path, "stale-qualification", "TOOL_QUALIFICATION",
                           candidate_subject("tool", candidate, requirements))
    stale["valid_until"] = "2000-01-01T00:00:00Z"
    stale_trust = write(tmp_path, "stale-trust.yaml", {"sources": [stale, correct_availability]})
    stale_result = invoke("plan", work, "--root", ROOT, "--task-metadata", metadata,
                          "--candidate-snapshot", candidates, "--trust-context", stale_trust,
                          "--require-ready", "--out", envelope_path)
    assert stale_result.returncode != 0
    assert load_yaml(envelope_path)["disposition"] == "DEFER"


def test_partial_resolver_with_material_gap_stays_not_ready(tmp_path: Path) -> None:
    receipt = {"resolver": "external-resolver", "status": "PARTIAL",
               "resolution_ref": {"scheme": "repo", "locator": "PROTOCOL.md"},
               "unresolved_capabilities": ["cap-b"],
               "satisfied_capabilities": ["cap-a"],
               "integrity": "sha256:" + sha256((ROOT / "PROTOCOL.md").read_bytes()).hexdigest(),
               "observed_at": None}
    subject = candidate_subject("resolver", receipt, {"capability": "cap-a"})
    trust = write(tmp_path, "trust.yaml", {"sources": [
        trusted_source(tmp_path, "partial-proof", "RESOLVER_SATISFACTION", subject)
    ]})
    work = write(tmp_path, "order.yaml", order(capability_requirements=[
        {"id": "cap-a"}, {"id": "cap-b"}]))
    envelope_path = tmp_path / "envelope.yaml"
    planned_result = invoke("plan", work, "--root", ROOT, "--trust-context", trust,
                            "--resolver-receipt", write(tmp_path, "receipt.yaml", receipt),
                            "--require-ready", "--out", envelope_path)
    assert planned_result.returncode != 0
    assert load_yaml(envelope_path)["disposition"] == "DEFER"
    checked = invoke("validate", envelope_path, "--root", ROOT,
                     "--trust-context", trust, "--require-ready", "--json")
    assert checked.returncode != 0
    assert "RESOLVER_RESULT_UNVERIFIED" in checked.stdout


def test_parallel_shared_branch_outside_scope_and_overlap_fail(tmp_path: Path) -> None:
    work = write(tmp_path, "order.yaml", order(allowed_writes=["src/a", "src/b"]))
    host = write(tmp_path, "host.yaml", {"profile": "eg.repo-agent.v0",
                 "capabilities": {"repo_write_reversible": True}})
    base = {"parallel_isolated": True, "serialized_publication": True,
            "write_scopes": ["src/a", "src/b"], "role_bindings": [
                {"role_id": "a", "scope": ["src/a"], "workspace": "a-work", "branch": "a-branch"},
                {"role_id": "b", "scope": ["src/b"], "workspace": "b-work", "branch": "b-branch"},
            ]}
    shared = json.loads(json.dumps(base))
    shared["role_bindings"][1]["branch"] = "a-branch"
    path = tmp_path / "envelope.yaml"
    result = invoke("plan", work, "--root", ROOT, "--host-capabilities", host,
                    "--task-metadata", write(tmp_path, "shared.yaml", shared),
                    "--out", path)
    assert result.returncode == 0, result.stderr
    checked = invoke("validate", path, "--root", ROOT, "--json")
    assert "PARALLEL_WORKSPACE_UNVERIFIED" in checked.stdout
    outside = json.loads(json.dumps(base))
    outside["write_scopes"][1] = "other"
    outside["role_bindings"][1]["scope"] = ["other"]
    result = invoke("plan", work, "--root", ROOT, "--host-capabilities", host,
                    "--task-metadata", write(tmp_path, "outside.yaml", outside),
                    "--out", path)
    assert result.returncode == 0, result.stderr
    checked = invoke("validate", path, "--root", ROOT, "--json")
    assert "PARALLEL_SCOPE_OUTSIDE_AUTHORITY" in checked.stdout
    overlap = json.loads(json.dumps(base))
    overlap["write_scopes"][1] = "src/a/sub"
    overlap["role_bindings"][1]["scope"] = ["src/a/sub"]
    result = invoke("plan", work, "--root", ROOT, "--host-capabilities", host,
                    "--task-metadata", write(tmp_path, "overlap.yaml", overlap),
                    "--out", path)
    assert result.returncode != 0


def test_changed_read_content_never_uses_old_identity(tmp_path: Path) -> None:
    envelope_path = tmp_path / "envelope.yaml"
    assert invoke("plan", write(tmp_path, "order.yaml", order()), "--root", ROOT,
                  "--out", envelope_path).returncode == 0
    envelope = load_yaml(envelope_path)
    target = tmp_path / "read-target.txt"
    target.write_bytes(b"first version")
    first = {"scheme": "file", "locator": str(target),
             "integrity": "sha256:" + sha256(target.read_bytes()).hexdigest()}
    target.write_bytes(b"changed version")
    second = {"scheme": "file", "locator": str(target),
              "integrity": "sha256:" + sha256(target.read_bytes()).hexdigest()}
    assert first["integrity"] != second["integrity"]
    trust = write(tmp_path, "read-trust.yaml", {"sources": [
        trusted_source(tmp_path, "read-first", "HISTORICAL_READ_IDENTITY",
                       read_subject(envelope, 0, first)),
        trusted_source(tmp_path, "read-second", "HISTORICAL_READ_IDENTITY",
                       read_subject(envelope, 1, second)),
    ]})
    actual = write(tmp_path, "actual.yaml", {"outcome": "SUCCESS", "tool_events": [],
                                            "context_reads": [{"ref": first}, {"ref": second}]})
    trace_path = tmp_path / "trace.yaml"
    assert invoke("record", envelope_path, actual, "--root", ROOT,
                  "--trust-context", trust, "--out", trace_path).returncode == 0
    results = [item["result"] for item in load_yaml(trace_path)["actual"]["context_events"]]
    assert results == ["READ_REQUIRED", "READ_REQUIRED"]


def _t1_tool_plan(tmp_path: Path) -> tuple[Path, dict, list[dict]]:
    candidate = {"id": "reader", "allowed": True, "available": True,
                 "availability": "AVAILABLE", "qualification": "VERIFIED",
                 "capabilities": ["read"]}
    requirements = {"capabilities": ["read"]}
    subject = candidate_subject("tool", candidate, requirements)
    sources = [trusted_source(tmp_path, "t1-tool-qualification", "TOOL_QUALIFICATION", subject),
               trusted_source(tmp_path, "t1-tool-availability", "TOOL_AVAILABILITY", subject)]
    trust = write(tmp_path, "tool-trust.yaml", {"sources": sources})
    envelope_path = tmp_path / "tool-envelope.yaml"
    planned_result = invoke("plan", write(tmp_path, "tool-order.yaml", order()),
                            "--root", ROOT, "--trust-context", trust,
                            "--task-metadata", write(tmp_path, "tool-metadata.yaml", {"tool_requirements": requirements}),
                            "--candidate-snapshot", write(tmp_path, "tool-candidates.yaml", {"tools": [candidate]}),
                            "--require-ready", "--out", envelope_path)
    assert planned_result.returncode == 0, planned_result.stderr
    envelope = load_yaml(envelope_path)
    assert len(expected_observations(envelope)["tools"]) == 1
    return envelope_path, envelope, sources


def _t1_observation_source(tmp_path: Path, envelope: dict, trace: dict) -> dict:
    dimensions = [name for name in ("tools", "actors", "executor", "model")
                  if name == "tools" and expected_observations(envelope)["tools"]
                  or name == "actors" and expected_observations(envelope)["actors"]
                  or name == "executor" and envelope["executor"]["selected_executor"]
                  or name == "model" and envelope["model"]["selected_model"]]
    projection = observation_projection(envelope, trace, dimensions)
    snapshot = write(tmp_path, "observed-snapshot.yaml", projection)
    return {"ref": {"scheme": "file", "locator": str(snapshot)},
            "digest": "sha256:" + sha256(snapshot.read_bytes()).hexdigest(),
            "predicate": "EXECUTION_OBSERVATIONS", "subject": observation_subject(projection),
            "scope": "project:noema", "authority": "host-fixture",
            "valid_until": "2099-01-01T00:00:00Z"}


def test_t1_cov_tools_empty(tmp_path: Path) -> None:
    envelope_path, _, sources = _t1_tool_plan(tmp_path)
    trace_path = tmp_path / "empty-tool-trace.yaml"
    assert invoke("record", envelope_path, write(tmp_path, "empty-tool-actual.yaml",
           {"outcome": "SUCCESS", "context_reads": [], "tool_events": []}),
           "--out", trace_path).returncode == 0
    compared = invoke("compare", envelope_path, trace_path, "--json")
    assert compared.returncode != 0
    report = json.loads(compared.stdout)
    assert report["status"] == "INCOMPLETE"
    assert report["coverage"]["tools"]["status"] == "INCOMPLETE"
    assert report["coverage"]["tools"]["missing"]
    trust = write(tmp_path, "empty-tool-trust.yaml", {"sources": sources + [
        _t1_observation_source(tmp_path, load_yaml(envelope_path), load_yaml(trace_path))]})
    assert json.loads(invoke("compare", envelope_path, trace_path, "--trust-context", trust,
                             "--json").stdout)["status"] == "INCOMPLETE"


def test_t1_duplicate_candidate_identifier_never_selects_last_silently(tmp_path: Path) -> None:
    first = {"id": "same-id", "allowed": True, "available": True,
             "availability": "AVAILABLE", "qualification": "VERIFIED",
             "capabilities": ["read"], "source_relation": "DIRECT"}
    second = {**first, "source_relation": "BROAD"}
    requirements = {"capabilities": ["read"]}
    subject = candidate_subject("tool", second, requirements)
    trust = write(tmp_path, "duplicate-candidate-trust.yaml", {"sources": [
        trusted_source(tmp_path, "duplicate-candidate-q", "TOOL_QUALIFICATION", subject),
        trusted_source(tmp_path, "duplicate-candidate-a", "TOOL_AVAILABILITY", subject)]})
    envelope_path = tmp_path / "duplicate-candidate-envelope.yaml"
    assert invoke("plan", write(tmp_path, "duplicate-candidate-order.yaml", order()),
                  "--root", ROOT, "--trust-context", trust,
                  "--task-metadata", write(tmp_path, "duplicate-candidate-metadata.yaml",
                                            {"tool_requirements": requirements}),
                  "--candidate-snapshot", write(tmp_path, "duplicate-candidate-snapshot.yaml",
                                                 {"tools": [first, second]}),
                  "--out", envelope_path).returncode == 0
    checked = invoke("validate", envelope_path, "--root", ROOT, "--trust-context", trust,
                     "--require-ready", "--json")
    assert checked.returncode != 0
    assert "TOOL_CANDIDATE_AMBIGUOUS" in checked.stdout


def test_t1_cov_tools_complete(tmp_path: Path) -> None:
    envelope_path, envelope, sources = _t1_tool_plan(tmp_path)
    obligation = expected_observations(envelope)["tools"][0]["obligation_ref"]
    actual = {"outcome": "SUCCESS", "context_reads": [], "tool_events": [{
        "candidate": "reader", "action": "CALL", "result": "SUCCESS",
        "reason_codes": [], "evidence_refs": [], "obligation_ref": obligation}]}
    trace_path = tmp_path / "complete-tool-trace.yaml"
    assert invoke("record", envelope_path, write(tmp_path, "complete-tool-actual.yaml", actual),
                  "--out", trace_path).returncode == 0
    without = invoke("compare", envelope_path, trace_path, "--json")
    assert json.loads(without.stdout)["status"] == "INCOMPLETE"
    source = _t1_observation_source(tmp_path, envelope, load_yaml(trace_path))
    trust = write(tmp_path, "complete-tool-trust.yaml", {"sources": sources + [source]})
    compared = invoke("compare", envelope_path, trace_path, "--trust-context", trust, "--json")
    assert compared.returncode == 0, compared.stdout + compared.stderr
    assert json.loads(compared.stdout)["coverage"]["tools"]["status"] == "COMPLETE"
    validated = invoke("validate", trace_path, "--envelope", envelope_path, "--root", ROOT,
                       "--trust-context", trust, "--require-ready", "--json")
    assert validated.returncode == 0, validated.stdout + validated.stderr
    assert json.loads(validated.stdout)["status"] == "PASS"


def test_final_r3_unbound_tool_never_certifies_with_host_snapshot(tmp_path: Path) -> None:
    envelope_path, envelope, sources = _t1_tool_plan(tmp_path)
    explained = invoke("explain", envelope_path, "--json")
    assert explained.returncode == 0
    obligation = json.loads(explained.stdout)["expected_observations"]["tools"][0]["obligation_ref"]
    actual = {"outcome": "SUCCESS", "context_reads": [], "tool_events": [{
        "candidate": "reader", "action": "CALL", "result": "SUCCESS",
        "reason_codes": [], "evidence_refs": []}]}
    trace_path = tmp_path / "unbound-tool-trace.yaml"
    recorded = invoke("record", envelope_path, write(tmp_path, "unbound-tool-actual.yaml", actual),
                      "--out", trace_path)
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    trace = load_yaml(trace_path)
    assert "obligation_ref" not in trace["actual"]["tool_events"][0]
    source = _t1_observation_source(tmp_path, envelope, trace)
    trust = write(tmp_path, "unbound-tool-trust.yaml", {"sources": sources + [source]})
    compared = invoke("compare", envelope_path, trace_path, "--trust-context", trust, "--json")
    validated = invoke("validate", trace_path, "--envelope", envelope_path,
                       "--root", ROOT, "--trust-context", trust, "--require-ready", "--json")
    assert compared.returncode != 0
    assert validated.returncode != 0
    for response in (compared, validated):
        report = json.loads(response.stdout)
        assert report["status"] == "FAIL"
        assert report["coverage"]["tools"]["status"] == "INCOMPLETE"
        assert report["coverage"]["tools"]["missing"] == [obligation]
        assert report["coverage"]["tools"]["unexpected"] == [0]
        assert "TOOL_OBLIGATION_UNBOUND" in report["deviations"]
        assert report["observation_verification"]["state"] == "VERIFIED"


def test_final_r2_legacy_tool_binding_cannot_certify(tmp_path: Path) -> None:
    envelope_path, envelope, sources = _t1_tool_plan(tmp_path)
    actual = {"outcome": "SUCCESS", "context_reads": [], "tool_events": [{
        "candidate": "reader", "action": "CALL", "result": "SUCCESS",
        "reason_codes": [], "evidence_refs": []}]}
    trace_path = tmp_path / "legacy-tool-trace.yaml"
    assert invoke("record", envelope_path, write(tmp_path, "legacy-tool-actual.yaml", actual),
                  "--out", trace_path).returncode == 0
    trace = load_yaml(trace_path)
    trace["contract_revision"] = 2
    trace["observation_coverage"] = {
        name: "OBSERVED" for name in ("executor", "model", "tools", "topology", "historical_reads")
    }
    write(tmp_path, "legacy-tool-trace.yaml", trace)
    source = _t1_observation_source(tmp_path, envelope, trace)
    trust = write(tmp_path, "legacy-tool-trust.yaml", {"sources": sources + [source]})
    checked = invoke("validate", trace_path, "--envelope", envelope_path,
                     "--root", ROOT, "--trust-context", trust, "--require-ready", "--json")
    assert checked.returncode != 0
    report = json.loads(checked.stdout)
    assert report["coverage"]["tools"]["status"] == "COMPLETE"
    assert report["observation_verification"]["state"] == "VERIFIED"
    assert report["status"] == "INCOMPLETE"
    assert "legacy_obligation_binding" in report["missing_observations"]


def test_final_unbound_actor_cannot_certify_with_host_snapshot(tmp_path: Path) -> None:
    envelope_path, envelope, sources = _t1_parallel_plan(tmp_path)
    obligations = expected_observations(envelope)["actors"]
    actors = [{**item["binding"], "participation": "REPORTED_EXECUTED",
               "obligation_ref": item["obligation_ref"]} for item in obligations]
    actors[0].pop("obligation_ref")
    trace_path = tmp_path / "unbound-actor-trace.yaml"
    assert invoke("record", envelope_path, write(tmp_path, "unbound-actor-actual.yaml",
           {"outcome": "SUCCESS", "context_reads": [], "role_bindings": actors}),
           "--out", trace_path).returncode == 0
    snapshot = _t1_observation_source(tmp_path, envelope, load_yaml(trace_path))
    trust = write(tmp_path, "unbound-actor-trust.yaml", {"sources": sources + [snapshot]})
    compared = invoke("compare", envelope_path, trace_path, "--trust-context", trust, "--json")
    validated = invoke("validate", trace_path, "--envelope", envelope_path,
                       "--root", ROOT, "--trust-context", trust, "--require-ready", "--json")
    assert compared.returncode != 0 and validated.returncode != 0
    for response in (compared, validated):
        report = json.loads(response.stdout)
        assert report["status"] == "FAIL"
        assert report["coverage"]["actors"]["missing"] == [obligations[0]["obligation_ref"]]
        assert report["coverage"]["actors"]["matched"] == [obligations[1]["obligation_ref"]]
        assert report["coverage"]["actors"]["unexpected"] == [0]
        assert "ACTOR_OBLIGATION_UNBOUND" in report["deviations"]
        assert report["observation_verification"]["state"] == "VERIFIED"


def test_final_actor_absence_binding_diagnostics_public(tmp_path: Path) -> None:
    envelope_path, envelope, sources = _t1_parallel_plan(tmp_path)
    explained = invoke("explain", envelope_path, "--json")
    assert explained.returncode == 0
    obligations = json.loads(explained.stdout)["expected_observations"]["actors"]
    assert len(obligations) == 2
    base = [{**item["binding"], "obligation_ref": item["obligation_ref"],
             "participation": "REPORTED_EXECUTED"} for item in obligations]
    for label, contradictory in (("exact", False), ("wrong", True)):
        actors = deepcopy(base)
        actors[0]["participation"] = "REPORTED_NOT_EXECUTED"
        if contradictory:
            actors[0].update({"workspace": "wrong-workspace", "branch": "wrong-branch",
                              "scope": ["wrong/scope"]})
        trace_path = tmp_path / f"{label}-absence-trace.yaml"
        recorded = invoke("record", envelope_path, write(tmp_path, f"{label}-absence-actual.yaml",
                          {"outcome": "SUCCESS", "context_reads": [], "role_bindings": actors}),
                          "--out", trace_path)
        assert recorded.returncode == 0, recorded.stdout + recorded.stderr
        snapshot = _t1_observation_source(tmp_path, envelope, load_yaml(trace_path))
        trust = write(tmp_path, f"{label}-absence-trust.yaml", {"sources": sources + [snapshot]})
        compared = invoke("compare", envelope_path, trace_path, "--trust-context", trust, "--json")
        validated = invoke("validate", trace_path, "--envelope", envelope_path,
                           "--root", ROOT, "--trust-context", trust, "--require-ready", "--json")
        assert compared.returncode != 0 and validated.returncode != 0
        for response in (compared, validated):
            report = json.loads(response.stdout)
            assert report["status"] == "FAIL"
            assert report["coverage"]["actors"]["status"] == "COMPLETE"
            assert report["coverage"]["actors"]["explicitly_absent"] == [obligations[0]["obligation_ref"]]
            assert report["coverage"]["actors"]["matched"] == [obligations[1]["obligation_ref"]]
            assert "EXPECTED_ACTOR_NOT_EXECUTED" in report["deviations"]
            assert ("ACTOR_BINDING_MISMATCH" in report["deviations"]) is contradictory
            assert report["observation_verification"]["state"] == "VERIFIED"


def test_final_foreign_tool_refs_never_fall_back_to_candidate(tmp_path: Path) -> None:
    envelope_path, envelope, _ = _t1_tool_plan(tmp_path)
    expected_ref = expected_observations(envelope)["tools"][0]["obligation_ref"]
    variants = []
    for field in ("attempt_id", "action_id"):
        foreign = deepcopy(envelope)
        foreign["intent"][field] += "-other"
        variants.append(expected_observations(foreign)["tools"][0]["obligation_ref"])
    foreign = deepcopy(envelope)
    foreign["execution_id"] = "exec-other"
    variants.append(expected_observations(foreign)["tools"][0]["obligation_ref"])
    variants.append("sha256:" + "f" * 64)
    for index, ref in enumerate(variants):
        trace_path = tmp_path / f"foreign-{index}.yaml"
        actual = {"outcome": "SUCCESS", "context_reads": [], "tool_events": [{
            "candidate": "reader", "action": "CALL", "result": "SUCCESS",
            "reason_codes": [], "evidence_refs": [], "obligation_ref": ref}]}
        assert invoke("record", envelope_path, write(tmp_path, f"actual-{index}.yaml", actual),
                      "--out", trace_path).returncode == 0
        compared = invoke("compare", envelope_path, trace_path, "--json")
        assert compared.returncode != 0
        report = json.loads(compared.stdout)
        assert report["status"] == "FAIL"
        assert report["coverage"]["tools"]["missing"] == [expected_ref]
        assert report["coverage"]["tools"]["unexpected"] == [0]
        assert "TOOL_OBLIGATION_MISMATCH" in report["deviations"]


def test_final_snapshot_without_ref_cannot_verify_bound_trace(tmp_path: Path) -> None:
    envelope_path, envelope, sources = _t1_tool_plan(tmp_path)
    event = {"candidate": "reader", "action": "CALL", "result": "SUCCESS",
             "reason_codes": [], "evidence_refs": []}
    unbound_path = tmp_path / "unbound.yaml"
    assert invoke("record", envelope_path, write(tmp_path, "unbound-actual.yaml",
           {"outcome": "SUCCESS", "context_reads": [], "tool_events": [event]}),
           "--out", unbound_path).returncode == 0
    unbound = load_yaml(unbound_path)
    stale_source = _t1_observation_source(tmp_path, envelope, unbound)
    bound = deepcopy(unbound)
    bound["actual"]["tool_events"][0]["obligation_ref"] = expected_observations(envelope)["tools"][0]["obligation_ref"]
    bound_path = write(tmp_path, "manually-bound.yaml", bound)
    checked = invoke("compare", envelope_path, bound_path,
                     "--trust-context", write(tmp_path, "stale-trust.yaml",
                     {"sources": sources + [stale_source]}), "--json")
    report = json.loads(checked.stdout)
    assert report["status"] == "INCOMPLETE"
    assert report["observation_verification"]["state"] == "UNVERIFIED"
    relabeled = {**stale_source, "subject": observation_subject(
        observation_projection(envelope, bound, ["tools"]))}
    checked = invoke("compare", envelope_path, bound_path,
                     "--trust-context", write(tmp_path, "relabeled-trust.yaml",
                     {"sources": sources + [relabeled]}), "--json")
    report = json.loads(checked.stdout)
    assert report["status"] == "INCOMPLETE"
    assert report["observation_verification"]["state"] == "INVALID"


def test_final_r2_without_occurrence_obligations_keeps_prior_result(tmp_path: Path) -> None:
    envelope_path, _ = planned(tmp_path, order())
    trace_path = tmp_path / "legacy-direct.yaml"
    assert invoke("record", envelope_path, write(tmp_path, "direct-actual.yaml",
           {"outcome": "SUCCESS", "context_reads": []}), "--out", trace_path).returncode == 0
    trace = load_yaml(trace_path)
    trace["contract_revision"] = 2
    trace["observation_coverage"] = {
        name: "OBSERVED" for name in ("executor", "model", "tools", "topology", "historical_reads")
    }
    write(tmp_path, "legacy-direct.yaml", trace)
    compared = invoke("compare", envelope_path, trace_path, "--json")
    assert compared.returncode == 0, compared.stdout + compared.stderr
    report = json.loads(compared.stdout)
    assert report["status"] == "PASS"
    assert "legacy_obligation_binding" not in report["missing_observations"]


def test_t1_obligation_duplicates_absence_and_fail_precedence(tmp_path: Path) -> None:
    envelope_path, envelope, _ = _t1_tool_plan(tmp_path)
    obligation = expected_observations(envelope)["tools"][0]["obligation_ref"]
    explained = invoke("explain", envelope_path, "--json")
    assert explained.returncode == 0
    assert json.loads(explained.stdout)["expected_observations"]["tools"][0]["obligation_ref"] == obligation
    event = {"candidate": "reader", "action": "CALL", "result": "SUCCESS",
             "reason_codes": [], "evidence_refs": [], "obligation_ref": obligation}
    trace_path = tmp_path / "duplicate-trace.yaml"
    actual = {"outcome": "SUCCESS", "context_reads": [], "tool_events": [event, event]}
    assert invoke("record", envelope_path, write(tmp_path, "duplicate-actual.yaml", actual),
                  "--out", trace_path).returncode == 0
    compared = invoke("compare", envelope_path, trace_path, "--json")
    assert compared.returncode != 0
    report = json.loads(compared.stdout)
    assert report["status"] == "FAIL"
    assert report["coverage"]["tools"]["duplicates"] == [obligation]
    validated = invoke("validate", trace_path, "--envelope", envelope_path,
                       "--require-ready", "--json")
    assert json.loads(validated.stdout)["status"] == "FAIL"
    absent = {**event, "result": "NOT_CALLED"}
    absent_actual = {"outcome": "SUCCESS", "context_reads": [], "tool_events": [absent]}
    absent_trace = tmp_path / "absent-tool-trace.yaml"
    assert invoke("record", envelope_path, write(tmp_path, "absent-tool-actual.yaml", absent_actual),
                  "--out", absent_trace).returncode == 0
    absent_report = json.loads(invoke("compare", envelope_path, absent_trace, "--json").stdout)
    assert absent_report["status"] == "FAIL"
    assert absent_report["coverage"]["tools"]["explicitly_absent"] == [obligation]


def test_t1_actor_wrong_workspace_and_partial_fields(tmp_path: Path) -> None:
    envelope_path, envelope, _ = _t1_parallel_plan(tmp_path)
    obligations = expected_observations(envelope)["actors"]
    complete = [{**item["binding"], "participation": "REPORTED_EXECUTED",
                 "obligation_ref": item["obligation_ref"]} for item in obligations]
    complete[0]["workspace"] = "wrong-workspace"
    wrong_trace = tmp_path / "wrong-actor-trace.yaml"
    assert invoke("record", envelope_path, write(tmp_path, "wrong-actor-actual.yaml",
           {"outcome": "SUCCESS", "context_reads": [], "role_bindings": complete}),
           "--out", wrong_trace).returncode == 0
    report = json.loads(invoke("compare", envelope_path, wrong_trace, "--json").stdout)
    assert report["status"] == "FAIL"
    assert "ACTOR_BINDING_MISMATCH" in report["deviations"]
    complete[0].pop("workspace")
    partial_trace = tmp_path / "partial-actor-trace.yaml"
    assert invoke("record", envelope_path, write(tmp_path, "partial-actor-actual.yaml",
           {"outcome": "SUCCESS", "context_reads": [], "role_bindings": complete}),
           "--out", partial_trace).returncode == 0
    partial = json.loads(invoke("compare", envelope_path, partial_trace, "--json").stdout)
    assert partial["status"] == "INCOMPLETE"
    assert obligations[0]["obligation_ref"] in partial["coverage"]["actors"]["missing"]


def _t1_parallel_plan(tmp_path: Path) -> tuple[Path, dict, list[dict]]:
    metadata = {"parallel_isolated": True, "serialized_publication": True,
                "write_scopes": ["src/a", "src/b"], "role_bindings": [
                    {"role_id": "a", "scope": ["src/a"], "workspace": "a-work", "branch": "a-branch"},
                    {"role_id": "b", "scope": ["src/b"], "workspace": "b-work", "branch": "b-branch"}]}
    envelope_path = tmp_path / "parallel-envelope.yaml"
    assert invoke("plan", write(tmp_path, "parallel-order.yaml",
           order(allowed_writes=["src/a", "src/b"])), "--root", ROOT,
           "--host-capabilities", write(tmp_path, "parallel-host.yaml",
           {"profile": "eg.repo-agent.v0", "capabilities": {"repo_write_reversible": True}}),
           "--task-metadata", write(tmp_path, "parallel-metadata.yaml", metadata),
           "--out", envelope_path).returncode == 0
    envelope = load_yaml(envelope_path)
    sources = [trusted_source(tmp_path, "t1-isolation", "HOST_ISOLATION",
                              envelope["material_binding"]["digest"])]
    return envelope_path, envelope, sources


def test_t1_cov_actor_empty(tmp_path: Path) -> None:
    envelope_path, _, _ = _t1_parallel_plan(tmp_path)
    trace_path = tmp_path / "empty-actor-trace.yaml"
    assert invoke("record", envelope_path, write(tmp_path, "empty-actor-actual.yaml",
           {"outcome": "SUCCESS", "context_reads": [], "role_bindings": []}),
           "--out", trace_path).returncode == 0
    compared = invoke("compare", envelope_path, trace_path, "--json")
    assert compared.returncode != 0
    report = json.loads(compared.stdout)
    assert report["status"] == "INCOMPLETE"
    assert len(report["coverage"]["actors"]["missing"]) == 2


def test_t1_cov_actors_complete(tmp_path: Path) -> None:
    envelope_path, envelope, sources = _t1_parallel_plan(tmp_path)
    actors = [{**item["binding"], "participation": "REPORTED_EXECUTED",
               "obligation_ref": item["obligation_ref"]}
              for item in expected_observations(envelope)["actors"]]
    trace_path = tmp_path / "complete-actors-trace.yaml"
    actual = {"outcome": "SUCCESS", "context_reads": [], "role_bindings": actors}
    assert invoke("record", envelope_path, write(tmp_path, "complete-actors-actual.yaml", actual),
                  "--out", trace_path).returncode == 0
    without = invoke("compare", envelope_path, trace_path, "--json")
    assert json.loads(without.stdout)["status"] == "INCOMPLETE"
    source = _t1_observation_source(tmp_path, envelope, load_yaml(trace_path))
    trust = write(tmp_path, "complete-actors-trust.yaml", {"sources": sources + [source]})
    compared = invoke("compare", envelope_path, trace_path, "--trust-context", trust, "--json")
    assert compared.returncode == 0, compared.stdout + compared.stderr
    validated = invoke("validate", trace_path, "--envelope", envelope_path, "--root", ROOT,
                       "--trust-context", trust, "--require-ready", "--json")
    assert validated.returncode == 0, validated.stdout + validated.stderr


def _t1_resolver_plan(tmp_path: Path, integrity: str | None) -> tuple[Path, Path, Path]:
    target = tmp_path / "resolver-result.txt"
    target.write_bytes(b"verified result")
    receipt = {"resolver": "external-resolver", "status": "RESOLVED",
               "resolution_ref": {"scheme": "file", "locator": str(target)},
               "satisfied_capabilities": ["cap-a"], "unresolved_capabilities": [],
               "integrity": integrity, "observed_at": None}
    subject = candidate_subject("resolver", receipt, {"capability": "cap-a"})
    trust = write(tmp_path, "t1-resolver-trust.yaml", {"sources": [
        trusted_source(tmp_path, "t1-resolver-assertion", "RESOLVER_SATISFACTION", subject)]})
    envelope_path = tmp_path / "t1-resolver-envelope.yaml"
    assert invoke("plan", write(tmp_path, "t1-resolver-order.yaml",
           order(capability_requirements=[{"id": "cap-a"}])), "--root", ROOT,
           "--trust-context", trust, "--resolver-receipt", write(tmp_path, "t1-receipt.yaml", receipt),
           "--out", envelope_path).returncode == 0
    return envelope_path, trust, target


def test_t1_resolver_drift(tmp_path: Path) -> None:
    target = tmp_path / "resolver-result.txt"
    digest = "sha256:" + sha256(b"verified result").hexdigest()
    envelope_path, trust, target = _t1_resolver_plan(tmp_path, digest)
    assert invoke("validate", envelope_path, "--root", ROOT, "--trust-context", trust,
                  "--require-ready").returncode == 0
    target.write_bytes(b"mutated result")
    checked = invoke("validate", envelope_path, "--root", ROOT, "--trust-context", trust,
                     "--require-ready", "--json")
    assert checked.returncode != 0
    assert json.loads(checked.stdout)["readiness"] == "NOT_EXECUTION_READY"


def test_t1_resolver_no_integrity(tmp_path: Path) -> None:
    envelope_path, trust, _ = _t1_resolver_plan(tmp_path, None)
    checked = invoke("validate", envelope_path, "--root", ROOT, "--trust-context", trust,
                     "--require-ready", "--json")
    assert checked.returncode != 0
    report = json.loads(checked.stdout)
    assert report["readiness"] == "NOT_EXECUTION_READY"
    assert any(item["predicate"] == "RESOLVER_SATISFACTION" and item["state"] == "UNVERIFIED"
               for item in report["evidence_results"])
