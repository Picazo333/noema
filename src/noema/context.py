from __future__ import annotations

from pathlib import Path

from .refs import parse_ref, safe_project_path


CONTEXT_METRIC = "Noema Context Units v1 (characters/4)"


def _mode_config(manifest: dict, mode: str | None = None) -> tuple[str, dict]:
    context = manifest.get("context", {})
    selected = mode or context.get("default_mode", "build")
    mode_cfg = context.get("modes", {}).get(selected, {}) or {}
    return selected, mode_cfg


def required_context_refs(manifest: dict, mode: str | None = None) -> list[str]:
    _, mode_cfg = _mode_config(manifest, mode)
    return list(mode_cfg.get("required", []))


def optional_context_refs(manifest: dict, mode: str | None = None) -> list[str]:
    _, mode_cfg = _mode_config(manifest, mode)
    return list(mode_cfg.get("optional", []))


def resolve_context_paths(
    root: Path,
    manifest: dict,
    mode: str | None = None,
    *,
    include_optional: bool = True,
    include_manifest: bool = True,
) -> list[Path]:
    """Resolve project-local context references safely.

    `include_optional=True` is the validation-oriented default so declared optional
    references cannot silently rot. Cold-start measurement must explicitly pass
    `include_optional=False`; optional context is validated but not loaded by default.
    """

    paths = [safe_project_path(root, manifest["context"]["entrypoint"])]
    if include_manifest:
        paths.append(safe_project_path(root, "noema.project.yaml"))

    refs = required_context_refs(manifest, mode)
    if include_optional:
        refs += optional_context_refs(manifest, mode)

    for value in refs:
        ref = parse_ref(value)
        if ref.scheme == "repo":
            paths.append(safe_project_path(root, ref.locator))

    # Stable de-dup preserving declared order.
    seen: set[Path] = set()
    out: list[Path] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out


def context_stats(paths: list[Path]) -> dict:
    total_bytes = 0
    total_chars = 0
    total_words = 0
    missing: list[str] = []
    for path in paths:
        if not path.exists():
            missing.append(str(path))
            continue
        text = path.read_text(encoding="utf-8")
        total_bytes += len(text.encode("utf-8"))
        total_chars += len(text)
        total_words += len(text.split())

    context_units = round(total_chars / 4)
    return {
        "files": len(paths),
        "missing": missing,
        "bytes": total_bytes,
        "characters": total_chars,
        "words": total_words,
        "context_units": context_units,
        # Backward-compatible field name. This is a normalized comparison metric,
        # not provider billing-token accounting.
        "approx_tokens": context_units,
        "approximation": CONTEXT_METRIC,
    }
