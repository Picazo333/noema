"""Honest component-vector economics; intentionally no aggregate score."""

from __future__ import annotations

from .trace import metric


def economics_vector(trace: dict) -> dict:
    metrics = trace.get("metrics", {})
    keys = ("context_units", "input_tokens", "output_tokens", "monetary_cost", "wall_time_ms", "human_interventions")
    return {
        key: metrics.get(key, metric()) for key in keys
    } | {
        "tool_calls": sum(1 for event in trace.get("actual", {}).get("tool_events", []) if event.get("action") == "CALL"),
        "suppressed_calls": sum(1 for event in trace.get("actual", {}).get("tool_events", []) if event.get("action") == "SOFT_SUPPRESS"),
        "retries": trace.get("retries", 0),
        "rework_cycles": trace.get("rework_cycles", 0),
        "outcome": trace.get("outcome"),
    }
