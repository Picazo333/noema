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
