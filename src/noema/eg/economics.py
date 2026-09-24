"""Honest component-vector economics; intentionally no aggregate score."""

from __future__ import annotations

from .trace import metric


def economics_vector(trace: dict) -> dict:
    metrics = trace.get("metrics", {})
    keys = ("context_units", "input_tokens", "output_tokens", "monetary_cost", "wall_time_ms", "human_interventions")
    return {
        key: metrics.get(key, metric()) for key in keys
    } | {
        "tool_calls": metrics.get("tool_calls", metric()),
        "suppressed_calls": metrics.get("suppressed_calls", metric()),
        "retries": trace.get("retries"),
        "rework_cycles": trace.get("rework_cycles"),
        "outcome": trace.get("outcome"),
    }
