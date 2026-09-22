"""Ephemeral runtime-pressure policy. No quota data is stored by this module."""

from __future__ import annotations

from .enums import RuntimePosture, TopologyMode


def classify_runtime_posture(snapshot: dict | None) -> RuntimePosture:
    if not snapshot:
        return RuntimePosture.UNKNOWN
    hint = snapshot.get("posture_hint") or snapshot.get("posture")
    if hint in RuntimePosture._value2member_map_:
        return RuntimePosture(hint)
    signals = snapshot.get("signals", [])
    names = {str(signal.get("name", "")).lower() for signal in signals if isinstance(signal, dict)}
    if "blocked" in names:
        return RuntimePosture.BLOCKED
    if "throttled" in names or snapshot.get("retry_after") is not None:
        return RuntimePosture.THROTTLED
    if "conserve" in names:
        return RuntimePosture.CONSERVE
    return RuntimePosture.NORMAL


def derive_resource_policy(
    posture: RuntimePosture, host_caps: dict | None = None, deliberation: object | None = None,
    topology: object | None = None,
) -> dict:
    values = {
        "posture": posture.value,
        "parallelism_ceiling": 1,
        "optional_external_calls": "NORMAL",
        "dedupe_reads": True,
        "batch_reads_when_safe": bool((host_caps or {}).get("batch_reads")),
        "reason_codes": [],
    }
    if posture is RuntimePosture.CONSERVE:
        values.update(optional_external_calls="CONSERVE", reason_codes=["RUNTIME_PRESSURE_CONSERVE"])
    elif posture is RuntimePosture.THROTTLED:
        values.update(optional_external_calls="DEFER", reason_codes=["PROVIDER_THROTTLED"])
    elif posture is RuntimePosture.BLOCKED:
        values.update(optional_external_calls="DEFER", reason_codes=["PLATFORM_BLOCKED"])
    elif posture is RuntimePosture.UNKNOWN:
        values["reason_codes"] = ["RUNTIME_PRESSURE_UNKNOWN"]
    if topology == TopologyMode.PARALLEL_ISOLATED and posture is RuntimePosture.NORMAL:
        values["parallelism_ceiling"] = 2
    return values


def resource_disposition_constraint(
    posture: RuntimePosture,
    snapshot: dict | None,
    task_metadata: dict | None,
    candidate_snapshot: dict | None,
) -> dict | None:
    """Return a terminal runtime constraint only for a blocked required resource.

    A generic blocked host signal must not stop pure/local work. The caller must
    declare or supply a concrete required resource before EG constrains execution.
    """
    if posture not in {RuntimePosture.BLOCKED, RuntimePosture.THROTTLED}:
        return None
    snapshot = snapshot or {}
    metadata = task_metadata or {}
    candidates = candidate_snapshot or {}
    blocked = {str(value).casefold() for value in snapshot.get("blocked_resources", [])}
    blocked.update(str(value).casefold() for value in snapshot.get("blocked_interfaces", []))
    required = {str(value).casefold() for value in metadata.get("required_resources", [])}
    required.update(
        str(value).casefold()
        for value in metadata.get("tool_requirements", {}).get("interfaces", [])
    )
    required.update(
        str(value).casefold()
        for value in metadata.get("executor_requirements", {}).get("interfaces", [])
    )
    for tool in candidates.get("tools", []):
        if tool.get("required"):
            required.update(str(value).casefold() for value in tool.get("interfaces", []))
            required.add(str(tool.get("id", "")).casefold())
    if metadata.get("requires_external"):
        required.add("external")
    matches = bool(blocked & required) or (
        bool(required) and bool(snapshot.get("block_all_external"))
    )
    if not matches:
        return None
    if posture is RuntimePosture.BLOCKED:
        return {"disposition": "BLOCKED", "reason_code": "REQUIRED_RESOURCE_BLOCKED"}
    return {"disposition": "DEFER", "reason_code": "REQUIRED_RESOURCE_THROTTLED"}
