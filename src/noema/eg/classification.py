"""Inspectable, deterministic classification functions."""

from __future__ import annotations

from .enums import ActionEffect, AuthorityScope, DataSensitivity, Deliberation


def classify_deliberation(work_order: dict, task_metadata: dict | None = None) -> Deliberation:
    metadata = task_metadata or {}
    if metadata.get("deliberation") in Deliberation._value2member_map_:
        return Deliberation(metadata["deliberation"])
    objective = work_order.get("objective", "").lower()
    deep_terms = ("architecture", "research", "cross-repo", "novel", "migration")
    standard_terms = ("multi", "investigate", "refactor", "evaluate", "recover")
    if metadata.get("architecture_impact") or metadata.get("high_uncertainty") or any(
        term in objective for term in deep_terms
    ):
        return Deliberation.DEEP
    if metadata.get("dependency_depth", 0) > 1 or any(term in objective for term in standard_terms):
        return Deliberation.STANDARD
    return Deliberation.MINIMAL


def classify_action_effect(work_order: dict, requested_action: str | None = None) -> ActionEffect:
    action = (requested_action or work_order.get("requested_action") or "").upper()
    if action in ActionEffect._value2member_map_:
        return ActionEffect(action)
    objective = work_order.get("objective", "").lower()
    if any(term in objective for term in ("publish", "release publicly")):
        return ActionEffect.PUBLICATION
    if any(term in objective for term in ("merge", "canonical", "main branch")):
        return ActionEffect.CANONICAL_MUTATION
    if any(term in objective for term in ("delete", "destroy", "irreversible")):
        return ActionEffect.WRITE_DESTRUCTIVE
    if work_order.get("allowed_writes"):
        return ActionEffect.WRITE_REVERSIBLE
    if any(term in objective for term in ("read", "inspect", "audit", "review")):
        return ActionEffect.READ
    return ActionEffect.REASON


def classify_data_sensitivity(inputs: list | None, explicit_metadata: dict | None = None) -> DataSensitivity:
    metadata = explicit_metadata or {}
    explicit = metadata.get("data_sensitivity")
    if explicit in DataSensitivity._value2member_map_:
        return DataSensitivity(explicit)
    for item in inputs or []:
        locator = str(item.get("locator", "") if isinstance(item, dict) else item).lower()
        if any(term in locator for term in ("secret", "credential", "password", "token", ".env")):
            return DataSensitivity.SECRET
    return DataSensitivity.INTERNAL if inputs is not None else DataSensitivity.UNKNOWN


def classify_authority_scope(project_manifest: dict, target_ref: object | None) -> AuthorityScope:
    if target_ref is None:
        return AuthorityScope.LOCAL_PROJECT
    locator = str(target_ref.get("locator", "") if isinstance(target_ref, dict) else target_ref)
    if locator.startswith("repo://") or locator.startswith("repo:"):
        return AuthorityScope.LOCAL_PROJECT
    if locator.startswith("project:"):
        targets = {relation.get("target") for relation in project_manifest.get("relations", [])}
        return AuthorityScope.DECLARED_RELATION if locator in targets else AuthorityScope.FOREIGN
    return AuthorityScope.LOCAL_PROJECT if not locator else AuthorityScope.UNKNOWN
