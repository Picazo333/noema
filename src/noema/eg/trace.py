"""Explicit, structured execution traces without private payload persistence."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from uuid import uuid4

from .context_plan import ReadSet
from .bindings import envelope_digest, material_digest, read_subject
from .evidence import VerificationContext, verify_assertion
from .enums import MetricStatus
from .semantics import raise_for_issues, sensitive_ref, validate_envelope_semantics, validate_trace_semantics


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
    elif not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"Metric `{status}` requires a finite numeric value")
    if status == MetricStatus.ESTIMATED.value and methodology_ref is None:
        raise ValueError("ESTIMATED metrics require methodology_ref")
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
    if sensitive_ref(ref):
        raise ValueError(f"{label} contains a credential-like locator")
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
    defaults = {}
    if "tool_events" in actual:
        defaults["tool_calls"] = len(
            [event for event in tool_events if event.get("action") == "CALL"]
        )
        defaults["suppressed_calls"] = len(
            [event for event in tool_events if event.get("action") == "SOFT_SUPPRESS"]
        )
    if "retries" in actual:
        defaults["retries"] = _observed_count(actual, "retries")
    if "rework_cycles" in actual:
        defaults["rework"] = _observed_count(actual, "rework_cycles")
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
    verification_context: VerificationContext | None = None,
) -> dict:
    """Create a trace from explicit observations, never raw tool payloads."""
    raise_for_issues(validate_envelope_semantics(envelope))
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
    revision2 = envelope.get("contract_revision") == 2
    if revision2 and envelope_ref != {"scheme": "memory", "locator": envelope["execution_id"]}:
        raise ValueError("R5 trace envelope reference does not match the selected envelope")
    if actual.get("outcome", "UNKNOWN" if revision2 else "SUCCESS") not in {
        "SUCCESS", "PARTIAL", "BLOCKED", "FAILED", "ABORTED", "NO_ACTION", "UNKNOWN"
    }:
        raise ValueError("Unknown execution outcome")
    for key in ("executor", "model"):
        if actual.get(key) is not None and not isinstance(actual.get(key), str):
            raise ValueError(f"{key} must be a string or null")
    read_set = ReadSet()
    context_events = []
    context_refs = []
    read_bindings = []
    for index, read in enumerate(raw_reads):
        ref = _storage_ref(read.get("ref"), "context read ref")
        verified_identity = False
        if revision2 and verification_context is not None and "integrity" in ref:
            subject = read_subject(envelope, index, ref)
            checked = verify_assertion(
                verification_context, f"read:{index}", subject,
                "HISTORICAL_READ_IDENTITY", "project:" + envelope["project_id"])
            if checked.state == "VERIFIED" and checked.source_ref and checked.source_digest:
                verified_identity = True
                read_bindings.append({"event_index": index,
                                      "subject_fingerprint": subject,
                                      "source_ref": checked.source_ref,
                                      "source_digest": checked.source_digest})
        # A claimed hash alone cannot establish a historical observation.
        identity_ref = ({key: value for key, value in ref.items() if key != "integrity"}
                        if revision2 and not verified_identity else ref)
        result = read_set.record(identity_ref, read.get("freshness"), low_signal=bool(read.get("low_signal")))
        context_events.append({
            "ref": ref,
            "result": result["reason_code"],
            "identity_kind": result["identity_kind"],
            "identity_fingerprint": result["identity_fingerprint"],
        })
        if result["read"]:
            context_refs.append(ref)
    started_at = started_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    trace = {
        "contract_version": "execution-trace/v1",
        "trace_id": f"trace-{uuid4().hex}",
        "execution_id": envelope["execution_id"],
        "envelope_ref": envelope_ref,
        "project_id": envelope["project_id"],
        "started_at": started_at,
        "finished_at": finished_at or started_at,
        "outcome": actual.get("outcome", "UNKNOWN" if revision2 else "SUCCESS"),
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
        "retries": _observed_count(actual, "retries"),
        "rework_cycles": _observed_count(actual, "rework_cycles"),
    }
    if revision2:
        trace.update({
            "contract_revision": 2,
            "work_order_id": envelope["work_order_id"],
            "envelope_digest": envelope_digest(envelope),
            "material_digest": material_digest(envelope),
            "read_identity_bindings": read_bindings,
            "observation_coverage": {
                "executor": ("OBSERVED" if actual.get("executor") else "UNVERIFIED"
                             if envelope["intent"]["planned_executor"] else "NOT_REQUIRED"),
                "model": ("OBSERVED" if actual.get("model") else "UNVERIFIED"
                          if envelope["intent"]["planned_model"] else "NOT_REQUIRED"),
                "tools": ("OBSERVED" if "tool_events" in actual else "UNVERIFIED"
                          if envelope["intent"]["planned_tools"] else "NOT_REQUIRED"),
                "topology": ("OBSERVED" if "role_bindings" in actual else "UNVERIFIED"
                             if envelope["topology"]["mode"] == "PARALLEL_ISOLATED"
                             else "NOT_REQUIRED"),
                "historical_reads": "OBSERVED" if "context_reads" in actual else "UNVERIFIED",
            },
        })
    raise_for_issues(validate_trace_semantics(trace))
    return trace


def _observed_count(actual: dict, key: str) -> int | None:
    if key not in actual:
        return None
    value = actual[key]
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{key} must be a non-negative observed integer")
    return value
