"""Generic topology constraints, not agent/process orchestration."""

from __future__ import annotations

from .enums import TopologyMode


def derive_topology(metadata: dict | None = None, evaluation: dict | None = None) -> dict:
    metadata = metadata or {}
    evaluation = evaluation or {}
    if evaluation.get("independent_review_required"):
        return {"mode": TopologyMode.AUDITED_SINGLE.value, "max_parallelism": 1, "role_bindings": metadata.get("role_bindings", [])}
    if metadata.get("parallel_isolated"):
        scopes = metadata.get("write_scopes", [])
        if len(scopes) != len(set(scopes)) or not metadata.get("serialized_publication"):
            raise ValueError("PARALLEL_ISOLATED requires disjoint scopes and serialized publication")
        return {"mode": TopologyMode.PARALLEL_ISOLATED.value, "max_parallelism": 2, "role_bindings": metadata.get("role_bindings", [])}
    return {"mode": TopologyMode.SINGLE.value, "max_parallelism": 1, "role_bindings": metadata.get("role_bindings", [])}
