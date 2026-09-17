from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
from uuid import uuid4

from .loader import dump_yaml, load_yaml
from .refs import parse_ref, repo_ref_exists, safe_project_path
from .schemas import schema_root, validation_errors


def _slug(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value[:48] or "finding"


def _evidence_refs(root: Path, values: list[str]) -> list[dict]:
    refs: list[dict] = []
    for value in values:
        ref = parse_ref(value)
        if ref.scheme == "repo" and not repo_ref_exists(root, value):
            raise ValueError(f"Harvest evidence reference does not exist: {value}")
        refs.append({"scheme": ref.scheme, "locator": ref.locator})
    return refs


def new_candidate(
    root: Path,
    finding: str,
    routes: list[str] | None = None,
    evidence_refs: list[str] | None = None,
    confidence: str = "medium",
    confidentiality: str = "INTERNAL",
    scope: str = "project",
) -> Path:
    root = root.resolve()
    manifest = load_yaml(root / "noema.project.yaml")
    now = datetime.now(timezone.utc)
    suffix = uuid4().hex[:8]
    harvest_id = (
        f"harvest-{now.strftime('%Y%m%d%H%M%S%f')}-{_slug(finding)}-{suffix}"
    )
    data = {
        "harvest_id": harvest_id,
        "project_id": manifest["project"]["id"],
        "finding": finding,
        "evidence_refs": _evidence_refs(root, evidence_refs or []),
        "scope": scope,
        "confidence": confidence,
        "routes": routes or [],
        "confidentiality": confidentiality,
        "status": "CANDIDATE",
    }
    target = safe_project_path(root, f"harvest/{harvest_id}.yaml")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dump_yaml(data), encoding="utf-8")
    return target


def validate_candidate(path: Path, protocol_root: Path | None = None):
    protocol_root = schema_root(protocol_root)
    data = load_yaml(path)
    return validation_errors("harvest-candidate", data, protocol_root)
