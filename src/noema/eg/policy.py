"""Declarative EG policy loading; policy cannot redefine ownership."""

from __future__ import annotations

from pathlib import Path

from ..loader import load_yaml


def load_policy(path: Path | None = None) -> dict:
    if path is None:
        return {"policy_version": "eg-policy-v0", "retry_cap": 1}
    data = load_yaml(path)
    if not isinstance(data, dict) or not isinstance(data.get("policy_version"), str):
        raise ValueError("EG policy must be an object with policy_version")
    return data
