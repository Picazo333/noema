"""Explicit, structured execution traces without private payload persistence."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4

from .context_plan import ReadSet
from .enums import MetricStatus


_METRIC_NAMES = (
    "context_units", "tool_calls", "suppressed_calls", "retries", "rework",
    "human_interventions", "wall_time_ms", "provider_tokens", "monetary_cost",
)
_SAFE_TOKEN_KEYS = {"provider_tokens"}
_SENSITIVE_KEYS = {
    "authorization", "authentication", "authheader", "cookie", "setcookie",
    "apikey", "xapikey", "accesstoken", "refreshtoken", "idtoken", "bearertoken",
    "sessiontoken", "clientsecret", "password", "credential", "privatekey", "secretkey",
    "accesskey", "clientkey",
}
_PAYLOAD_KEYS = {"payload", "headers", "response", "request", "body"}
_ACTUAL_KEYS = {
    "envelope_ref", "outcome", "role_bindings", "executor", "model",
    "context_reads", "tool_events", "eval_refs", "artifact_refs", "permission_events",
    "metrics", "retries", "rework_cycles",
}
_TOOL_EVENT_KEYS = {"candidate", "action", "result", "reason_codes", "evidence_refs", "occurred_at"}
_CONTEXT_READ_KEYS = {"ref", "freshness", "low_signal"}
_PERMISSION_EVENT_KEYS = {"action", "decision", "reason_codes", "occurred_at"}
_ROLE_BINDING_KEYS = {"role_id", "executor_id", "model_id", "provenance_refs"}
_STORAGE_REF_KEYS = {"scheme", "locator", "version", "integrity"}
_METRIC_KEYS = {"status", "value", "methodology_ref"}


def _normalized_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def _is_sensitive_key(key: object) -> bool:
    raw = str(key).lower()
    normalized = _normalized_key(key)
    if raw in _SAFE_TOKEN_KEYS:
        return False
    return normalized in _SENSITIVE_KEYS or normalized.endswith(
        ("token", "secret", "password", "credential", "key", "privatekey")
    )


def _contains_sensitive(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            _is_sensitive_key(key)
            or _normalized_key(key) in _PAYLOAD_KEYS
            or _contains_sensitive(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_sensitive(item) for item in value)
    return False


def _require_known_mapping(value: object, allowed: set[str], label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{label} has unsupported fields: {sorted(unknown)}")
    if _contains_sensitive(value):
        raise ValueError(f"{label} contains secret-like data or an opaque payload")
    return value


def metric(
    value: object = None,
    status: str | None = None,
    methodology_ref: object = None,
) -> dict:
    if status is None:
        status = MetricStatus.UNAVAILABLE.value if value is None else MetricStatus.MEASURED.value
    if status not in {item.value for item in MetricStatus}:
        raise ValueError(f"Unknown metric status: {status}")
    if status == MetricStatus.UNAVAILABLE.value:
        value = None
    elif value is None:
        raise ValueError(f"Metric `{status}` requires a value")
    if status == MetricStatus.ESTIMATED_LABELED.value and methodology_ref is None:
        raise ValueError("ESTIMATED_LABELED metrics require methodology_ref")
    result = {"status": status, "value": value}
    if methodology_ref is not None:
        result["methodology_ref"] = _storage_ref(methodology_ref, "metric methodology_ref")
    return result


def _structured_events(actual: dict, key: str, allowed: set[str]) -> list[dict]:
    events = actual.get(key, [])
    if not isinstance(events, list):
        raise ValueError(f"{key} must be a list")
    return [_require_known_mapping(event, allowed, key) for event in events]


def _storage_ref(value: object, label: str) -> dict:
    ref = _require_known_mapping(value, _STORAGE_REF_KEYS, label)
    if not isinstance(ref.get("scheme"), str) or not isinstance(ref.get("locator"), str):
        raise ValueError(f"{label} requires a scheme and locator")
    return ref


def _storage_refs(value: object, label: str) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    return [_storage_ref(ref, label) for ref in value]


def _role_bindings(value: object) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("role_bindings must be a list")
    bindings = []
    for binding in value:
        item = _require_known_mapping(binding, _ROLE_BINDING_KEYS, "role_bindings")
        if not isinstance(item.get("role_id"), str):
            raise ValueError("role_bindings requires role_id")
        if "provenance_refs" in item:
            _storage_refs(item["provenance_refs"], "role binding provenance_refs")
        bindings.append(item)
    return bindings


def _typed_event_lists(
    tool_events: list[dict], permission_events: list[dict], raw_reads: list[dict]
) -> None:
    for event in tool_events:
        if (
            not isinstance(event.get("candidate"), str)
            or event.get("action") not in {"CALL", "SOFT_SUPPRESS", "HARD_DENY", "DEFER"}
            or event.get("result") not in {"SUCCESS", "FAILED", "UNAVAILABLE", "NOT_CALLED"}
            or not isinstance(event.get("reason_codes"), list)
        ):
            raise ValueError("tool_events does not match the persistable event contract")
        _storage_refs(event.get("evidence_refs"), "tool event evidence_refs")
    for event in permission_events:
        if (
            not isinstance(event.get("action"), str)
            or event.get("decision") not in {
                "ALLOW", "ALLOW_SCOPED", "REQUIRE_HUMAN", "DENY", "DEFER", "ROUTE_ELSEWHERE"
            }
            or not isinstance(event.get("reason_codes"), list)
        ):
            raise ValueError("permission_events does not match the persistable event contract")
    for read in raw_reads:
        if "freshness" in read and not isinstance(read["freshness"], (str, type(None))):
            raise ValueError("context read freshness must be a string or null")


def _trace_metrics(actual: dict, tool_events: list[dict]) -> dict:
    supplied = actual.get("metrics", {})
    if not isinstance(supplied, dict):
        raise ValueError("metrics must be an object")
    if set(supplied) - set(_METRIC_NAMES):
        raise ValueError("metrics contains unsupported metric names")
    defaults = {
        "tool_calls": len([event for event in tool_events if event.get("action") == "CALL"]),
        "suppressed_calls": len(
            [event for event in tool_events if event.get("action") == "SOFT_SUPPRESS"]
        ),
        "retries": int(actual.get("retries", 0)),
        "rework": int(actual.get("rework_cycles", 0)),
    }
    result = {}
    for name in _METRIC_NAMES:
        supplied_value = supplied.get(name)
        if isinstance(supplied_value, dict):
            item = _require_known_mapping(supplied_value, _METRIC_KEYS, f"metric {name}")
            result[name] = metric(
                item.get("value"), item.get("status"), item.get("methodology_ref")
            )
        elif name in supplied:
            result[name] = metric(supplied_value)
        elif name in defaults:
            result[name] = metric(defaults[name])
        else:
            result[name] = metric()
    return result


def create_trace(
    envelope: dict,
    actual: dict,
    *,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> dict:
    """Create a trace from explicit observations, never raw tool payloads."""
    _require_known_mapping(actual, _ACTUAL_KEYS, "actual execution")
    tool_events = _structured_events(actual, "tool_events", _TOOL_EVENT_KEYS)
    permission_events = _structured_events(actual, "permission_events", _PERMISSION_EVENT_KEYS)
    raw_reads = _structured_events(actual, "context_reads", _CONTEXT_READ_KEYS)
    _typed_event_lists(tool_events, permission_events, raw_reads)
    role_bindings = _role_bindings(actual.get("role_bindings", []))
    eval_refs = _storage_refs(actual.get("eval_refs", []), "eval_refs")
    artifact_refs = _storage_refs(actual.get("artifact_refs", []), "artifact_refs")
    envelope_ref = _storage_ref(
        actual.get("envelope_ref", {"scheme": "memory", "locator": envelope["execution_id"]}),
        "envelope_ref",
    )
    if actual.get("outcome", "SUCCESS") not in {
        "SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "ABORTED", "NO_ACTION"
    }:
        raise ValueError("Unknown execution outcome")
    for key in ("executor", "model"):
        if actual.get(key) is not None and not isinstance(actual.get(key), str):
            raise ValueError(f"{key} must be a string or null")
    read_set = ReadSet()
    context_events = []
    context_refs = []
    for read in raw_reads:
        ref = _storage_ref(read.get("ref"), "context read ref")
        result = read_set.record(ref, read.get("freshness"), low_signal=bool(read.get("low_signal")))
        context_events.append({"ref": ref, "result": result["reason_code"]})
        if result["read"]:
            context_refs.append(ref)
    started_at = started_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "trace_id": f"trace-{uuid4().hex}",
        "execution_id": envelope["execution_id"],
        "envelope_ref": envelope_ref,
        "project_id": envelope["project_id"],
        "started_at": started_at,
        "finished_at": finished_at or started_at,
        "outcome": actual.get("outcome", "SUCCESS"),
        "actual": {
            "role_bindings": role_bindings,
            "executor": actual.get("executor"),
            "model": actual.get("model"),
            "context_refs": context_refs,
            "context_events": context_events,
            "tool_events": tool_events,
            "eval_refs": eval_refs,
            "artifact_refs": artifact_refs,
            "permission_events": permission_events,
        },
        "metrics": _trace_metrics(actual, tool_events),
        "retries": int(actual.get("retries", 0)),
        "rework_cycles": int(actual.get("rework_cycles", 0)),
    }
