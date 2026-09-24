"""Derived execution-local load planning over Noema's existing context resolver."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import posixpath
import re

from ..context import context_stats, optional_context_refs, resolve_context_paths
from ..refs import parse_ref, safe_project_path


_TIERS = {"HOT", "WARM", "COLD", "NEVER_PRELOAD"}


def _repo_ref(path: Path, root: Path) -> dict:
    return {"scheme": "repo", "locator": path.relative_to(root).as_posix()}


def _as_ref(value: object) -> dict:
    if isinstance(value, dict) and {"scheme", "locator"}.issubset(value):
        return dict(value)
    if isinstance(value, str):
        parsed = parse_ref(value)
        return {"scheme": parsed.scheme, "locator": parsed.locator}
    raise ValueError("Context candidate must be a StorageRef or URI")


def _append(refs: list[dict], seen: set[tuple[str, str]], ref: dict, tier: str, reason: str) -> None:
    key = (ref["scheme"], ref["locator"])
    if key not in seen:
        seen.add(key)
        refs.append({"ref": ref, "load_tier": tier, "reason_codes": [reason]})


def build_context_plan(
    root: Path,
    manifest: dict,
    work_order: dict,
    *,
    recovery_refs: list | None = None,
    context_hints: dict | None = None,
) -> dict:
    """Derive task-relative HOT/WARM/COLD/NEVER_PRELOAD refs without loading them."""
    root = root.resolve()
    hints = context_hints or {}
    mode = work_order.get("context_mode", manifest["context"].get("default_mode", "build"))
    hot_paths = resolve_context_paths(root, manifest, mode, include_optional=False)
    refs: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for path in hot_paths:
        _append(refs, seen, _repo_ref(path, root), "HOT", "REQUIRED_CONTEXT")
    for item in work_order.get("inputs", []):
        _append(refs, seen, _as_ref(item), "HOT", "TASK_INPUT")
    for item in recovery_refs or []:
        _append(refs, seen, _as_ref(item), "HOT", "RECOVERY_CRITICAL")
    for value in optional_context_refs(manifest, mode):
        parsed = parse_ref(value)
        if parsed.scheme == "repo":
            safe_project_path(root, parsed.locator)
            _append(refs, seen, {"scheme": "repo", "locator": parsed.locator}, "WARM", "OPTIONAL_CONTEXT")
    for item in hints.get("warm_refs", []):
        _append(refs, seen, _as_ref(item), "WARM", "KNOWN_RELEVANT")
    for item in hints.get("cold_refs", []) + hints.get("historical_refs", []):
        _append(refs, seen, _as_ref(item), "COLD", "HISTORICAL_OR_INACTIVE")
    for item in hints.get("never_preload_refs", []):
        _append(refs, seen, _as_ref(item), "NEVER_PRELOAD", "EXPLICIT_NO_PRELOAD")
    stats = context_stats(hot_paths)
    plan = {
        "mode": mode,
        "refs": refs,
        "noema_context_units": stats["context_units"],
        "preloaded_noema_context_units": stats["context_units"],
        "exclusions": ["raw-conversations", "whole-repository", "secret-stores", "tool-catalogs"],
        "tier_transitions": [],
        "read_set_policy": {"dedupe_by_ref_and_freshness": True},
    }
    for promotion in hints.get("promotions", []):
        promote_context_ref(plan, _as_ref(promotion["ref"]), promotion["reason_code"])
    return plan


def promote_context_ref(context_plan: dict, ref: dict, reason_code: str) -> dict:
    """Promote a known execution-relative ref to HOT with auditable reason."""
    if not reason_code:
        raise ValueError("Context promotion requires a reason code")
    for item in context_plan.get("refs", []):
        if item["ref"].get("scheme") == ref.get("scheme") and item["ref"].get("locator") == ref.get("locator"):
            previous = item["load_tier"]
            if previous not in _TIERS:
                raise ValueError("Unknown context load tier")
            if previous != "HOT":
                item["load_tier"] = "HOT"
                item["reason_codes"].append(reason_code)
                context_plan.setdefault("tier_transitions", []).append(
                    {"ref": item["ref"], "from": previous, "to": "HOT", "reason_code": reason_code}
                )
            return item
    raise ValueError("Cannot promote a ref absent from the context plan")


class ReadSet:
    """Execution-local freshness-keyed read memoization with traceable outcomes."""

    def __init__(self) -> None:
        self._seen: set[tuple[str, str, str, str]] = set()
        self.suppressed = 0
        self.thrash_events = 0

    def record(self, ref: dict, freshness: str | None = None, *, low_signal: bool = False) -> dict:
        identity = self._identity(ref, freshness)
        if identity.kind == "UNKNOWN":
            return self._read_required(identity, low_signal)
        key = (identity.scheme, identity.locator, identity.kind, identity.fingerprint)
        if key in self._seen:
            self.suppressed += 1
            return {
                "read": False,
                "reason_code": "DUPLICATE_READ_SUPPRESSED",
                "identity_kind": identity.kind,
                "identity_fingerprint": identity.fingerprint,
            }
        self._seen.add(key)
        return self._read_required(identity, low_signal)

    @staticmethod
    def _identity(ref: dict, freshness: str | None) -> "ReadIdentity":
        scheme = str(ref.get("scheme", "")).casefold()
        locator = str(ref.get("locator", "")).replace("\\", "/").strip()
        locator = posixpath.normpath(locator) if locator else locator
        integrity = ref.get("integrity")
        if isinstance(integrity, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", integrity):
            return ReadIdentity.from_evidence(scheme, locator, "INTEGRITY", integrity)
        return ReadIdentity(scheme, locator, "UNKNOWN", None)

    def _read_required(self, identity: "ReadIdentity", low_signal: bool) -> dict:
        if low_signal:
            self.thrash_events += 1
            return {
                "read": True,
                "reason_code": "CONTEXT_THRASH",
                "identity_kind": identity.kind,
                "identity_fingerprint": identity.fingerprint,
            }
        return {
            "read": True,
            "reason_code": "READ_REQUIRED",
            "identity_kind": identity.kind,
            "identity_fingerprint": identity.fingerprint,
        }


@dataclass(frozen=True)
class ReadIdentity:
    scheme: str
    locator: str
    kind: str
    fingerprint: str | None

    @classmethod
    def from_evidence(cls, scheme: str, locator: str, kind: str, evidence: str) -> "ReadIdentity":
        fingerprint = sha256(f"{scheme}:{locator}:{kind}:{evidence}".encode("utf-8")).hexdigest()
        return cls(scheme, locator, kind, fingerprint)
