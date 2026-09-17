from __future__ import annotations

from pathlib import Path
from .loader import load_yaml
from .schemas import validation_errors


def load_manifest(root: Path):
    return load_yaml(root / "noema.project.yaml")


def validate_manifest(root: Path, protocol_root: Path):
    data = load_manifest(root)
    return data, validation_errors("project-manifest", data, protocol_root)
