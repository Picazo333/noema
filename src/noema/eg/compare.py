"""Plan-versus-actual classification without inventing telemetry."""

from __future__ import annotations

from .economics import economics_vector
from .bindings import envelope_digest, material_digest


def compare_execution(envelope: dict, trace: dict) -> dict:
    deviations = []
    revision2 = envelope.get("contract_revision") == 2
    if revision2:
        if trace.get("contract_revision") != 2:
            deviations.append("TRACE_REVISION_MISMATCH")
        if trace.get("execution_id") != envelope.get("execution_id"):
            deviations.append("EXECUTION_ID_MISMATCH")
        if trace.get("work_order_id") != envelope.get("work_order_id"):
            deviations.append("WORK_ORDER_ID_MISMATCH")
        if trace.get("project_id") != envelope.get("project_id"):
            deviations.append("PROJECT_ID_MISMATCH")
        if trace.get("envelope_ref") != {"scheme": "memory", "locator": envelope.get("execution_id")}:
            deviations.append("ENVELOPE_REF_MISMATCH")
        if trace.get("envelope_digest") != envelope_digest(envelope):
            deviations.append("ENVELOPE_DIGEST_MISMATCH")
        if trace.get("material_digest") != material_digest(envelope):
            deviations.append("MATERIAL_DIGEST_MISMATCH")
    planned_tools = {item["candidate"]: item["decision"] for item in envelope.get("tool_decisions", [])}
    for event in trace.get("actual", {}).get("tool_events", []):
        planned = planned_tools.get(event.get("candidate"))
        if revision2 and event.get("action") == "CALL" and planned != "CALL":
            deviations.append("UNPLANNED_TOOL_CALL")
        if planned == "SOFT_SUPPRESS" and event.get("action") == "CALL":
            deviations.append("REDUNDANT_TOOL_CALL")
        if planned == "CALL" and event.get("action") == "SOFT_SUPPRESS":
            deviations.append("FALSE_TOOL_SUPPRESSION")
    if (trace.get("actual", {}).get("executor")
            and trace["actual"]["executor"] != envelope.get("executor", {}).get("selected_executor")):
        deviations.append("EXECUTOR_MISMATCH")
    if (trace.get("actual", {}).get("model")
            and trace["actual"]["model"] != envelope.get("model", {}).get("selected_model")):
        deviations.append("MODEL_MISMATCH")
    result = {"execution_id": envelope["execution_id"], "deviations": sorted(set(deviations)), "economics": economics_vector(trace)}
    if revision2:
        coverage = trace.get("observation_coverage", {})
        missing = [name for name, status in coverage.items() if status == "UNVERIFIED"]
        if trace.get("outcome") == "UNKNOWN":
            missing.append("outcome")
        result["status"] = "FAIL" if deviations else "INCOMPLETE" if missing else "PASS"
        result["missing_observations"] = sorted(set(missing))
    return result
