"""Derived execution-local load plan built on Noema's existing context resolver."""

from __future__ import annotations

from pathlib import Path

from ..context import context_stats, optional_context_refs, resolve_context_paths
from ..refs import parse_ref, safe_project_path


def _repo_ref(path: Path, root: Path) -> dict:
    return {"scheme": "repo", "locator": path.relative_to(root).as_posix()}


def build_context_plan(root: Path, manifest: dict, work_order: dict, *, recovery_refs: list | None = None) -> dict:
    """Preload only entrypoint/manifest/required/task inputs; leave optional refs warm."""
    root = root.resolve()
    mode = work_order.get("context_mode", manifest["context"].get("default_mode", "build"))
    hot_paths = resolve_context_paths(root, manifest, mode, include_optional=False)
    refs: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def append(ref: dict, tier: str, reason: str) -> None:
        key = (ref["scheme"], ref["locator"])
        if key not in seen:
            seen.add(key)
            refs.append({"ref": ref, "load_tier": tier, "reason_codes": [reason]})

    for path in hot_paths:
        append(_repo_ref(path, root), "HOT", "REQUIRED_CONTEXT")
    for item in work_order.get("inputs", []):
        if isinstance(item, dict):
            append(item, "HOT", "TASK_INPUT")
    for item in recovery_refs or []:
        if isinstance(item, dict):
            append(item, "HOT", "RECOVERY_CRITICAL")
    for value in optional_context_refs(manifest, mode):
        parsed = parse_ref(value)
        if parsed.scheme == "repo":
            safe_project_path(root, parsed.locator)
            append({"scheme": "repo", "locator": parsed.locator}, "WARM", "OPTIONAL_CONTEXT")
    stats = context_stats(hot_paths)
    return {
        "mode": mode,
        "refs": refs,
        "noema_context_units": stats["context_units"],
        "preloaded_noema_context_units": stats["context_units"],
        "exclusions": ["raw-conversations", "whole-repository", "secret-stores", "tool-catalogs"],
    }


class ReadSet:
    """Execution-local, freshness-keyed read memoization without durable caching."""

    def __init__(self) -> None:
        self._seen: set[tuple[str, str, str | None]] = set()
        self.suppressed = 0
        self.thrash_events = 0

    def record(self, ref: dict, freshness: str | None = None, *, low_signal: bool = False) -> dict:
        key = (ref.get("scheme", ""), ref.get("locator", ""), freshness)
        if key in self._seen:
            self.suppressed += 1
            return {"read": False, "reason_code": "DUPLICATE_READ_SUPPRESSED"}
        self._seen.add(key)
        if low_signal:
            self.thrash_events += 1
            return {"read": True, "reason_code": "CONTEXT_THRASH"}
        return {"read": True, "reason_code": "READ_REQUIRED"}
