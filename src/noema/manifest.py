from __future__ import annotations

from pathlib import Path
import re
from .loader import load_yaml
from .refs import safe_project_path
from .schemas import validation_errors


def load_manifest(root: Path):
    return load_yaml(root / "noema.project.yaml")


def validate_manifest(root: Path, protocol_root: Path):
    data = load_manifest(root)
    return data, validation_errors("project-manifest", data, protocol_root)


_STATE_SCOPE = re.compile(r"state\.[a-z0-9][a-z0-9._-]*\Z")


def state_scopes(manifest: dict) -> tuple[str, ...]:
    """Enumerate only canonical current-state cursors from the manifest."""
    sources = manifest.get("sources_of_truth", {})
    if not isinstance(sources, dict):
        raise ValueError("sources_of_truth must be an object")
    scopes = []
    for name in sources:
        if name.casefold() == "state" or name.casefold().startswith("state."):
            if not _STATE_SCOPE.fullmatch(name):
                raise ValueError("Invalid state scope name")
            scopes.append(name.removeprefix("state."))
    return tuple(sorted(scopes))


def resolve_state_scope(root: Path, manifest: dict, scope: str) -> Path:
    """Resolve a repo-owned state cursor without interpreting its domain facts."""
    name = "state." + scope
    if not _STATE_SCOPE.fullmatch(name):
        raise ValueError("Invalid state scope name")
    ref = manifest.get("sources_of_truth", {}).get(name)
    if not isinstance(ref, dict) or ref.get("scheme") != "repo":
        raise ValueError("State scope must name a project-local repo reference")
    locator = ref.get("locator")
    if not isinstance(locator, str) or not locator:
        raise ValueError("State scope locator is missing")
    return safe_project_path(root, locator)
