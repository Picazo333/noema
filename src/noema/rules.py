from __future__ import annotations

from pathlib import Path
from .loader import load_yaml


def load_rules(protocol_root: Path) -> list[dict]:
    data = load_yaml(protocol_root / "rules/core.yaml") or {}
    return list(data.get("rules", []))
