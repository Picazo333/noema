"""Generic topology constraints, not agent/process orchestration."""

from __future__ import annotations

from .enums import TopologyMode
from .semantics import normalize_scope, raise_for_issues, validate_topology_semantics


def derive_topology(metadata: dict | None = None, evaluation: dict | None = None) -> dict:
    metadata = metadata or {}
    evaluation = evaluation or {}
    if evaluation.get("independent_review_required"):
        return {
            "mode": TopologyMode.AUDITED_SINGLE.value,
            "max_parallelism": 1,
            "role_bindings": metadata.get("role_bindings", []),
        }
    if metadata.get("parallel_isolated"):
        scopes = [normalize_scope(scope) for scope in metadata.get("write_scopes", [])]
        if len(scopes) < 2:
            raise ValueError("PARALLEL_ISOLATED requires at least two disjoint worker scopes")
        if not metadata.get("serialized_publication"):
            raise ValueError("PARALLEL_ISOLATED requires serialized canonical publication")
        bindings = metadata.get("role_bindings", [])
        if not isinstance(bindings, list) or len(bindings) < 2:
            raise ValueError("PARALLEL_ISOLATED requires declared writing worker bindings")
        for binding in bindings:
            if not isinstance(binding, dict) or not binding.get("role_id"):
                raise ValueError("PARALLEL_ISOLATED requires a role_id for every worker")
            declared = binding.get("scope")
            if not isinstance(declared, list) or not declared:
                raise ValueError("PARALLEL_ISOLATED requires non-empty scope for every worker")
        topology = {
            "mode": TopologyMode.PARALLEL_ISOLATED.value,
            "max_parallelism": 2,
            "role_bindings": bindings,
            "write_scopes": scopes,
        }
        raise_for_issues(validate_topology_semantics(topology))
        return topology
    return {
        "mode": TopologyMode.SINGLE.value,
        "max_parallelism": 1,
        "role_bindings": metadata.get("role_bindings", []),
    }
