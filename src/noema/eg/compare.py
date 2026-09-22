"""Plan-versus-actual classification without inventing telemetry."""

from __future__ import annotations

from .economics import economics_vector


def compare_execution(envelope: dict, trace: dict) -> dict:
    deviations = []
    planned_tools = {item["candidate"]: item["decision"] for item in envelope.get("tool_decisions", [])}
    for event in trace.get("actual", {}).get("tool_events", []):
        planned = planned_tools.get(event.get("candidate"))
        if planned == "SOFT_SUPPRESS" and event.get("action") == "CALL":
            deviations.append("REDUNDANT_TOOL_CALL")
        if planned == "CALL" and event.get("action") == "SOFT_SUPPRESS":
            deviations.append("FALSE_TOOL_SUPPRESSION")
    if trace.get("actual", {}).get("executor") and trace["actual"]["executor"] != envelope.get("executor", {}).get("selected_executor"):
        if envelope.get("executor", {}).get("selected_executor") is not None:
            deviations.append("EXECUTOR_MISMATCH")
    if trace.get("actual", {}).get("model") and envelope.get("model", {}).get("selected_model") not in {None, trace["actual"]["model"]}:
        deviations.append("MODEL_MISMATCH")
    return {"execution_id": envelope["execution_id"], "deviations": sorted(set(deviations)), "economics": economics_vector(trace)}
