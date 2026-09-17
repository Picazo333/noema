from __future__ import annotations

from pathlib import Path
from .refs import parse_ref, safe_project_path


def required_context_refs(manifest: dict, mode: str | None = None) -> list[str]:
    context = manifest.get("context", {})
    selected = mode or context.get("default_mode", "build")
    mode_cfg = context.get("modes", {}).get(selected, {})
    return list(mode_cfg.get("required", []))


def resolve_context_paths(root: Path, manifest: dict, mode: str | None = None) -> list[Path]:
    paths = [safe_project_path(root, manifest["context"]["entrypoint"])]
    for value in required_context_refs(manifest, mode):
        ref = parse_ref(value)
        if ref.scheme == "repo":
            paths.append(safe_project_path(root, ref.locator))
    # stable de-dup preserving order
    seen = set()
    out = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def context_stats(paths: list[Path]) -> dict:
    total_bytes = 0
    total_chars = 0
    total_words = 0
    missing = []
    for path in paths:
        if not path.exists():
            missing.append(str(path))
            continue
        text = path.read_text(encoding="utf-8")
        total_bytes += len(text.encode("utf-8"))
        total_chars += len(text)
        total_words += len(text.split())
    return {
        "files": len(paths),
        "missing": missing,
        "bytes": total_bytes,
        "characters": total_chars,
        "words": total_words,
        "approx_tokens": round(total_chars / 4),
        "approximation": "characters/4 heuristic",
    }
