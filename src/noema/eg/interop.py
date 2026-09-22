"""Opaque external resolver-receipt validation."""

from __future__ import annotations

from datetime import datetime


_STATUSES = {"RESOLVED", "PARTIAL", "UNRESOLVED", "NOT_REQUIRED", "BLOCKED"}


def validate_resolver_receipt(receipt: dict) -> dict:
    if not isinstance(receipt, dict):
        raise ValueError("Resolver receipt must be an object")
    if not isinstance(receipt.get("resolver"), str) or not receipt["resolver"]:
        raise ValueError("Resolver receipt requires resolver")
    if receipt.get("status") not in _STATUSES:
        raise ValueError("Resolver receipt has unknown status")
    result_ref = receipt.get("result_ref") or receipt.get("resolution_ref")
    if result_ref is not None and (not isinstance(result_ref, dict) or "scheme" not in result_ref or "locator" not in result_ref):
        raise ValueError("Resolver result_ref must be a StorageRef")
    observed = receipt.get("observed_at")
    if observed:
        datetime.fromisoformat(observed.replace("Z", "+00:00"))
    return {
        "resolver": receipt["resolver"],
        "status": receipt["status"],
        "result_ref": result_ref,
        "integrity": receipt.get("integrity"),
        "observed_at": observed,
    }
