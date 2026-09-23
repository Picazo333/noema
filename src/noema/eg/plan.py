"""Deterministic ExecutionEnvelope composition entry point."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ..loader import load_yaml
from ..schemas import schema_root
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
from .needs import derive_execution_needs
from .permissions import evaluate_control
from .profiles import flattened_capabilities
from .recovery import recovery_requirements
from .runtime import (
    classify_runtime_posture,
    derive_resource_policy,
    resource_disposition_constraint,
)
from .provenance import LoadedWorkOrder, programmatic_work_order
from .semantics import canonical_digest, contract_issues, raise_for_issues, sensitive_ref, validate_envelope_semantics
from .tooling import decide_tools
from .topology import derive_topology
from .bindings import gate_fingerprint, material_digest
from .evidence import VerificationContext, required_dependency_results
from .persistence import assert_persistable, project_r2_inputs


def _validate_work_order(work_order: dict, root: Path) -> None:
    errors = contract_issues("work-order", work_order, schema_root(root))
    if errors:
        rendered = "; ".join(error.message for error in errors[:3])
        raise ValueError(f"Invalid WorkOrder: {rendered}")


def _terminal(disposition: str, reason: str) -> dict:
    return {"disposition": disposition, "reason_codes": [reason]}


def _binding(value: object, source_ref: dict | None = None) -> dict:
    def reject_credentials(item: object) -> None:
        if isinstance(item, dict):
            if sensitive_ref(item):
                raise ValueError("EG input reference contains a credential-like locator")
            for key, child in item.items():
                if str(key).lower().replace("-", "_") in {
                    "access_token", "refresh_token", "api_key", "password", "client_secret",
                    "authorization", "credential", "secret_key",
                }:
                    raise ValueError("EG input snapshot contains a credential-like field")
                reject_credentials(child)
        elif isinstance(item, list):
            for child in item:
                reject_credentials(child)

    reject_credentials(value)
    digest = canonical_digest(value)
    return {
        "snapshot": value,
        "digest": digest,
        "source_ref": source_ref or {"scheme": "memory", "locator": digest, "integrity": digest},
    }


def build_execution_envelope(
    root: Path,
    work_order: dict,
    *,
    work_order_ref: str | dict | None = None,
    loaded_work_order: LoadedWorkOrder | None = None,
    profile: str = "eg.repo-agent.v0",
    host_capabilities: dict | None = None,
    candidate_snapshot: dict | None = None,
    runtime_pressure: dict | None = None,
    resolver_receipts: list[dict] | None = None,
    task_metadata: dict | None = None,
    baseline_sha: str | None = None,
    revision: int | None = None,
    verification_context: VerificationContext | None = None,
    _replay_execution_id: str | None = None,
    _replay_created_at: str | None = None,
) -> dict:
    """Create derived governance state; no tool call or host action occurs here."""
    root = root.resolve()
    # `work_order_ref` is retained only for source compatibility.  It is not
    # authoritative: programmatic input receives a content-bound identity and
    # CLI input supplies LoadedWorkOrder from the file it actually read.
    loaded = loaded_work_order or programmatic_work_order(work_order)
    if loaded.data != work_order:
        raise ValueError("LoadedWorkOrder data must be the WorkOrder being planned")
    if loaded_work_order is not None:
        ref = loaded_work_order.canonical_source_ref
        if ref.get("scheme") == "file":
            from .provenance import load_work_order

            verified = load_work_order(Path(ref["locator"]))
            if verified.data != work_order or verified.source_digest != loaded_work_order.source_digest:
                raise ValueError("LoadedWorkOrder source does not match its file content")
            loaded = verified
        else:
            loaded = programmatic_work_order(work_order)
    _validate_work_order(loaded.data, root)
    work_order = loaded.data
    manifest = load_yaml(root / "noema.project.yaml")
    work_order_project_id = work_order["project_id"]
    metadata = task_metadata or {}
    candidates = candidate_snapshot or {}
    if revision == 2:
        metadata, candidates = project_r2_inputs(metadata, candidates)
    host = flattened_capabilities(host_capabilities or {})
    action = classify_action_effect(work_order, metadata.get("requested_action"))
    sensitivity = classify_data_sensitivity(work_order.get("inputs"), metadata)
    authority = classify_authority_scope(manifest, metadata.get("target_ref"))
    control = evaluate_control(action, sensitivity, authority, work_order, host)
    deliberation = classify_deliberation(work_order, metadata)
    evaluation = derive_evaluation_constraints(work_order, metadata)
    topology = derive_topology(metadata, evaluation)
    receipts = [validate_resolver_receipt(item, revision=2 if revision == 2 else 1)
                for item in resolver_receipts or []]
    needs = derive_execution_needs(work_order, metadata)
    executor_requirements = metadata.get("executor_requirements", {})
    model_requirements = metadata.get("model_requirements", {})
    tool_requirements = metadata.get("tool_requirements", {})
    resolver_required = needs.resolution_required
    unexpected_receipts = bool(receipts) and not resolver_required
    needs_resolution = needs.external_required
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
    elif resolver_required and any(
        set(receipt.get("unresolved_capabilities", [])) & needs.capability_requirements
        for receipt in receipts if receipt.get("status") == "PARTIAL"
    ):
        final = _terminal("DEFER", "RESOLVER_PARTIAL_REQUIRED")
    elif resolver_required and not resolver_statuses.issubset({"RESOLVED", "PARTIAL"}):
        final = _terminal("DEFER", "RESOLVER_RECEIPT_UNUSABLE")
    elif control["control"] == "REQUIRE_HUMAN" and not host.get("enforce_human_gate"):
        final = _terminal("DEFER", "HUMAN_GATE_UNENFORCEABLE")

    runtime_constraint = resource_disposition_constraint(
        posture, runtime_pressure, metadata, candidates, needs
    )
    if runtime_constraint is not None:
        final = _terminal(runtime_constraint["disposition"], runtime_constraint["reason_code"])

    for category, required in (("resources", needs.required_resources),
                               ("interfaces", needs.required_interfaces)):
        witnesses = candidates.get(category, [])
        verified = {item.get("id") for item in witnesses if isinstance(item, dict)
                    and item.get("available") is True and item.get("allowed") is True
                    and item.get("qualification") == "VERIFIED"}
        if required - verified and final["disposition"] not in {"BLOCKED", "ROUTE_ELSEWHERE"}:
            final = _terminal("DEFER", "REQUIRED_DEPENDENCY_UNVERIFIED")

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
    if final["disposition"] in {"DEFER", "BLOCKED", "ROUTE_ELSEWHERE", "NO_ACTION"}:
        for item in tool_decisions:
            if item["decision"] == "CALL":
                item["decision"] = "DEFER"
                item["reason_codes"] = ["PLAN_NOT_EXECUTABLE"]

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
    envelope = {
        "contract_version": "execution-envelope/v1",
        "execution_id": _replay_execution_id or f"exec-{uuid4().hex}",
        "work_order_ref": loaded.canonical_source_ref,
        "work_order_id": work_order["work_order_id"],
        "project_id": work_order_project_id,
        "profile": profile,
        "policy_version": "eg-policy-v1",
        "created_at": _replay_created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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
        "effective_needs": needs.to_dict(),
        "input_bindings": {
            "work_order": _binding(work_order, loaded.canonical_source_ref),
            "metadata": _binding(metadata),
            "runtime_pressure": _binding(runtime_pressure),
            "candidate_snapshot": _binding(candidates if revision == 2 else candidate_snapshot),
            "resolver_receipts": _binding(receipts if revision == 2 else resolver_receipts or []),
            "host_capabilities": _binding(host_capabilities),
            "manifest": _binding(manifest, {"scheme": "file", "locator": str(root / "noema.project.yaml"), "integrity": canonical_digest(manifest)}),
        },
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
    if revision == 2:
        planned_tools = sorted({item["candidate"] for item in tool_decisions
                                if item["decision"] == "CALL"})
        envelope["contract_revision"] = 2
        envelope["intent"] = {
            "attempt_id": str(metadata.get("attempt_id") or envelope["execution_id"]),
            "action_id": str(metadata.get("action_id") or "action-1"),
            "action_effect": action.value,
            "target_ref": metadata.get("target_ref"),
            "planned_executor": executor["selected_executor"],
            "planned_model": model["selected_model"],
            "planned_tools": planned_tools,
            "planned_topology": topology,
        }
        envelope["verification_requirements"] = []
        envelope["evidence_bindings"] = list(metadata.get("evidence_bindings", []))
        envelope["material_binding"] = {"algorithm": "EG-C14N-1", "digest": ""}
        envelope["material_binding"]["digest"] = material_digest(envelope)
        envelope["verification_requirements"] = [
            {"id": f"gate:{gate}", "predicate": "HUMAN_APPROVAL",
             "subject_fingerprint": gate_fingerprint(envelope, gate),
             "required_for_execution": True}
            for gate in work_order.get("human_gates", [])
        ]
        context_for_dependencies = verification_context or VerificationContext.from_host(
            root, schema_root())
        dependency_observations, dependency_reasons = required_dependency_results(
            envelope, context_for_dependencies)
        envelope["verification_requirements"].extend(
            {"id": item["requirement_id"], "predicate": item["predicate"],
             "subject_fingerprint": item["subject_fingerprint"],
             "required_for_execution": True} for item in dependency_observations
        )
        if dependency_reasons and envelope["disposition"] not in {"BLOCKED", "ROUTE_ELSEWHERE"}:
            envelope["disposition"] = "DEFER"
            envelope["reason_codes"] = list(dict.fromkeys(
                envelope["reason_codes"] + ["DEPENDENCY_EVIDENCE_UNVERIFIED"]))
            for item in envelope["tool_decisions"]:
                if item["decision"] == "CALL":
                    item["decision"] = "DEFER"
                    item["reason_codes"] = ["DEPENDENCY_EVIDENCE_UNVERIFIED"]
        assert_persistable(envelope)
    elif revision is not None:
        raise ValueError("Unsupported EG contract revision")
    raise_for_issues(validate_envelope_semantics(envelope))
    return envelope
