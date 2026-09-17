from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from .loader import dump_yaml, load_yaml
from .schemas import schema_root, validation_errors
from .refs import safe_project_path


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value[:48] or "finding"


def new_candidate(root: Path, finding: str, routes: list[str] | None = None, confidence: str = "medium", confidentiality: str = "INTERNAL", scope: str = "project") -> Path:
    root = root.resolve()
    manifest = load_yaml(root / "noema.project.yaml")
    now = datetime.now(timezone.utc)
    hid = f"harvest-{now.strftime('%Y%m%d%H%M%S')}-{_slug(finding)}"
    data = {
        "harvest_id": hid,
        "project_id": manifest["project"]["id"],
        "finding": finding,
        "evidence_refs": [],
        "scope": scope,
        "confidence": confidence,
        "routes": routes or [],
        "confidentiality": confidentiality,
        "status": "CANDIDATE",
    }
    target = safe_project_path(root, f"harvest/{hid}.yaml")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dump_yaml(data), encoding="utf-8")
    return target


def validate_candidate(path: Path, protocol_root: Path | None = None):
    protocol_root = schema_root(protocol_root)
    data = load_yaml(path)
    return validation_errors("harvest-candidate", data, protocol_root)
