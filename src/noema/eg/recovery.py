"""Resume checks against existing WorkOrder/Handoff/ref authorities."""

from __future__ import annotations

def recovery_requirements(work_order: dict, baseline_sha: str | None, policy: dict | None = None) -> dict:
    return {
        "retry_cap": int((policy or {}).get("retry_cap", 1)),
        "idempotency_key": None,
        "checkpoint_ref": None,
        "rollback_ref": None,
        "resume_check_required": bool(baseline_sha),
        "expected_sha": baseline_sha,
    }


def resume_check(envelope: dict, handoff: dict, current_sha: str | None = None) -> dict:
    failures = []
    if handoff.get("work_order_ref") != envelope.get("work_order_ref"):
        failures.append("WORK_ORDER_MISMATCH")
    expected = envelope.get("recovery", {}).get("expected_sha")
    if expected and current_sha and expected != current_sha:
        failures.append("STALE_SHA")
    if handoff.get("status") == "blocked":
        failures.append("HANDOFF_BLOCKED")
    return {"status": "FAIL" if failures else "PASS", "reason_codes": failures or ["RESUME_VALID"]}
