"""Derived input provenance for Execution Governance artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..loader import load_yaml
from .semantics import canonical_digest


@dataclass(frozen=True)
class LoadedWorkOrder:
    data: dict
    canonical_source_ref: dict
    source_digest: str


def programmatic_work_order(data: dict) -> LoadedWorkOrder:
    """Give programmatic input a deterministic, content-bound source identity."""
    digest = canonical_digest(data)
    return LoadedWorkOrder(
        data=data,
        canonical_source_ref={
            "scheme": "memory",
            "locator": f"work-order/{data.get('work_order_id', 'unknown')}",
            "integrity": digest,
        },
        source_digest=digest,
    )


def load_work_order(path: Path) -> LoadedWorkOrder:
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ValueError("WorkOrder document must contain an object")
    digest = canonical_digest(data)
    return LoadedWorkOrder(
        data=data,
        canonical_source_ref={"scheme": "file", "locator": str(path.resolve()), "integrity": digest},
        source_digest=digest,
    )
