"""Transient predicate-specific verification against a host-selected root."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from ..loader import load_yaml
from .bindings import digest, read_subject


@dataclass(frozen=True)
class VerificationResult:
    requirement_id: str
    subject_fingerprint: str
    predicate: str
    state: str
    method: str
    source_ref: dict | None
    source_digest: str | None
    authority: str | None
    observed_at: str | None
    valid_until: str | None
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class VerificationContext:
    project_root: Path
    package_root: Path
    policy_revision: str
    verifier_revision: str
    baseline_sha: str | None
    evaluated_at: datetime
    trust_root_id: str | None
    sources: tuple[dict, ...]

    @classmethod
    def from_host(cls, project_root: Path, package_root: Path,
                  trust_path: Path | None = None) -> "VerificationContext":
        project = project_root.resolve()
        package = package_root.resolve()
        now = datetime.now(timezone.utc)
        if trust_path is None:
            return cls(project, package, "eg-policy-v1", "r5", None, now, None, ())
        source_path = trust_path.resolve()
        if source_path.is_relative_to(project):
            raise ValueError("EG trust context cannot be inside the evaluated project")
        raw = source_path.read_bytes()
        config = load_yaml(source_path)
        if not isinstance(config, dict) or not isinstance(config.get("sources"), list):
            raise ValueError("EG trust context has invalid structure")
        root_id = "sha256:" + sha256(raw).hexdigest()
        return cls(project, package, str(config.get("policy_revision", "eg-policy-v1")),
                   str(config.get("verifier_revision", "r5")),
                   config.get("baseline_sha"), now, root_id,
                   tuple(config["sources"]))


def result(requirement_id: str, subject: str, predicate: str, state: str,
           reason: str, *, method: str = "NONE", source_ref: dict | None = None,
           source_digest: str | None = None, authority: str | None = None,
           observed_at: str | None = None, valid_until: str | None = None) -> VerificationResult:
    return VerificationResult(requirement_id, subject, predicate, state, method,
                              source_ref, source_digest, authority, observed_at,
                              valid_until, (reason,))


def verify_content(path: Path, expected_digest: str, requirement_id: str,
                   subject: str) -> VerificationResult:
    try:
        observed = "sha256:" + sha256(path.read_bytes()).hexdigest()
    except OSError:
        return result(requirement_id, subject, "CONTENT_INTEGRITY", "UNVERIFIED", "SOURCE_UNAVAILABLE")
    state = "VERIFIED" if observed == expected_digest else "INVALID"
    return result(requirement_id, subject, "CONTENT_INTEGRITY", state,
                  "CONTENT_MATCH" if state == "VERIFIED" else "CONTENT_MISMATCH",
                  method="OBSERVED_BYTES", source_ref={"scheme": "file", "locator": str(path)},
                  source_digest=observed, observed_at=datetime.now(timezone.utc).isoformat())


def verify_assertion(context: VerificationContext, requirement_id: str,
                     subject: str, predicate: str, scope: str,
                     evidence_ref: dict | None = None) -> VerificationResult:
    if context.trust_root_id is None:
        return result(requirement_id, subject, predicate, "UNVERIFIED", "TRUST_ROOT_MISSING")
    for source in context.sources:
        if not isinstance(source, dict):
            continue
        if any(source.get(name) != value for name, value in
               (("predicate", predicate), ("subject", subject), ("scope", scope))):
            continue
        ref = source.get("ref")
        if not isinstance(ref, dict) or ref.get("scheme") != "file":
            continue
        if evidence_ref is not None and evidence_ref != ref:
            continue
        path = Path(str(ref.get("locator", ""))).resolve()
        if path.is_relative_to(context.project_root):
            continue
        try:
            raw = path.read_bytes()
            observed = "sha256:" + sha256(raw).hexdigest()
            claimed = source.get("digest")
            if observed != claimed:
                return result(requirement_id, subject, predicate, "INVALID", "SOURCE_DIGEST_MISMATCH")
            valid_until = datetime.fromisoformat(str(source["valid_until"]).replace("Z", "+00:00"))
            if valid_until <= context.evaluated_at:
                return result(requirement_id, subject, predicate, "UNVERIFIED", "SOURCE_EXPIRED")
            assertion = load_yaml(path)
            if not isinstance(assertion, dict):
                return result(requirement_id, subject, predicate, "INVALID", "ASSERTION_INVALID")
            if (assertion.get("predicate") != predicate or assertion.get("subject") != subject
                    or assertion.get("scope") != scope
                    or assertion.get("authority") != source.get("authority")):
                return result(requirement_id, subject, predicate, "INVALID", "ASSERTION_MISMATCH")
            expected_decision = "APPROVED" if predicate == "HUMAN_APPROVAL" else "VERIFIED"
            if assertion.get("decision") != expected_decision:
                return result(requirement_id, subject, predicate, "INVALID", "ASSERTION_DENIED")
            return result(requirement_id, subject, predicate, "VERIFIED", "AUTHORITY_ASSERTION_MATCH",
                          method="HOST_ACCEPTED_SOURCE", source_ref=ref, source_digest=observed,
                          authority=source.get("authority"),
                          observed_at=context.evaluated_at.isoformat(),
                          valid_until=valid_until.isoformat())
        except (OSError, ValueError, KeyError):
            return result(requirement_id, subject, predicate, "UNVERIFIED", "SOURCE_UNAVAILABLE")
    return result(requirement_id, subject, predicate, "UNVERIFIED", "NO_ACCEPTED_SOURCE")


def verify_host_snapshot(context: VerificationContext, requirement_id: str,
                         subject: str, predicate: str, scope: str,
                         expected: object) -> VerificationResult:
    """Compare a caller-supplied state with bytes independently pinned by the host."""
    if context.trust_root_id is None:
        return result(requirement_id, subject, predicate, "UNVERIFIED", "TRUST_ROOT_MISSING")
    for source in context.sources:
        if not isinstance(source, dict) or any(source.get(key) != value for key, value in (
            ("predicate", predicate), ("subject", subject), ("scope", scope),
        )):
            continue
        ref = source.get("ref")
        if not isinstance(ref, dict) or ref.get("scheme") != "file":
            continue
        path = Path(str(ref.get("locator", ""))).resolve()
        if path.is_relative_to(context.project_root):
            continue
        try:
            raw = path.read_bytes()
            observed = "sha256:" + sha256(raw).hexdigest()
            if observed != source.get("digest"):
                return result(requirement_id, subject, predicate, "INVALID", "SOURCE_DIGEST_MISMATCH")
            valid_until = datetime.fromisoformat(str(source["valid_until"]).replace("Z", "+00:00"))
            if valid_until <= context.evaluated_at:
                return result(requirement_id, subject, predicate, "UNVERIFIED", "SOURCE_EXPIRED")
            if load_yaml(path) != expected:
                return result(requirement_id, subject, predicate, "INVALID", "HOST_STATE_MISMATCH")
            return result(requirement_id, subject, predicate, "VERIFIED", "HOST_STATE_MATCH",
                          method="HOST_PINNED_BYTES", source_ref=ref, source_digest=observed,
                          authority=source.get("authority"),
                          observed_at=context.evaluated_at.isoformat(),
                          valid_until=valid_until.isoformat())
        except (OSError, ValueError, KeyError):
            return result(requirement_id, subject, predicate, "UNVERIFIED", "SOURCE_UNAVAILABLE")
    return result(requirement_id, subject, predicate, "UNVERIFIED", "NO_ACCEPTED_SOURCE")


def context_identity(context: VerificationContext) -> str | None:
    if context.trust_root_id is None:
        return None
    return digest("noema-eg-trust-context-r2", {
        "trust_root_id": context.trust_root_id,
        "policy_revision": context.policy_revision,
        "verifier_revision": context.verifier_revision,
    })


def candidate_subject(kind: str, candidate: dict, requirements: dict) -> str:
    """Bind a qualification projection to the exact candidate and requested use."""
    return digest("noema-eg-candidate-r2", {
        "kind": kind,
        "candidate": candidate,
        "requirements": requirements,
    })


def verify_trace_read_bindings(trace: dict, context: VerificationContext) -> bool:
    """Reverify every historical-read source against the current host root."""
    events = trace.get("actual", {}).get("context_events", [])
    for binding in trace.get("read_identity_bindings", []):
        index = binding["event_index"]
        if index >= len(events):
            return False
        ref = events[index]["ref"]
        subject = read_subject(trace, index, ref)
        checked = verify_assertion(
            context, f"read:{index}", subject, "HISTORICAL_READ_IDENTITY",
            "project:" + trace["project_id"], binding["source_ref"])
        if (checked.state != "VERIFIED" or checked.source_digest != binding["source_digest"]
                or subject != binding["subject_fingerprint"]):
            return False
    return True


def required_dependency_results(envelope: dict, context: VerificationContext) -> tuple[list[dict], list[str]]:
    """Verify each material dependency against its exact subject and authority."""
    observations: list[dict] = []
    reasons: list[str] = []
    scope = "project:" + envelope["project_id"]
    needs = envelope["effective_needs"]
    candidates = envelope["input_bindings"]["candidate_snapshot"]["snapshot"] or {}
    metadata = envelope["input_bindings"]["metadata"]["snapshot"] or {}

    def require(requirement_id: str, subject: str, predicate: str) -> None:
        checked = verify_assertion(context, requirement_id, subject, predicate, scope)
        observations.append(checked.to_dict())
        if checked.state != "VERIFIED":
            reasons.append(predicate + "_UNVERIFIED")

    def missing(requirement_id: str, subject: str, predicate: str,
                reason_code: str) -> None:
        observations.append(result(requirement_id, subject, predicate,
                                   "UNVERIFIED", reason_code).to_dict())
        reasons.append(reason_code)

    if envelope["decision"]["control"] == "REQUIRE_HUMAN":
        host_claim = envelope["input_bindings"]["host_capabilities"]["snapshot"] or {}
        if host_claim.get("capabilities", {}).get("enforce_human_gate") is not True:
            reasons.append("HUMAN_GATE_UNENFORCEABLE")
        else:
            require("host:human-gate", candidate_subject("host", host_claim, {
                "work_order_id": envelope["work_order_id"],
                "action_id": envelope["intent"]["action_id"],
            }), "HOST_GATE_ENFORCEMENT")

    for capability in needs.get("capability_requirements", []):
        matched = False
        for receipt in envelope.get("resolver_receipts", []):
            if receipt.get("status") not in {"RESOLVED", "PARTIAL"}:
                continue
            if capability in receipt.get("unresolved_capabilities", []):
                continue
            if capability not in receipt.get("satisfied_capabilities", []):
                continue
            ref = receipt.get("resolution_ref")
            if not isinstance(ref, dict):
                continue
            scheme, locator = ref.get("scheme"), ref.get("locator")
            if scheme == "repo" and isinstance(locator, str):
                path = (context.project_root / locator).resolve()
                if not path.is_relative_to(context.project_root):
                    continue
            elif scheme == "file" and isinstance(locator, str):
                path = Path(locator).resolve()
            else:
                continue
            if not path.is_file():
                continue
            if receipt.get("integrity"):
                observed = "sha256:" + sha256(path.read_bytes()).hexdigest()
                if receipt["integrity"] != observed:
                    continue
            matched = True
            require(f"resolver:{capability}", candidate_subject("resolver", receipt, {
                "capability": capability,
            }),
                    "RESOLVER_SATISFACTION")
            break
        if not matched:
            missing(f"resolver:{capability}", f"resolver:{capability}",
                    "RESOLVER_SATISFACTION", "RESOLVER_RESULT_UNVERIFIED")

    tool_requirements = metadata.get("tool_requirements", {})
    tools = {item.get("id"): item for item in candidates.get("tools", [])
             if isinstance(item, dict) and item.get("id")}
    selected_tools = envelope["intent"]["planned_tools"]
    if tool_requirements and not selected_tools:
        missing("tool:selection", digest("noema-eg-tool-requirement-r2", tool_requirements),
                "TOOL_SELECTION", "TOOL_NOT_SELECTED")
    for tool_id in selected_tools:
        candidate = tools.get(tool_id)
        if not isinstance(candidate, dict):
            missing(f"tool:{tool_id}", f"tool:{tool_id}",
                    "TOOL_QUALIFICATION", "TOOL_CANDIDATE_MISSING")
            continue
        required_caps = set(tool_requirements.get("capabilities", []))
        required_interfaces = set(tool_requirements.get("interfaces", []))
        if (candidate.get("allowed") is not True or candidate.get("available") is not True
                or candidate.get("qualification") != "VERIFIED"
                or candidate.get("availability") not in {"AVAILABLE", "available"}
                or not required_caps.issubset(set(candidate.get("capabilities", [])))
                or not required_interfaces.issubset(set(candidate.get("interfaces", [])))):
            missing(f"tool:{tool_id}:qualification",
                    candidate_subject("tool", candidate, tool_requirements),
                    "TOOL_QUALIFICATION", "TOOL_CLAIM_INSUFFICIENT")
            continue
        subject = candidate_subject("tool", candidate, tool_requirements)
        require(f"tool:{tool_id}:qualification", subject, "TOOL_QUALIFICATION")
        require(f"tool:{tool_id}:availability", subject, "TOOL_AVAILABILITY")
    for category, required in (("resources", needs.get("required_resources", [])),
                               ("interfaces", needs.get("required_interfaces", []))):
        witnesses = {item.get("id"): item for item in candidates.get(category, [])
                     if isinstance(item, dict) and item.get("id")}
        for ident in required:
            witness = witnesses.get(ident)
            if (not isinstance(witness, dict) or witness.get("available") is not True
                    or witness.get("allowed") is not True
                    or witness.get("qualification") != "VERIFIED"):
                missing(f"{category}:{ident}", f"{category}:{ident}",
                        "RESOURCE_AVAILABILITY" if category == "resources" else "INTERFACE_AVAILABILITY",
                        "DEPENDENCY_CLAIM_INSUFFICIENT")
            else:
                require(f"{category}:{ident}", candidate_subject(category, witness, {"id": ident}),
                        "RESOURCE_AVAILABILITY" if category == "resources" else "INTERFACE_AVAILABILITY")
    model_requirements = metadata.get("model_requirements", {})
    if model_requirements:
        model_id = envelope["intent"]["planned_model"]
        models = {item.get("id"): item for item in candidates.get("models", [])
                  if isinstance(item, dict) and item.get("id")}
        model = models.get(model_id)
        if (not isinstance(model, dict) or model.get("available") is not True
                or model.get("qualification") != "VERIFIED"
                or not set(model_requirements.get("modalities", [])).issubset(
                    set(model.get("modalities", [])))):
            missing(f"model:{model_id}:qualification", f"model:{model_id}",
                    "MODEL_QUALIFICATION", "MODEL_CLAIM_INSUFFICIENT")
        else:
            subject = candidate_subject("model", model, model_requirements)
            require(f"model:{model_id}:qualification", subject, "MODEL_QUALIFICATION")
            require(f"model:{model_id}:availability", subject, "MODEL_AVAILABILITY")
    if metadata.get("executor_requirements"):
        executor_id = envelope["intent"]["planned_executor"]
        if not executor_id:
            missing("executor:selection", "executor:missing",
                    "EXECUTOR_ELIGIBILITY", "EXECUTOR_NOT_SELECTED")
        else:
            require(f"executor:{executor_id}", f"executor:{executor_id}", "EXECUTOR_ELIGIBILITY")
    if envelope["topology"].get("mode") == "PARALLEL_ISOLATED":
        require("parallel-isolation", envelope["material_binding"]["digest"], "HOST_ISOLATION")
    return observations, sorted(set(reasons))
