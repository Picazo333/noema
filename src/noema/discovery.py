from __future__ import annotations

from pathlib import Path

MANIFEST = "noema.project.yaml"


def discover_root(start: str | Path = ".") -> Path:
    current = Path(start).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / MANIFEST).exists():
            return candidate
    raise FileNotFoundError(f"No {MANIFEST} found from {current} upward")
