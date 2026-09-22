"""Generic topology constraints, not agent/process orchestration."""

from __future__ import annotations

import posixpath

from .enums import TopologyMode


def _normalize_scope(scope: object) -> str:
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("PARALLEL_ISOLATED requires non-empty write scopes")
    value = scope.replace("\\", "/").strip()
    if value.startswith("/") or ".." in value.split("/") or any(char in value for char in "*?["):
        raise ValueError("PARALLEL_ISOLATED write scopes must be local concrete paths")
    normalized = posixpath.normpath(value).lstrip("./")
    if normalized in {"", "."}:
        raise ValueError("PARALLEL_ISOLATED requires non-empty write scopes")
    return normalized


def _overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


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
        return {
            "mode": TopologyMode.PARALLEL_ISOLATED.value,
            "max_parallelism": 2,
            "role_bindings": metadata.get("role_bindings", []),
            "write_scopes": scopes,
        }
    return {
        "mode": TopologyMode.SINGLE.value,
        "max_parallelism": 1,
        "role_bindings": metadata.get("role_bindings", []),
    }
