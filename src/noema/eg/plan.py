"""Deterministic ExecutionEnvelope composition entry point."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..loader import load_yaml
from .classification import (
    classify_action_effect,
    classify_authority_scope,
    classify_data_sensitivity,
    classify_deliberation,
)
from .context_plan import build_context_plan
from .decision import decide_disposition
from .evaluation import derive_evaluation_constraints
from .interop import validate_resolver_receipt
from .permissions import evaluate_control
from .profiles import flattened_capabilities
from .recovery import recovery_requirements
from .runtime import classify_runtime_posture, derive_resource_policy
from .tooling import decide_tools
from .topology import derive_topology


def _storage_ref(value: str | dict) -> dict:
    if isinstance(value, dict):
        return value
    if "://" not in value:
        raise ValueError("WorkOrder reference must be a StorageRef or URI")
    scheme, locator = value.split("://", 1)
    return {"scheme": scheme, "locator": locator}


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
    """Create a derived envelope. It never performs a tool call or host action."""
    root = root.resolve()
    manifest = load_yaml(root / "noema.project.yaml")
    metadata = task_metadata or {}
    host = flattened_capabilities(host_capabilities or {})
    action = classify_action_effect(work_order, metadata.get("requested_action"))
    sensitivity = classify_data_sensitivity(work_order.get("inputs", []), metadata)
    authority = classify_authority_scope(manifest, metadata.get("target_ref"))
    control = evaluate_control(action, sensitivity, authority, work_order, host)
    deliberation = classify_deliberation(work_order, metadata)
    evaluation = derive_evaluation_constraints(work_order, metadata)
    topology = derive_topology(metadata, evaluation)
    receipts = [validate_resolver_receipt(item) for item in resolver_receipts or []]
    needs_resolution = bool(work_order.get("capability_requirements") or receipts)
    decision = decide_disposition(
        control["control"],
        already_complete=bool(metadata.get("already_complete")),
        needs_resolution=needs_resolution,
        needs_topology=topology["mode"] != "SINGLE",
        context_simple=not bool(metadata.get("complex_context")),
        required_evidence_available=not bool(metadata.get("required_evidence_unavailable")),
    )
    context = build_context_plan(root, manifest, work_order)
    posture = classify_runtime_posture(runtime_pressure)
    resource_policy = derive_resource_policy(posture, host, deliberation, topology["mode"])
    resource_policy["snapshot_ref"] = runtime_pressure.get("source_ref") if runtime_pressure else None
    # DIRECT, NO_ACTION and terminal paths intentionally skip candidate routing.
    tool_decisions = []
    if decision["disposition"] == "ROUTED":
        tool_decisions = decide_tools((candidate_snapshot or {}).get("tools", []), metadata.get("tool_requirements"), control=control["control"])
    baseline = {"scheme": "git", "locator": baseline_sha} if baseline_sha else {"scheme": "repo", "locator": "."}
    reasons = list(dict.fromkeys(control["reason_codes"] + decision["reason_codes"] + resource_policy["reason_codes"]))
    return {
        "execution_id": f"exec-{uuid4().hex}",
        "work_order_ref": _storage_ref(work_order_ref),
        "project_id": manifest["project"]["id"],
        "profile": profile,
        "policy_version": "eg-policy-v0",
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "baseline_ref": baseline,
        "disposition": decision["disposition"],
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
        "executor": {"requirements": metadata.get("executor_requirements", {}), "selected_executor": None},
        "model": {"requirements": metadata.get("model_requirements", {}), "selected_model": None},
        "topology": topology,
        "evaluation_constraints": evaluation,
        "recovery": recovery_requirements(work_order, baseline_sha),
        "evidence_refs": [],
    }
