"""Resume verification over WorkOrder/Handoff authorities and observed state."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess

from ..loader import load_yaml
from ..manifest import load_manifest, resolve_state_scope
from ..refs import safe_project_path
from ..schemas import schema_root

from .semantics import contract_issues, normalize_scope, raise_for_issues, validate_envelope_semantics, validate_resume_semantics


_RECOVERY_FIELDS = {
    "project_id": str, "role_id": str, "branch": str, "workspace": str,
    "sha": str, "closed_claims": list, "closed_evidence_refs": list,
    "active_blockers": list, "outstanding_human_gates": list,
    "prohibited_scope": list, "effective_allowed_writes": list,
    "next_action": str, "next_action_kind": str, "handoff_ref": dict,
}


def validate_recovery_projection(state: object) -> list[str]:
    """Validate the operational checkpoint without creating a public artifact."""
    if not isinstance(state, dict):
        return ["RECOVERY_PROJECTION_INVALID"]
    missing = [f"{name.upper()}_MISSING" for name in _RECOVERY_FIELDS if name not in state]
    if "frontier_ref" not in state:
        missing.append("FRONTIER_REF_MISSING")
    if "envelope_ref" not in state:
        missing.append("ENVELOPE_REF_MISSING")
    if missing:
        return missing
    invalid = [f"{name.upper()}_INVALID" for name, kind in _RECOVERY_FIELDS.items()
               if not isinstance(state[name], kind)]
    for name in ("project_id", "role_id", "branch", "workspace", "next_action"):
        if isinstance(state[name], str) and not state[name].strip():
            invalid.append(f"{name.upper()}_INVALID")
    if not isinstance(state["sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", state["sha"]):
        invalid.append("SHA_INVALID")
    for name in ("executor_id", "model_id"):
        if name in state and state[name] is not None and (not isinstance(state[name], str) or not state[name].strip()):
            invalid.append(f"{name.upper()}_INVALID")
    for name in ("handoff_ref", "envelope_ref", "frontier_ref"):
        value = state[name]
        if value is None and name != "handoff_ref":
            continue
        if not isinstance(value, dict) or value.get("scheme") != "repo" or not isinstance(value.get("locator"), str) or not value["locator"]:
            invalid.append(f"{name.upper()}_INVALID")
    for name in ("closed_claims", "active_blockers",
                 "outstanding_human_gates", "prohibited_scope", "effective_allowed_writes"):
        if isinstance(state[name], list) and any(not isinstance(item, str) or not item for item in state[name]):
            invalid.append(f"{name.upper()}_INVALID")
    if isinstance(state["closed_evidence_refs"], list) and any(
        not isinstance(item, (str, dict)) for item in state["closed_evidence_refs"]
    ):
        invalid.append("CLOSED_EVIDENCE_REFS_INVALID")
    if state.get("next_action_kind") not in {"EXECUTE", "VERIFY", "RESOLVE_BLOCKERS", "AWAIT_HUMAN"}:
        invalid.append("NEXT_ACTION_KIND_INVALID")
    return sorted(set(invalid))


def _recovery_ref_path(root: Path, ref: dict) -> Path:
    if ref["scheme"] != "repo":
        raise ValueError("Recovery references must be project-local")
    return safe_project_path(root, ref["locator"])


def recover_current_execution(root: Path, *, last_seen_sha: str | None = None,
                              last_seen_state_ref: str | None = None,
                              runtime_pressure: dict | None = None) -> dict:
    """Derive a read-only recovery view from the declared current cursor."""
    root = root.resolve()
    reasons: list[str] = []
    report: dict = {"status": "INCOMPLETE", "continuation": "INCOMPLETE",
                    "session_freshness": "UNKNOWN", "reason_codes": reasons,
                    "checkpoint_ready": False,
                    "context_pressure": context_pressure_advisory(runtime_pressure)}
    try:
        manifest = load_manifest(root)
        manifest_project_id = manifest["project"]["id"]
        state_path = resolve_state_scope(root, manifest, "execution")
    except (OSError, ValueError, KeyError, TypeError):
        reasons.append("CURRENT_STATE_CURSOR_UNAVAILABLE")
        return report
    report["state_ref"] = {"scheme": "repo", "locator": state_path.relative_to(root).as_posix()}
    if not state_path.is_file():
        reasons.append("RECOVERY_CHECKPOINT_MISSING")
        return report
    try:
        state = load_yaml(state_path)
    except (OSError, ValueError):
        reasons.append("RECOVERY_CHECKPOINT_INVALID")
        return report
    reasons.extend(validate_recovery_projection(state))
    if reasons:
        return report
    report["checkpoint"] = state
    if state["project_id"] != manifest_project_id:
        report["status"] = "FAIL"
        reasons.append("RECOVERY_PROJECT_MISMATCH")
        return report
    try:
        observed_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        observed_branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        reasons.append("OBSERVED_REPOSITORY_STATE_UNAVAILABLE")
        return report
    report["observed"] = {"sha": observed_sha, "branch": observed_branch,
                          "workspace": str(root)}
    if state["sha"] != observed_sha or state["branch"] != observed_branch or Path(state["workspace"]).resolve() != root:
        report["status"] = "STALE_CHECKPOINT"
        reasons.append("STALE_CHECKPOINT")
    if last_seen_sha is not None or last_seen_state_ref is not None:
        ref_matches = (last_seen_state_ref is None or
                       last_seen_state_ref == f"repo://{state_path.relative_to(root).as_posix()}")
        if not ref_matches or last_seen_sha is not None and last_seen_sha != observed_sha:
            report["session_freshness"] = "STALE"
            reasons.append("STALE_SESSION")
        elif last_seen_sha is not None:
            report["session_freshness"] = "CURRENT"
    try:
        handoff = load_yaml(_recovery_ref_path(root, state["handoff_ref"]))
    except (OSError, ValueError, KeyError):
        reasons.append("HANDOFF_UNAVAILABLE")
        return report
    if contract_issues("handoff", handoff, schema_root()):
        reasons.append("HANDOFF_INVALID")
        return report
    report["handoff"] = handoff
    work_ref = handoff.get("work_order_ref", "")
    if not isinstance(work_ref, str) or not work_ref.startswith("repo://"):
        reasons.append("WORK_ORDER_REF_INVALID")
        return report
    try:
        work_path = safe_project_path(root, work_ref.removeprefix("repo://"))
        work_order = load_yaml(work_path)
    except (OSError, ValueError):
        reasons.append("WORK_ORDER_UNAVAILABLE")
        return report
    if contract_issues("work-order", work_order, schema_root()):
        reasons.append("WORK_ORDER_INVALID")
        return report
    if work_order.get("project_id") != manifest_project_id:
        reasons.append("RECOVERY_PROJECT_MISMATCH")
    report["work_order"] = work_order
    required_gates = set(work_order.get("human_gates", []))
    if required_gates - set(state["outstanding_human_gates"]):
        reasons.append("HUMAN_GATE_DROPPED_WITHOUT_EVIDENCE")
    try:
        declared_writes = _scope_set(work_order.get("allowed_writes", []))
        effective_writes = _scope_set(state["effective_allowed_writes"])
        prohibited = _scope_set(work_order.get("scope", {}).get("excluded", []))
        state_prohibited = _scope_set(state["prohibited_scope"])
        if not _writes_within_boundaries(effective_writes, declared_writes):
            reasons.append("EFFECTIVE_WRITES_BROADENED")
        if not prohibited.issubset(state_prohibited):
            reasons.append("PROHIBITED_SCOPE_DROPPED")
        if any(_scopes_overlap(write, excluded) for write in effective_writes for excluded in state_prohibited):
            reasons.append("PROHIBITED_SCOPE_ACCESS")
    except ValueError:
        reasons.append("RECOVERY_SCOPE_INVALID")
    if handoff.get("status") in {"blocked", "failed"}:
        reasons.append("HANDOFF_NOT_CONTINUABLE")
    envelope = None
    if state["envelope_ref"] is not None:
        try:
            envelope = load_yaml(_recovery_ref_path(root, state["envelope_ref"]))
        except (OSError, ValueError, KeyError):
            reasons.append("ENVELOPE_UNAVAILABLE")
            return report
        if contract_issues("execution-envelope", envelope, schema_root()):
            reasons.append("ENVELOPE_INVALID")
            return report
        report["envelope"] = envelope
        planned_model = envelope.get("intent", {}).get("planned_model")
        if planned_model is not None and state.get("model_id") != planned_model:
            reasons.append("MODEL_MISMATCH")
    elif state["next_action_kind"] == "EXECUTE":
        reasons.append("EXECUTION_ENVELOPE_REQUIRED")
    if envelope is not None:
        report["resume_semantics"] = resume_check(envelope, handoff, state)
        if report["resume_semantics"]["status"] != "PASS":
            reasons.extend(report["resume_semantics"]["reason_codes"])
    if state["active_blockers"]:
        reasons.append("ACTIVE_BLOCKERS")
    if state["outstanding_human_gates"]:
        reasons.append("OUTSTANDING_HUMAN_GATES")
    report["context_plan"] = _recovery_context_plan(root, state_path, state, handoff, work_order, work_ref)
    report["decision_ids"] = list(handoff.get("decisions", []))
    report["checkpoint_ready"] = not bool(set(reasons) - {
        "STALE_SESSION", "ACTIVE_BLOCKERS", "OUTSTANDING_HUMAN_GATES",
        "HANDOFF_NOT_CONTINUABLE",
    })
    if not reasons:
        # A current checkpoint is necessary, but not independent execution evidence.
        report["status"] = "PASS"
        report["continuation"] = "INCOMPLETE" if envelope is not None else "PASS"
    elif report["status"] != "STALE_CHECKPOINT" and (
        report.get("resume_semantics", {}).get("status") == "FAIL" or set(reasons) & {
        "RECOVERY_PROJECT_MISMATCH", "HUMAN_GATE_DROPPED_WITHOUT_EVIDENCE",
        "EFFECTIVE_WRITES_BROADENED", "PROHIBITED_SCOPE_DROPPED",
        "PROHIBITED_SCOPE_ACCESS", "MODEL_MISMATCH", "HANDOFF_NOT_CONTINUABLE",
        }
    ):
        report["status"] = "FAIL"
    return report


def _recovery_context_plan(root: Path, state_path: Path, state: dict,
                           handoff: dict, work_order: dict, work_ref: str) -> dict:
    refs = [
        {"scheme": "repo", "locator": "noema.project.yaml"},
        {"scheme": "repo", "locator": state_path.relative_to(root).as_posix()},
        state["handoff_ref"], {"scheme": "repo", "locator": work_ref.removeprefix("repo://")},
    ]
    if state["envelope_ref"] is not None:
        refs.append(state["envelope_ref"])
    for item in work_order.get("inputs", []):
        if isinstance(item, dict) and {"scheme", "locator"}.issubset(item):
            refs.append(item)
    if state["frontier_ref"] is not None:
        refs.append(state["frontier_ref"])
    for decision in handoff.get("decisions", []):
        if isinstance(decision, str) and decision.startswith("repo://"):
            refs.append({"scheme": "repo", "locator": decision.removeprefix("repo://")})
    seen = set()
    hot = []
    for ref in refs:
        key = (ref["scheme"], ref["locator"])
        if key not in seen:
            seen.add(key)
            hot.append({"ref": ref, "load_tier": "HOT"})
    return {"mode": "recover", "refs": hot,
            "exclusions": ["raw-conversations", "whole-repository", "all-handoffs",
                           "all-decisions", "all-evidence", "optional-research"]}


def context_pressure_advisory(snapshot: dict | None) -> dict:
    """Host-reported pressure never changes authority or execution readiness."""
    level = snapshot.get("context_pressure") if isinstance(snapshot, dict) else None
    mapping = {"LOW": "CONTINUE", "MODERATE": "CONTINUE",
               "HIGH": "PREPARE_NEW_SESSION", "CRITICAL": "MIGRATE_NOW"}
    if not isinstance(level, str) or level not in mapping:
        return {"level": "UNKNOWN", "provenance": "UNKNOWN", "recommendation": None}
    return {"level": level, "provenance": "HOST_REPORTED", "recommendation": mapping[level]}


def recovery_requirements(
    work_order: dict,
    baseline_sha: str | None,
    metadata: dict | None = None,
    policy: dict | None = None,
    effective_executor: str | None = None,
) -> dict:
    metadata = metadata or {}
    return {
        "retry_cap": int((policy or {}).get("retry_cap", 1)),
        "idempotency_key": metadata.get("idempotency_key"),
        "checkpoint_ref": metadata.get("checkpoint_ref"),
        "rollback_ref": metadata.get("rollback_ref"),
        "resume_check_required": True,
        "expected_sha": baseline_sha,
        "expected_role": metadata.get("role_id"),
        "expected_executor": effective_executor,
        "expected_branch": metadata.get("branch"),
        "expected_workspace": metadata.get("workspace"),
        "expected_frontier_ref": metadata.get("frontier_ref"),
        "required_closed_claims": list(work_order.get("quality_claims", [])),
        "required_human_gates": list(work_order.get("human_gates", [])),
        "prohibited_scope": list(work_order.get("scope", {}).get("excluded", [])),
        "allowed_writes": list(work_order.get("allowed_writes", [])),
    }


def resume_check(
    envelope: dict,
    handoff: dict,
    current_state: dict | None = None,
    *,
    verified_gates: set[str] | None = None,
) -> dict:
    """Return PASS/FAIL/INCOMPLETE without rewriting historical evidence."""
    raise_for_issues(validate_envelope_semantics(envelope))
    state = current_state or {}
    requirements = envelope.get("recovery", {})
    failures: list[str] = []
    incomplete: list[str] = []
    handoff_ref = handoff.get("work_order_ref")
    if isinstance(handoff_ref, str) and "://" in handoff_ref:
        scheme, locator = handoff_ref.split("://", 1)
        handoff_ref = {"scheme": scheme, "locator": locator}
    expected_ref = envelope.get("work_order_ref", {})
    if not isinstance(handoff_ref, dict) or any(
        handoff_ref.get(key) != expected_ref.get(key) for key in ("scheme", "locator")
    ):
        failures.append("WORK_ORDER_MISMATCH")
    required_fields = {
        "project_id": "PROJECT_STATE_MISSING",
        "role_id": "ROLE_STATE_MISSING",
        "branch": "BRANCH_STATE_MISSING",
        "workspace": "WORKSPACE_STATE_MISSING",
        "sha": "SHA_STATE_MISSING",
        "frontier_ref": "FRONTIER_STATE_MISSING",
        "closed_claims": "CLOSED_CLAIMS_MISSING",
        "closed_evidence_refs": "CLOSED_EVIDENCE_MISSING",
        "active_blockers": "BLOCKERS_STATE_MISSING",
        "outstanding_human_gates": "HUMAN_GATES_STATE_MISSING",
        "prohibited_scope": "PROHIBITED_SCOPE_STATE_MISSING",
        "effective_allowed_writes": "EFFECTIVE_WRITES_STATE_MISSING",
        "next_action": "NEXT_ACTION_MISSING",
        "next_action_kind": "NEXT_ACTION_KIND_MISSING",
    }
    for field, reason in required_fields.items():
        if field not in state:
            incomplete.append(reason)
    if incomplete:
        return {"status": "INCOMPLETE", "reason_codes": incomplete}
    if requirements.get("expected_executor") and "executor_id" not in state:
        return {"status": "INCOMPLETE", "reason_codes": ["EXECUTOR_STATE_MISSING"]}
    if state["project_id"] != envelope.get("project_id"):
        failures.append("PROJECT_MISMATCH")
    expected_role = requirements.get("expected_role")
    if expected_role and state["role_id"] != expected_role:
        failures.append("ROLE_MISMATCH")
    expected_executor = requirements.get("expected_executor")
    if expected_executor and state.get("executor_id") != expected_executor:
        failures.append("EXECUTOR_MISMATCH")
    if requirements.get("expected_branch") and state["branch"] != requirements["expected_branch"]:
        failures.append("BRANCH_MISMATCH")
    if requirements.get("expected_workspace") and state["workspace"] != requirements["expected_workspace"]:
        failures.append("WORKSPACE_MISMATCH")
    expected_sha = requirements.get("expected_sha")
    if expected_sha and state["sha"] != expected_sha:
        failures.append("STALE_SHA")
    if requirements.get("expected_frontier_ref") and state["frontier_ref"] != requirements["expected_frontier_ref"]:
        failures.append("FRONTIER_MISMATCH")
    missing_claims = set(requirements.get("required_closed_claims", [])) - set(state["closed_claims"])
    if missing_claims:
        failures.append("CLOSED_CLAIMS_INCOMPLETE")
    if requirements.get("required_closed_claims") and not state["closed_evidence_refs"]:
        failures.append("CLOSED_EVIDENCE_INCOMPLETE")
    state_prohibitions = _scope_set(state["prohibited_scope"])
    semantic_issues = validate_resume_semantics(envelope, state)
    if any(item.code == "EG-RESUME-PROHIBITION" for item in semantic_issues):
        failures.append("PROHIBITED_SCOPE_DROPPED")
    allowed_boundaries = _scope_set(requirements.get("allowed_writes", []))
    effective_writes = _scope_set(state["effective_allowed_writes"])
    if not _writes_within_boundaries(effective_writes, allowed_boundaries):
        failures.append("EFFECTIVE_WRITES_BROADENED")
    if any(_scopes_overlap(write, prohibited) for write in effective_writes for prohibited in state_prohibitions):
        failures.append("PROHIBITED_SCOPE_ACCESS")
    blockers = state["active_blockers"]
    gates = state["outstanding_human_gates"]
    required_gates = set(requirements.get("required_human_gates", []))
    clearances = state.get("gate_clearances", [])
    cleared = set(verified_gates or ())
    if envelope.get("contract_revision") != 2 and isinstance(clearances, list):
        for clearance in clearances:
            if not isinstance(clearance, dict):
                continue
            ref = clearance.get("evidence_ref", {})
            if (isinstance(ref, dict)
                    and ref.get("scheme") == "file"
                    and isinstance(ref.get("locator"), str)
                    and isinstance(ref.get("integrity"), str)
                    and ref in (handoff.get("evidence") or [])):
                from pathlib import Path
                from .semantics import canonical_digest
                from ..loader import load_yaml

                try:
                    evidence = load_yaml(Path(ref["locator"]))
                    if (isinstance(evidence, dict)
                            and evidence.get("gate_id") == clearance.get("gate_id")
                            and evidence.get("work_order_id") == envelope.get("work_order_id")
                            and evidence.get("decision") == "APPROVED"
                            and isinstance(evidence.get("approved_by"), str)
                            and evidence["approved_by"]
                            and canonical_digest(evidence) == ref["integrity"]):
                        cleared.add(clearance.get("gate_id"))
                except (OSError, ValueError):
                    pass
    if required_gates - set(gates) - cleared:
        failures.append("HUMAN_GATE_DROPPED_WITHOUT_EVIDENCE")
    if blockers:
        failures.append("ACTIVE_BLOCKERS")
        if state["next_action_kind"] != "RESOLVE_BLOCKERS":
            failures.append("NEXT_ACTION_INCONSISTENT")
    if gates:
        failures.append("OUTSTANDING_HUMAN_GATES")
        if state["next_action_kind"] != "AWAIT_HUMAN":
            failures.append("NEXT_ACTION_INCONSISTENT")
    if not blockers and not gates and state["next_action_kind"] not in {"EXECUTE", "VERIFY"}:
        failures.append("NEXT_ACTION_INCONSISTENT")
    if handoff.get("status") == "blocked":
        failures.append("HANDOFF_BLOCKED")
    return {"status": "FAIL" if failures else "PASS", "reason_codes": sorted(set(failures)) or ["RESUME_VALID"]}


def _scope_set(values: object) -> set[str]:
    if not isinstance(values, list):
        raise ValueError("Resume scope state must be a list")
    normalized = set()
    for value in values:
        normalized.add(normalize_scope(value).casefold())
    return normalized


def _scopes_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _writes_within_boundaries(writes: set[str], boundaries: set[str]) -> bool:
    if not boundaries:
        return not writes
    return all(any(write == boundary or write.startswith(boundary + "/") for boundary in boundaries) for write in writes)
