"""Single semantic-contract kernel for experimental Execution Governance.

Schemas establish shape.  This module establishes the cross-field invariants
that JSON Schema cannot express safely.  Every public EG boundary uses these
structured issues rather than maintaining its own interpretation of validity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import posixpath
import re
from pathlib import Path
from typing import Iterable

from ..schemas import validation_errors


@dataclass(frozen=True)
class SemanticIssue:
    code: str
    severity: str
    path: str
    message: str
    related_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


class SemanticValidationError(ValueError):
    def __init__(self, issues: Iterable[SemanticIssue]):
        self.issues = tuple(issues)
        super().__init__("; ".join(f"{issue.code}: {issue.message}" for issue in self.issues))


def issue(code: str, path: str, message: str, *, severity: str = "ERROR", related_refs: Iterable[str] = ()) -> SemanticIssue:
    return SemanticIssue(code, severity, path, message, tuple(related_refs))


def raise_for_issues(issues: Iterable[SemanticIssue]) -> None:
    collected = tuple(issues)
    if collected:
        raise SemanticValidationError(collected)


def canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()


def normalize_scope(scope: object) -> str:
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("scope must be a non-empty project-relative path")
    value = scope.replace("\\", "/").strip()
    if value.startswith(("/", "//")) or re.match(r"^[A-Za-z]:", value) or any(char in value for char in "*?["):
        raise ValueError("scope must be project-relative")
    normalized = posixpath.normpath(value)
    if normalized in {"", "."} or ".." in normalized.split("/"):
        raise ValueError("scope must not escape the project")
    return normalized


def scopes_overlap(left: str, right: str) -> bool:
    left, right = left.casefold(), right.casefold()
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def validate_work_order_semantics(work_order: object) -> list[SemanticIssue]:
    if not isinstance(work_order, dict):
        return [issue("EG-WORKORDER-OBJECT", "$", "WorkOrder must be an object")]
    return []


def validate_runtime_pressure_semantics(snapshot: object) -> list[SemanticIssue]:
    if not isinstance(snapshot, dict):
        return [issue("EG-RUNTIME-OBJECT", "$", "runtime-pressure must be an object")]
    issues: list[SemanticIssue] = []
    for field in ("blocked_resources", "blocked_interfaces"):
        value = snapshot.get(field, [])
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            issues.append(issue("EG-RUNTIME-DEPENDENCY", field, f"{field} must be a list of non-empty identifiers"))
    return issues


_RESOLVER_STATUSES = {"NOT_REQUIRED", "RESOLVED", "PARTIAL", "UNRESOLVED", "BLOCKED"}


def _storage_ref(value: object) -> bool:
    return isinstance(value, dict) and isinstance(value.get("scheme"), str) and bool(value.get("scheme")) and isinstance(value.get("locator"), str) and bool(value.get("locator"))


def validate_resolver_receipt_semantics(receipt: object, *, participates: bool | None = None) -> list[SemanticIssue]:
    if not isinstance(receipt, dict):
        return [issue("EG-RESOLVER-OBJECT", "$", "resolver receipt must be an object")]
    status = receipt.get("status")
    issues: list[SemanticIssue] = []
    if status not in _RESOLVER_STATUSES:
        return [issue("EG-RESOLVER-STATUS", "status", "resolver status is not in the frozen vocabulary")]
    ref = receipt.get("resolution_ref")
    if status in {"RESOLVED", "PARTIAL"} and not _storage_ref(ref):
        issues.append(issue("EG-RESOLVER-USABLE-RESULT", "resolution_ref", f"{status} requires a usable resolution_ref"))
    if status == "PARTIAL":
        unresolved = receipt.get("unresolved_capabilities")
        if not isinstance(unresolved, list) or not unresolved or any(not isinstance(value, str) or not value for value in unresolved):
            issues.append(issue("EG-RESOLVER-PARTIAL-SET", "unresolved_capabilities", "PARTIAL requires an explicit non-empty unresolved_capabilities set"))
    if participates is True and status == "NOT_REQUIRED":
        issues.append(issue("EG-RESOLVER-PARTICIPATION", "status", "NOT_REQUIRED cannot satisfy a required resolver dependency"))
    return issues


def validate_topology_semantics(topology: object) -> list[SemanticIssue]:
    if not isinstance(topology, dict):
        return [issue("EG-TOPOLOGY-OBJECT", "topology", "topology must be an object")]
    if topology.get("mode") != "PARALLEL_ISOLATED":
        return []
    issues: list[SemanticIssue] = []
    bindings = topology.get("role_bindings")
    scopes = topology.get("write_scopes")
    if not isinstance(bindings, list) or len(bindings) < 2:
        return [issue("EG-TOPOLOGY-BINDINGS", "topology.role_bindings", "parallel isolation requires at least two writing bindings")]
    if not isinstance(scopes, list) or len(scopes) < 2:
        return [issue("EG-TOPOLOGY-SCOPES", "topology.write_scopes", "parallel isolation requires at least two write scopes")]
    owner_by_scope: dict[str, str] = {}
    declared: set[str] = set()
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict) or not isinstance(binding.get("role_id"), str) or not binding["role_id"]:
            issues.append(issue("EG-TOPOLOGY-WORKER", f"topology.role_bindings[{index}]", "every writing binding requires role_id"))
            continue
        worker_scopes = binding.get("scope")
        if not isinstance(worker_scopes, list) or not worker_scopes:
            issues.append(issue("EG-TOPOLOGY-WORKER-SCOPE", f"topology.role_bindings[{index}].scope", "every writing binding requires non-empty scope"))
            continue
        for scope_index, raw_scope in enumerate(worker_scopes):
            try:
                normalized = normalize_scope(raw_scope)
            except ValueError as exc:
                issues.append(issue("EG-TOPOLOGY-SCOPE", f"topology.role_bindings[{index}].scope[{scope_index}]", str(exc)))
                continue
            key = normalized.casefold()
            for prior, owner in owner_by_scope.items():
                if owner != binding["role_id"] and scopes_overlap(prior, key):
                    issues.append(issue("EG-TOPOLOGY-OWNERSHIP-COLLISION", f"topology.role_bindings[{index}].scope[{scope_index}]", f"{normalized} overlaps scope owned by {owner}"))
            if key in owner_by_scope and owner_by_scope[key] != binding["role_id"]:
                issues.append(issue("EG-TOPOLOGY-OWNERSHIP-COLLISION", f"topology.role_bindings[{index}].scope[{scope_index}]", f"{normalized} has multiple writing owners"))
            owner_by_scope[key] = binding["role_id"]
    for index, raw_scope in enumerate(scopes):
        try:
            normalized = normalize_scope(raw_scope)
        except ValueError as exc:
            issues.append(issue("EG-TOPOLOGY-SCOPE", f"topology.write_scopes[{index}]", str(exc)))
            continue
        key = normalized.casefold()
        for prior in declared:
            if scopes_overlap(prior, key):
                issues.append(issue("EG-TOPOLOGY-SCOPE-COLLISION", f"topology.write_scopes[{index}]", f"{normalized} overlaps declared write scope {prior}"))
        declared.add(key)
    if declared != set(owner_by_scope):
        issues.append(issue("EG-TOPOLOGY-OWNERSHIP-MAP", "topology", "declared write scopes must map to exactly one writing worker"))
    return issues


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_metric_semantics(metric: object, path: str) -> list[SemanticIssue]:
    if not isinstance(metric, dict):
        return [issue("EG-METRIC-OBJECT", path, "metric must be an object")]
    status, value = metric.get("status"), metric.get("value")
    if status == "UNAVAILABLE":
        return [] if value is None else [issue("EG-METRIC-UNAVAILABLE", path + ".value", "UNAVAILABLE metrics require null value")]
    if status == "MEASURED":
        return [] if _is_finite_number(value) else [issue("EG-METRIC-MEASURED", path + ".value", "MEASURED metrics require a finite observed number")]
    if status == "ESTIMATED":
        problems = [] if _is_finite_number(value) else [issue("EG-METRIC-ESTIMATED", path + ".value", "ESTIMATED metrics require a finite number")]
        if not _storage_ref(metric.get("methodology_ref")):
            problems.append(issue("EG-METRIC-METHODOLOGY", path + ".methodology_ref", "ESTIMATED metrics require methodology_ref"))
        return problems
    return [issue("EG-METRIC-STATUS", path + ".status", "metric status is not in the frozen vocabulary")]


def validate_trace_semantics(trace: object) -> list[SemanticIssue]:
    if not isinstance(trace, dict):
        return [issue("EG-TRACE-OBJECT", "$", "ExecutionTrace must be an object")]
    issues: list[SemanticIssue] = []
    metrics = trace.get("metrics", {})
    if isinstance(metrics, dict):
        for name, value in metrics.items():
            issues.extend(validate_metric_semantics(value, f"metrics.{name}"))
    actual = trace.get("actual", {})
    if isinstance(actual, dict):
        for index, event in enumerate(actual.get("context_events", [])):
            if not isinstance(event, dict):
                continue
            kind = event.get("identity_kind")
            fingerprint = event.get("identity_fingerprint")
            if kind == "UNKNOWN" and fingerprint is not None:
                issues.append(issue("EG-READ-UNKNOWN-FINGERPRINT", f"actual.context_events[{index}]", "unknown read identity cannot claim a fingerprint"))
            if kind != "UNKNOWN" and (not isinstance(fingerprint, str) or not fingerprint):
                issues.append(issue("EG-READ-FINGERPRINT", f"actual.context_events[{index}]", "read identity evidence requires a stable fingerprint"))
    return issues


def validate_envelope_semantics(envelope: object) -> list[SemanticIssue]:
    if not isinstance(envelope, dict):
        return [issue("EG-ENVELOPE-OBJECT", "$", "ExecutionEnvelope must be an object")]
    issues = validate_topology_semantics(envelope.get("topology"))
    required = bool(envelope.get("capability_requirements"))
    receipts = envelope.get("resolver_receipts", [])
    if required and not receipts:
        issues.append(issue("EG-RESOLVER-MISSING", "resolver_receipts", "required resolution has no receipt"))
    if isinstance(receipts, list):
        for index, receipt in enumerate(receipts):
            issues.extend(
                SemanticIssue(item.code, item.severity, f"resolver_receipts[{index}].{item.path}", item.message, item.related_refs)
                for item in validate_resolver_receipt_semantics(receipt, participates=required)
            )
            if required and isinstance(receipt, dict) and receipt.get("status") == "BLOCKED" and envelope.get("disposition") == "ROUTED":
                issues.append(issue("EG-RESOLVER-BLOCKED-ROUTED", f"resolver_receipts[{index}]", "blocked required resolution cannot produce ROUTED"))
    return issues


def validate_resume_semantics(envelope: object, state: object) -> list[SemanticIssue]:
    if not isinstance(envelope, dict) or not isinstance(state, dict):
        return [issue("EG-RESUME-OBJECT", "$", "resume inputs must be objects")]
    recovery = envelope.get("recovery", {})
    required = recovery.get("prohibited_scope", []) if isinstance(recovery, dict) else []
    actual = state.get("prohibited_scope", [])
    try:
        previous = {normalize_scope(scope).casefold() for scope in required}
        resumed = {normalize_scope(scope).casefold() for scope in actual}
    except ValueError as exc:
        return [issue("EG-RESUME-SCOPE", "prohibited_scope", str(exc))]
    if not previous.issubset(resumed):
        return [issue("EG-RESUME-PROHIBITION", "prohibited_scope", "resume removed an inherited prohibited scope")]
    return []


def contract_issues(kind: str, data: object, root: Path) -> list[SemanticIssue]:
    """Return structural and semantic issues for a public artifact."""
    structural = [issue("EG-SCHEMA", ".".join(map(str, error.absolute_path)) or "$", error.message) for error in validation_errors(kind, data, root)]
    if structural:
        return structural
    validators = {
        "work-order": validate_work_order_semantics,
        "runtime-pressure": validate_runtime_pressure_semantics,
        "execution-envelope": validate_envelope_semantics,
        "execution-trace": validate_trace_semantics,
    }
    validator = validators.get(kind)
    return validator(data) if validator else []
