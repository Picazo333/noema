"""Deterministic ExecutionEnvelope composition entry point."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..loader import load_yaml
from ..schemas import schema_root, validation_errors
from .classification import (
    classify_action_effect,
    classify_authority_scope,
    classify_data_sensitivity,
    classify_deliberation,
)
from .context_plan import build_context_plan
from .decision import decide_disposition
from .evaluation import derive_evaluation_constraints
from .executor import filter_model_candidates, select_existing_executor
from .interop import validate_resolver_receipt
from .permissions import evaluate_control
from .profiles import flattened_capabilities
from .recovery import recovery_requirements
from .runtime import (
    classify_runtime_posture,
    derive_resource_policy,
    resource_disposition_constraint,
)
from .tooling import decide_tools
from .topology import derive_topology


def _storage_ref(value: str | dict) -> dict:
    if isinstance(value, dict):
        return value
    if "://" not in value:
        raise ValueError("WorkOrder reference must be a StorageRef or URI")
    scheme, locator = value.split("://", 1)
    return {"scheme": scheme, "locator": locator}


def _validate_work_order(work_order: dict, root: Path) -> None:
    errors = validation_errors("work-order", work_order, schema_root(root))
    if errors:
        rendered = "; ".join(error.message for error in errors[:3])
        raise ValueError(f"Invalid WorkOrder: {rendered}")


def _terminal(disposition: str, reason: str) -> dict:
    return {"disposition": disposition, "reason_codes": [reason]}


def build_execution_envelope(
    root: Path,
    work_order: dict,
    *,
    work_order_ref: str | dict,
    profile: str = "eg.repo-agent.v0",
    host_capabilities: dict | None = None,
    candidate_snapshot: dict | None = None,
    runtime_pressure: dict | None = None,
    resolver_receipts: list[dict] | None = None,
    task_metadata: dict | None = None,
    baseline_sha: str | None = None,
) -> dict:
    """Create derived governance state; no tool call or host action occurs here."""
    root = root.resolve()
    _validate_work_order(work_order, root)
    manifest = load_yaml(root / "noema.project.yaml")
    work_order_project_id = work_order["project_id"]
    metadata = task_metadata or {}
    candidates = candidate_snapshot or {}
    host = flattened_capabilities(host_capabilities or {})
    action = classify_action_effect(work_order, metadata.get("requested_action"))
    sensitivity = classify_data_sensitivity(work_order.get("inputs"), metadata)
    authority = classify_authority_scope(manifest, metadata.get("target_ref"))
    control = evaluate_control(action, sensitivity, authority, work_order, host)
    deliberation = classify_deliberation(work_order, metadata)
    evaluation = derive_evaluation_constraints(work_order, metadata)
    topology = derive_topology(metadata, evaluation)
    receipts = [validate_resolver_receipt(item) for item in resolver_receipts or []]
    executor_requirements = metadata.get("executor_requirements", {})
    model_requirements = metadata.get("model_requirements", {})
    tool_requirements = metadata.get("tool_requirements", {})
    resolver_required = bool(work_order.get("capability_requirements") or metadata.get("resolver_required"))
    unexpected_receipts = bool(receipts) and not resolver_required
    needs_resolution = bool(
        resolver_required
        or tool_requirements
        or executor_requirements
        or model_requirements
    )
    decision = decide_disposition(
        control["control"],
        already_complete=bool(metadata.get("already_complete")),
        needs_resolution=needs_resolution,
        needs_topology=topology["mode"] != "SINGLE",
        context_simple=not bool(metadata.get("complex_context")),
        required_evidence_available=not bool(metadata.get("required_evidence_unavailable")),
    )
    context = build_context_plan(
        root,
        manifest,
        work_order,
        recovery_refs=metadata.get("recovery_refs"),
        context_hints=metadata.get("context_hints"),
    )
    posture = classify_runtime_posture(runtime_pressure)
    resource_policy = derive_resource_policy(posture, host, deliberation, topology["mode"])
    resource_policy["snapshot_ref"] = runtime_pressure.get("source_ref") if runtime_pressure else None

    tool_decisions: list[dict] = []
    executor = {"requirements": executor_requirements, "selected_executor": None, "status": "UNBOUND"}
    model = {"requirements": model_requirements, "selected_model": None, "selection": "UNBOUND_HOST_SELECTED"}
    final = decision

    resolver_statuses = {receipt["status"] for receipt in receipts}
    if work_order_project_id != manifest["project"]["id"]:
        final = _terminal("ROUTE_ELSEWHERE", "WORK_ORDER_PROJECT_MISMATCH")
    elif resolver_required and not receipts:
        final = _terminal("DEFER", "RESOLVER_RECEIPT_MISSING")
    elif resolver_required and "BLOCKED" in resolver_statuses:
        final = _terminal("BLOCKED", "RESOLVER_BLOCKED")
    elif resolver_required and "UNRESOLVED" in resolver_statuses:
        final = _terminal("DEFER", "RESOLVER_UNRESOLVED")
    elif resolver_required and not resolver_statuses.issubset({"RESOLVED", "PARTIAL"}):
        final = _terminal("DEFER", "RESOLVER_RECEIPT_UNUSABLE")
    elif control["control"] == "REQUIRE_HUMAN" and not host.get("enforce_human_gate"):
        final = _terminal("DEFER", "HUMAN_GATE_UNENFORCEABLE")

    runtime_constraint = resource_disposition_constraint(
        posture, runtime_pressure, metadata, candidates
    )
    if runtime_constraint is not None:
        final = _terminal(runtime_constraint["disposition"], runtime_constraint["reason_code"])

    if final["disposition"] == "ROUTED":
        tool_decisions = decide_tools(candidates.get("tools", []), tool_requirements, control=control["control"])
        if tool_requirements and not any(item["decision"] == "CALL" for item in tool_decisions):
            final = _terminal("DEFER", "NO_ELIGIBLE_TOOL")
        if final["disposition"] == "ROUTED" and executor_requirements:
            selected = select_existing_executor(
                root, executor_requirements, candidates.get("executor_runtime")
            )
            executor = {
                "requirements": executor_requirements,
                "selected_executor": selected["executor"],
                "status": selected["status"],
                "eligible": selected["eligible"],
            }
            if selected["status"] == "BLOCKED_NO_VERIFIED_EXECUTOR":
                final = _terminal("BLOCKED", "BLOCKED_NO_VERIFIED_EXECUTOR")
        if final["disposition"] == "ROUTED" and model_requirements:
            selected_model = filter_model_candidates(candidates.get("models"), model_requirements)
            model = {"requirements": model_requirements, **selected_model}
            if model["selected_model"] is None:
                final = _terminal("DEFER", "NO_ELIGIBLE_MODEL")

    baseline = (
        {"scheme": "git", "locator": baseline_sha}
        if baseline_sha
        else {"scheme": "repo", "locator": "."}
    )
    reasons = list(
        dict.fromkeys(
            control["reason_codes"]
            + final["reason_codes"]
            + resource_policy["reason_codes"]
            + (["RESOLVER_RECEIPT_NOT_REQUIRED"] if unexpected_receipts else [])
        )
    )
    return {
        "execution_id": f"exec-{uuid4().hex}",
        "work_order_ref": _storage_ref(work_order_ref),
        "work_order_id": work_order["work_order_id"],
        "project_id": work_order_project_id,
        "profile": profile,
        "policy_version": "eg-policy-v0",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "baseline_ref": baseline,
        "disposition": final["disposition"],
        "reason_codes": reasons,
        "decision": {
            "deliberation": deliberation.value,
            "action_effect": action.value,
            "data_sensitivity": sensitivity.value,
            "authority_scope": authority.value,
            "control": control["control"],
        },
        "context": context,
        "runtime_resource_policy": resource_policy,
        "capability_requirements": list(work_order.get("capability_requirements", [])),
        "resolver_receipts": receipts,
        "tool_decisions": tool_decisions,
        "executor": executor,
        "model": model,
        "topology": topology,
        "evaluation_constraints": evaluation,
        "recovery": recovery_requirements(
            work_order,
            baseline_sha,
            metadata,
            effective_executor=executor["selected_executor"],
        ),
        "evidence_refs": [],
    }
