"""Thin wrappers around the frozen RC0 executor router and runtime model inputs."""

from __future__ import annotations

from pathlib import Path

from ..routing import load_executors, load_routes, select_executor


def select_existing_executor(root: Path, requirements: dict, runtime: dict | None = None) -> dict:
    routes = load_routes(root)
    executors = load_executors(root)
    route = next(
        (
            route
            for route in routes
            if set(requirements.get("capabilities", [])).issubset(
                set(route.get("requires", {}).get("capabilities", []))
            )
        ),
        {"prefer": [], "fallback": []},
    )
    return select_executor(requirements, executors, route, runtime)


def filter_model_candidates(candidates: list[dict] | None, requirements: dict | None = None) -> dict:
    requirements = requirements or {}
    for candidate in candidates or []:
        if not candidate.get("available", True):
            continue
        if set(requirements.get("modalities", [])).issubset(set(candidate.get("modalities", []))):
            return {"selected_model": candidate.get("id"), "selection": "RUNTIME_CANDIDATE"}
    return {"selected_model": None, "selection": "UNBOUND_HOST_SELECTED"}
