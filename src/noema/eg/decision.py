"""Cheap execution-disposition decision, evaluated before expensive resolution."""

from __future__ import annotations

from .enums import ControlDecision, Disposition


def decide_disposition(
    control: str,
    *,
    already_complete: bool = False,
    needs_resolution: bool = False,
    needs_topology: bool = False,
    context_simple: bool = True,
    required_evidence_available: bool = True,
) -> dict:
    if already_complete:
        return {"disposition": Disposition.NO_ACTION.value, "reason_codes": ["NO_MATERIAL_ACTION"]}
    if control == ControlDecision.DENY.value:
        return {"disposition": Disposition.BLOCKED.value, "reason_codes": ["CONTROL_DENY"]}
    if control == ControlDecision.ROUTE_ELSEWHERE.value:
        return {"disposition": Disposition.ROUTE_ELSEWHERE.value, "reason_codes": ["FOREIGN_AUTHORITY"]}
    if control == ControlDecision.DEFER.value:
        return {"disposition": Disposition.DEFER.value, "reason_codes": ["CONTROL_DEFER"]}
    if control == ControlDecision.REQUIRE_HUMAN.value:
        return {"disposition": Disposition.DEFER.value, "reason_codes": ["HUMAN_APPROVAL_REQUIRED"]}
    if not required_evidence_available:
        return {"disposition": Disposition.BLOCKED.value, "reason_codes": ["REQUIRED_EVIDENCE_UNAVAILABLE"]}
    if not needs_resolution and not needs_topology and context_simple:
        return {"disposition": Disposition.DIRECT_EXECUTION.value, "reason_codes": ["DIRECT_BOUNDED"]}
    return {"disposition": Disposition.ROUTED.value, "reason_codes": ["ROUTING_MATERIAL"]}
