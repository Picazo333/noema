from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedRef:
    scheme: str
    locator: str


def parse_ref(value: str) -> ParsedRef:
    if "://" not in value:
        raise ValueError(f"Invalid reference: {value}")
    scheme, locator = value.split("://", 1)
    if not scheme or not locator:
        raise ValueError(f"Invalid reference: {value}")
    return ParsedRef(scheme=scheme, locator=locator)


def repo_ref_exists(project_root: Path, value: str) -> bool:
    ref = parse_ref(value)
    if ref.scheme != "repo":
        return True
    target = (project_root / ref.locator).resolve()
    try:
        target.relative_to(project_root.resolve())
    except ValueError:
        return False
    return target.exists()


def safe_project_path(project_root: Path, relative: str) -> Path:
    target = (project_root / relative).resolve()
    try:
        target.relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(f"Path escapes project root: {relative}") from exc
    return target
