from __future__ import annotations

from pathlib import Path
from .loader import load_yaml


def claim_catalog(protocol_root: Path) -> dict:
    data = load_yaml(protocol_root / "catalog/quality-claims.yaml") or {}
    return data.get("quality_claims", {})


def project_types(protocol_root: Path) -> set[str]:
    data = load_yaml(protocol_root / "catalog/project-types.yaml") or {}
    return set(data.get("project_types", []))


def traits(protocol_root: Path) -> set[str]:
    data = load_yaml(protocol_root / "catalog/traits.yaml") or {}
    return set(data.get("traits", []))
