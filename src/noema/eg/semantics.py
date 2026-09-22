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
from urllib.parse import parse_qsl, urlsplit

from ..loader import load_yaml
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


_CREDENTIAL_KEYS = {"access_token", "token", "api_key", "apikey", "password", "secret", "signature", "sig", "credential", "authorization", "auth"}


def sensitive_ref(value: object) -> bool:
    if not _storage_ref(value):
        return False
    locator = value["locator"]
    parsed = urlsplit(locator)
    if parsed.username or parsed.password:
        return True
    return any(key.lower().replace("-", "_") in _CREDENTIAL_KEYS
               for key, _ in parse_qsl(parsed.query, keep_blank_values=True))


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
    actors: set[str] = set()
    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict) or not isinstance(binding.get("role_id"), str) or not binding["role_id"]:
            issues.append(issue("EG-TOPOLOGY-WORKER", f"topology.role_bindings[{index}]", "every writing binding requires role_id"))
            continue
        actor = binding["role_id"].casefold()
        if actor in actors:
            issues.append(issue("EG-TOPOLOGY-DUPLICATE-ACTOR", f"topology.role_bindings[{index}].role_id", "parallel writing actors must have distinct role_id values"))
        actors.add(actor)
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
        return [] if _is_finite_number(value) and value >= 0 else [issue("EG-METRIC-MEASURED", path + ".value", "MEASURED metrics require a non-negative finite observed number")]
    if status == "ESTIMATED":
        problems = [] if _is_finite_number(value) and value >= 0 else [issue("EG-METRIC-ESTIMATED", path + ".value", "ESTIMATED metrics require a non-negative finite number")]
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
    def check_refs(value: object, path: str) -> None:
        if _storage_ref(value):
            if sensitive_ref(value):
                issues.append(issue("EG-TRACE-SECRET-REF", path, "persisted reference contains a credential-like locator"))
            return
        if isinstance(value, dict):
            for key, child in value.items():
                check_refs(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                check_refs(child, f"{path}[{index}]")
    check_refs(trace, "$")
    if isinstance(actual, dict):
        seen: set[tuple[str, str, str]] = set()
        for index, event in enumerate(actual.get("context_events", [])):
            if not isinstance(event, dict):
                continue
            kind = event.get("identity_kind")
            fingerprint = event.get("identity_fingerprint")
            if kind == "UNKNOWN" and fingerprint is not None:
                issues.append(issue("EG-READ-UNKNOWN-FINGERPRINT", f"actual.context_events[{index}]", "unknown read identity cannot claim a fingerprint"))
            if kind != "UNKNOWN" and (not isinstance(fingerprint, str) or not fingerprint):
                issues.append(issue("EG-READ-FINGERPRINT", f"actual.context_events[{index}]", "read identity evidence requires a stable fingerprint"))
            if trace.get("contract_version") == "execution-trace/v1":
                ref = event.get("ref", {})
                from .context_plan import ReadSet

                identity = ReadSet._identity(ref, None)
                if kind != identity.kind or fingerprint != identity.fingerprint:
                    issues.append(issue("EG-READ-IDENTITY", f"actual.context_events[{index}]", "read identity does not match stable reference evidence"))
                key = (str(ref.get("scheme")), str(ref.get("locator")), str(fingerprint))
                if event.get("result") == "DUPLICATE_READ_SUPPRESSED" and (kind == "UNKNOWN" or key not in seen):
                    issues.append(issue("EG-READ-UNPROVEN-SUPPRESSION", f"actual.context_events[{index}]", "suppressed read has no prior stable identity"))
                if event.get("result") != "DUPLICATE_READ_SUPPRESSED" and kind != "UNKNOWN":
                    seen.add(key)
    return issues


def validate_envelope_semantics(envelope: object) -> list[SemanticIssue]:
    if not isinstance(envelope, dict):
        return [issue("EG-ENVELOPE-OBJECT", "$", "ExecutionEnvelope must be an object")]
    issues = validate_topology_semantics(envelope.get("topology"))
    disposition = envelope.get("disposition")
    control = envelope.get("decision", {}).get("control")
    calls = [item for item in envelope.get("tool_decisions", []) if isinstance(item, dict) and item.get("decision") == "CALL"]
    if control in {"DENY", "ROUTE_ELSEWHERE", "DEFER", "REQUIRE_HUMAN"} and (disposition in {"ROUTED", "DIRECT_EXECUTION"} or calls):
        issues.append(issue("EG-CONTROL-BYPASS", "disposition", "restrictive control cannot authorize execution or tool calls"))
    if disposition in {"DEFER", "BLOCKED", "ROUTE_ELSEWHERE", "NO_ACTION"} and calls:
        issues.append(issue("EG-TERMINAL-CALL", "tool_decisions", "terminal disposition cannot call a tool"))
    for index, item in enumerate(calls):
        if item.get("availability") not in {"AVAILABLE", "available"} or item.get("qualification") != "VERIFIED":
            issues.append(issue("EG-TOOL-UNQUALIFIED", f"tool_decisions[{index}]", "CALL requires explicit availability and verified qualification"))
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
    if envelope.get("contract_version") == "execution-envelope/v1":
        needs = envelope.get("effective_needs", {})
        required_ids = set(needs.get("capability_requirements", []))
        unresolved = {item for receipt in receipts if isinstance(receipt, dict) and receipt.get("status") == "PARTIAL"
                      for item in receipt.get("unresolved_capabilities", [])}
        if required_ids & unresolved and disposition in {"ROUTED", "DIRECT_EXECUTION"}:
            issues.append(issue("EG-RESOLVER-PARTIAL-REQUIRED", "resolver_receipts", "required capability remains unresolved"))
    return issues


def validate_v1_bindings(envelope: dict, root: Path) -> list[SemanticIssue]:
    bindings = envelope.get("input_bindings", {})
    issues: list[SemanticIssue] = []
    if not isinstance(bindings, dict):
        return [issue("EG-BINDINGS-MISSING", "input_bindings", "input bindings are required")]
    for name in ("work_order", "metadata", "runtime_pressure", "candidate_snapshot", "resolver_receipts", "host_capabilities", "manifest"):
        binding = bindings.get(name)
        if not isinstance(binding, dict):
            issues.append(issue("EG-BINDING-MISSING", f"input_bindings.{name}", "input binding is required"))
            continue
        digest = canonical_digest(binding.get("snapshot"))
        ref = binding.get("source_ref", {})
        if binding.get("digest") != digest or not _storage_ref(ref) or ref.get("integrity") != digest:
            issues.append(issue("EG-BINDING-DIGEST", f"input_bindings.{name}", "input snapshot, digest and reference integrity disagree"))
            continue
        if ref["scheme"] == "file":
            try:
                source = load_yaml(Path(ref["locator"]))
            except (OSError, ValueError) as exc:
                issues.append(issue("EG-SOURCE-UNVERIFIED", f"input_bindings.{name}", f"source cannot be verified: {exc}", severity="UNVERIFIED"))
                continue
            if canonical_digest(source) != digest:
                issues.append(issue("EG-SOURCE-DRIFT", f"input_bindings.{name}", "source content does not match bound snapshot"))
        elif ref["scheme"] != "memory":
            issues.append(issue("EG-SOURCE-UNVERIFIED", f"input_bindings.{name}", "source scheme has no local verifier", severity="UNVERIFIED"))
    if issues:
        return issues
    from .plan import build_execution_envelope

    work_order = bindings["work_order"]["snapshot"]
    ref = bindings["work_order"]["source_ref"]
    from .provenance import load_work_order

    loaded = load_work_order(Path(ref["locator"])) if ref["scheme"] == "file" else None
    baseline = envelope.get("baseline_ref", {})
    try:
        replay = build_execution_envelope(
            root, work_order, loaded_work_order=loaded,
            profile=envelope.get("profile", "eg.repo-agent.v0"),
            host_capabilities=bindings["host_capabilities"]["snapshot"],
            candidate_snapshot=bindings["candidate_snapshot"]["snapshot"],
            runtime_pressure=bindings["runtime_pressure"]["snapshot"],
            resolver_receipts=bindings["resolver_receipts"]["snapshot"],
            task_metadata=bindings["metadata"]["snapshot"],
            baseline_sha=baseline.get("locator") if baseline.get("scheme") == "git" else None,
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [issue("EG-REPLAY-UNVERIFIED", "$", f"contract replay failed: {exc}", severity="UNVERIFIED")]
    for field in ("work_order_ref", "work_order_id", "project_id", "disposition", "decision", "runtime_resource_policy", "capability_requirements", "resolver_receipts", "tool_decisions", "executor", "model", "topology", "evaluation_constraints", "recovery", "effective_needs"):
        if envelope.get(field) != replay.get(field):
            issues.append(issue("EG-REPLAY-MISMATCH", field, f"{field} differs from evaluated inputs"))
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
    versioned_kind = kind
    if kind in {"execution-envelope", "execution-trace"} and isinstance(data, dict):
        version = data.get("contract_version")
        if version is not None:
            if version != f"{kind}/v1":
                return [issue("EG-VERSION", "contract_version", "unsupported contract version")]
            versioned_kind = kind + "-v1"
    structural = [issue("EG-SCHEMA", ".".join(map(str, error.absolute_path)) or "$", error.message) for error in validation_errors(versioned_kind, data, root)]
    if structural:
        return structural
    validators = {
        "work-order": validate_work_order_semantics,
        "runtime-pressure": validate_runtime_pressure_semantics,
        "execution-envelope": validate_envelope_semantics,
        "execution-trace": validate_trace_semantics,
    }
    validator = validators.get(kind)
    problems = validator(data) if validator else []
    if not problems and kind == "execution-envelope" and versioned_kind.endswith("-v1"):
        problems.extend(validate_v1_bindings(data, root))
    return problems
