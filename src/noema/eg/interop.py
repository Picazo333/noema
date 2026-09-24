"""Opaque external resolver-receipt validation."""

from __future__ import annotations

from datetime import datetime

from .semantics import raise_for_issues, validate_resolver_receipt_semantics


_STATUSES = {"RESOLVED", "PARTIAL", "UNRESOLVED", "NOT_REQUIRED", "BLOCKED"}


def validate_resolver_receipt(receipt: dict, *, revision: int = 1) -> dict:
    if not isinstance(receipt, dict):
        raise ValueError("Resolver receipt must be an object")
    if not isinstance(receipt.get("resolver"), str) or not receipt["resolver"]:
        raise ValueError("Resolver receipt requires resolver")
    if receipt.get("status") not in _STATUSES:
        raise ValueError("Resolver receipt has unknown status")
    resolution_ref = receipt.get("resolution_ref")
    if resolution_ref is not None and (not isinstance(resolution_ref, dict) or "scheme" not in resolution_ref or "locator" not in resolution_ref):
        raise ValueError("Resolver resolution_ref must be a StorageRef")
    observed = receipt.get("observed_at")
    if observed:
        datetime.fromisoformat(observed.replace("Z", "+00:00"))
    normalized = {
        "resolver": receipt["resolver"],
        "status": receipt["status"],
        "resolution_ref": resolution_ref,
        "unresolved_capabilities": list(receipt.get("unresolved_capabilities", [])),
        "integrity": receipt.get("integrity"),
        "observed_at": observed,
    }
    if revision == 2:
        normalized["satisfied_capabilities"] = list(receipt.get("satisfied_capabilities", []))
    raise_for_issues(validate_resolver_receipt_semantics(normalized))
    return normalized
