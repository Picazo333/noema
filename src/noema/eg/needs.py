"""Canonical, derived execution dependencies.

This is deliberately an internal value object: it makes routing policy aware of
what is mandatory without becoming a tool, model, or capability registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import asdict


def _strings(value: object) -> frozenset[str]:
    if not isinstance(value, (list, tuple, set)):
        return frozenset()
    return frozenset(str(item) for item in value if isinstance(item, (str, int)) and str(item))


@dataclass(frozen=True)
class ExecutionNeeds:
    capability_requirements: frozenset[str]
    resolution_required: bool
    tool_capabilities: frozenset[str]
    required_resources: frozenset[str]
    required_interfaces: frozenset[str]
    executor_required: bool
    model_required: bool
    write_targets: frozenset[str]
    external_effect_required: bool
    independent_review_required: bool

    def to_dict(self) -> dict:
        return {key: sorted(value) if isinstance(value, frozenset) else value
                for key, value in asdict(self).items()}

    @property
    def external_required(self) -> bool:
        """Whether the planned path needs an external dependency to proceed."""
        return any((
            self.resolution_required,
            bool(self.tool_capabilities),
            bool(self.required_resources),
            bool(self.required_interfaces),
            self.executor_required,
            self.model_required,
            self.external_effect_required,
        ))


def derive_execution_needs(work_order: dict, metadata: dict | None = None) -> ExecutionNeeds:
    """Derive mandatory dependencies once, before disposition is selected."""
    metadata = metadata or {}
    tool = metadata.get("tool_requirements", {})
    executor = metadata.get("executor_requirements", {})
    model = metadata.get("model_requirements", {})
    capability_requirements = frozenset(
        str(item.get("id"))
        for item in work_order.get("capability_requirements", [])
        if isinstance(item, dict) and item.get("id")
    )
    interfaces = set(_strings(metadata.get("required_interfaces", [])))
    interfaces.update(_strings(tool.get("interfaces", []) if isinstance(tool, dict) else []))
    interfaces.update(_strings(executor.get("interfaces", []) if isinstance(executor, dict) else []))
    interfaces.update(_strings(model.get("interfaces", []) if isinstance(model, dict) else []))
    return ExecutionNeeds(
        capability_requirements=capability_requirements,
        resolution_required=bool(capability_requirements or metadata.get("resolver_required")),
        tool_capabilities=_strings(tool.get("capabilities", []) if isinstance(tool, dict) else []),
        required_resources=_strings(metadata.get("required_resources", [])),
        required_interfaces=frozenset(interfaces),
        executor_required=bool(executor),
        model_required=bool(model),
        write_targets=_strings(work_order.get("allowed_writes", [])),
        external_effect_required=bool(metadata.get("requires_external")),
        independent_review_required=bool(metadata.get("independent_review_required")),
    )
