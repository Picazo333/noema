"""Generic topology constraints, not agent/process orchestration."""

from __future__ import annotations

import posixpath
import re

from .enums import TopologyMode


def _normalize_scope(scope: object) -> str:
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("PARALLEL_ISOLATED requires non-empty write scopes")
    value = scope.replace("\\", "/").strip()
    if (
        value.startswith(("/", "//"))
        or re.match(r"^[A-Za-z]:", value)
        or ".." in value.split("/")
        or any(char in value for char in "*?[")
    ):
        raise ValueError("PARALLEL_ISOLATED write scopes must be local concrete paths")
    normalized = posixpath.normpath(value)
    if normalized in {"", "."}:
        raise ValueError("PARALLEL_ISOLATED requires non-empty write scopes")
    return normalized


def _overlap(left: str, right: str) -> bool:
    normalized_left = left.casefold()
    normalized_right = right.casefold()
    return (
        normalized_left == normalized_right
        or normalized_left.startswith(normalized_right + "/")
        or normalized_right.startswith(normalized_left + "/")
    )


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
        scopes = [_normalize_scope(scope) for scope in metadata.get("write_scopes", [])]
        if len(scopes) < 2:
            raise ValueError("PARALLEL_ISOLATED requires at least two disjoint worker scopes")
        if any(_overlap(left, right) for index, left in enumerate(scopes) for right in scopes[index + 1 :]):
            raise ValueError("PARALLEL_ISOLATED worker write scopes overlap")
        if not metadata.get("serialized_publication"):
            raise ValueError("PARALLEL_ISOLATED requires serialized canonical publication")
        bindings = metadata.get("role_bindings", [])
        if not isinstance(bindings, list) or len(bindings) < 2:
            raise ValueError("PARALLEL_ISOLATED requires declared writing worker bindings")
        binding_scopes = []
        for binding in bindings:
            if not isinstance(binding, dict) or not binding.get("role_id"):
                raise ValueError("PARALLEL_ISOLATED requires a role_id for every worker")
            declared = binding.get("scope")
            if not isinstance(declared, list) or not declared:
                raise ValueError("PARALLEL_ISOLATED requires non-empty scope for every worker")
            binding_scopes.extend(_normalize_scope(scope) for scope in declared)
        if {scope.casefold() for scope in binding_scopes} != {scope.casefold() for scope in scopes}:
            raise ValueError("PARALLEL_ISOLATED worker scopes must match declared write scopes")
        return {
            "mode": TopologyMode.PARALLEL_ISOLATED.value,
            "max_parallelism": 2,
            "role_bindings": bindings,
            "write_scopes": scopes,
        }
    return {
        "mode": TopologyMode.SINGLE.value,
        "max_parallelism": 1,
        "role_bindings": metadata.get("role_bindings", []),
    }
