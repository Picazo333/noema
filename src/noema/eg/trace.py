"""Explicit trace construction. Trace accepts observations, never hidden reasoning."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .enums import MetricStatus

_SENSITIVE_KEYS = {"secret", "token", "password", "credential", "api_key"}


def _contains_sensitive(value: object) -> bool:
    if isinstance(value, dict):
        return any(key.lower() in _SENSITIVE_KEYS or _contains_sensitive(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_sensitive(item) for item in value)
    return False


def metric(value: object = None, status: str | None = None) -> dict:
    if status is None:
        status = MetricStatus.UNAVAILABLE.value if value is None else MetricStatus.OBSERVED.value
    if status == MetricStatus.UNAVAILABLE.value:
        value = None
    return {"status": status, "value": value}


def create_trace(envelope: dict, actual: dict, *, started_at: str | None = None, finished_at: str | None = None) -> dict:
    if _contains_sensitive(actual):
        raise ValueError("Trace must not contain credentials, secrets, or raw tokens")
    started_at = started_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "trace_id": f"trace-{uuid4().hex}",
        "execution_id": envelope["execution_id"],
        "envelope_ref": actual.get("envelope_ref", {"scheme": "memory", "locator": envelope["execution_id"]}),
        "project_id": envelope["project_id"],
        "started_at": started_at,
        "finished_at": finished_at or started_at,
        "outcome": actual.get("outcome", "SUCCESS"),
        "actual": {
            "role_bindings": actual.get("role_bindings", []),
            "executor": actual.get("executor"),
            "model": actual.get("model"),
            "context_refs": actual.get("context_refs", []),
            "tool_events": actual.get("tool_events", []),
            "eval_refs": actual.get("eval_refs", []),
            "artifact_refs": actual.get("artifact_refs", []),
            "permission_events": actual.get("permission_events", []),
        },
        "metrics": {name: metric(value.get("value"), value.get("status")) if isinstance(value, dict) else metric(value) for name, value in actual.get("metrics", {}).items()},
        "retries": int(actual.get("retries", 0)),
        "rework_cycles": int(actual.get("rework_cycles", 0)),
    }
