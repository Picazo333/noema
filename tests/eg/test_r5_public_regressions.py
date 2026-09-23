"""Public-entrypoint regressions for the seven adversarial R4 P1 families."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

from noema.loader import dump_yaml, load_yaml
from noema.eg.bindings import gate_fingerprint, material_digest, read_subject
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
