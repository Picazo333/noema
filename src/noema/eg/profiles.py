"""Generic host profile and runtime-capability handling."""

from __future__ import annotations

from pathlib import Path

from ..loader import load_yaml


FEATURES = (
    "repo_read",
    "repo_write_reversible",
    "merge",
    "execute_local_cli",
    "spawn_isolated_worker",
    "enforce_human_gate",
)


def load_host_capabilities(path: Path | None = None, profile: str = "eg.repo-agent.v0") -> dict:
    if path is None:
        return {"profile": profile, "capabilities": {}, "telemetry": {}}
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ValueError("Host capabilities must be a YAML object")
    return data


def feature_status(host_capabilities: dict, feature: str) -> str:
    value = host_capabilities.get("capabilities", host_capabilities).get(feature)
    return "AVAILABLE" if value is True else "UNAVAILABLE"


def flattened_capabilities(host_capabilities: dict) -> dict:
    return dict(host_capabilities.get("capabilities", host_capabilities))
