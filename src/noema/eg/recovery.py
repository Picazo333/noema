"""Resume verification over WorkOrder/Handoff authorities and observed state."""

from __future__ import annotations

import posixpath

from .semantics import raise_for_issues, validate_envelope_semantics, validate_resume_semantics


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
    if handoff_ref != envelope.get("work_order_ref"):
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
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Resume scopes must be non-empty strings")
        candidate = posixpath.normpath(value.replace("\\", "/").strip())
        if candidate.startswith("/") or candidate == "." or ".." in candidate.split("/"):
            raise ValueError("Resume scopes must be project-relative")
        normalized.add(candidate.casefold())
    return normalized


def _scopes_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _writes_within_boundaries(writes: set[str], boundaries: set[str]) -> bool:
    if not boundaries:
        return not writes
    return all(any(write == boundary or write.startswith(boundary + "/") for boundary in boundaries) for write in writes)
