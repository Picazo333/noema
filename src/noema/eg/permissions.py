"""Conservative control evaluation over independent execution axes."""

from __future__ import annotations

from .enums import ActionEffect, AuthorityScope, ControlDecision, DataSensitivity


_MATERIAL = {
    ActionEffect.WRITE_DESTRUCTIVE,
    ActionEffect.CANONICAL_MUTATION,
    ActionEffect.EXTERNAL_COMMITMENT,
    ActionEffect.PUBLICATION,
}


def evaluate_control(
    action_effect: ActionEffect,
    data_sensitivity: DataSensitivity,
    authority_scope: AuthorityScope,
    work_order: dict,
    host_caps: dict | None = None,
    policy: dict | None = None,
) -> dict:
    """Return a reason-coded control decision; untrusted input cannot widen it."""
    host_caps = host_caps or {}
    forbidden = set(work_order.get("forbidden_effects", []))
    if action_effect.value in forbidden:
        return {"control": ControlDecision.DENY.value, "reason_codes": ["FORBIDDEN_EFFECT"]}
    if data_sensitivity is DataSensitivity.SECRET:
        return {"control": ControlDecision.DENY.value, "reason_codes": ["SECRET_DURABLE_EXPOSURE"]}
    if authority_scope is AuthorityScope.FOREIGN and action_effect is not ActionEffect.READ:
        return {"control": ControlDecision.ROUTE_ELSEWHERE.value, "reason_codes": ["FOREIGN_AUTHORITY"]}
    if (data_sensitivity is DataSensitivity.UNKNOWN or authority_scope is AuthorityScope.UNKNOWN) and action_effect in _MATERIAL:
        return {"control": ControlDecision.DEFER.value, "reason_codes": ["UNKNOWN_MATERIAL_STATE"]}
    if work_order.get("human_gates"):
        return {"control": ControlDecision.REQUIRE_HUMAN.value,
                "reason_codes": ["EXPLICIT_HUMAN_GATE"]}
    if action_effect in _MATERIAL:
        return {"control": ControlDecision.REQUIRE_HUMAN.value, "reason_codes": ["MATERIAL_EFFECT_HUMAN_GATE"]}
    if action_effect is ActionEffect.WRITE_REVERSIBLE:
        can_scope = host_caps.get("repo_write_reversible") or host_caps.get("can_enforce_write_scope")
        if work_order.get("allowed_writes") and can_scope and authority_scope is AuthorityScope.LOCAL_PROJECT:
            return {"control": ControlDecision.ALLOW_SCOPED.value, "reason_codes": ["SCOPED_REVERSIBLE_WRITE"]}
        return {"control": ControlDecision.DEFER.value, "reason_codes": ["WRITE_SCOPE_UNENFORCEABLE"]}
    return {"control": ControlDecision.ALLOW.value, "reason_codes": ["LOW_EFFECT_ALLOWED"]}
