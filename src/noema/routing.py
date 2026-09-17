from __future__ import annotations

from pathlib import Path
from .loader import load_yaml


def load_executors(protocol_root: Path) -> list[dict]:
    data = load_yaml(protocol_root / "registry/executors.yaml") or {}
    return list(data.get("executors", []))


def load_routes(protocol_root: Path) -> list[dict]:
    data = load_yaml(protocol_root / "registry/routing.yaml") or {}
    return list(data.get("routes", []))


def load_runtime_availability(path: Path | None = None) -> dict[str, dict]:
    path = path or (Path.home() / ".noema/runtime/availability.yaml")
    if not path.exists():
        return {}
    data = load_yaml(path) or {}
    if isinstance(data, dict) and "executors" in data:
        return {item["id"]: item for item in data.get("executors", []) if isinstance(item, dict) and "id" in item}
    return data if isinstance(data, dict) else {}


def _eligible(executor: dict, required_caps: set[str], required_interfaces: set[str], required_modalities: set[str], runtime: dict) -> bool:
    if executor.get("status") != "verified":
        return False
    if not required_caps.issubset(set(executor.get("capabilities", []))):
        return False
    if required_interfaces and not required_interfaces.issubset(set(executor.get("interfaces", []))):
        return False
    if required_modalities and not required_modalities.issubset(set(executor.get("modalities", []))):
        return False
    rt = runtime.get(executor.get("id"), {})
    if rt.get("enabled") is False or rt.get("availability") in {"down", "blocked"}:
        return False
    return True


def select_executor(requirements: dict, executors: list[dict], route: dict, runtime: dict | None = None) -> dict:
    runtime = runtime or {}
    required_caps = set(requirements.get("capabilities", []))
    required_interfaces = set(requirements.get("interfaces", []))
    required_modalities = set(requirements.get("modalities", []))
    by_id = {e["id"]: e for e in executors}
    eligible = {eid for eid, e in by_id.items() if _eligible(e, required_caps, required_interfaces, required_modalities, runtime)}
    order = list(route.get("prefer", [])) + [x for x in route.get("fallback", []) if x not in route.get("prefer", [])]
    for eid in order:
        if eid in eligible:
            return {"status": "ROUTED", "executor": eid, "eligible": sorted(eligible)}
    return {"status": "BLOCKED_NO_VERIFIED_EXECUTOR", "executor": None, "eligible": sorted(eligible)}
