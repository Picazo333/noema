"""Occurrence-level plan-versus-actual evaluation without invented telemetry."""

from __future__ import annotations

from collections import Counter, defaultdict

from .bindings import (canonical_bytes, envelope_digest, material_digest,
                       obligation_ref, observation_projection, observation_subject)
from .economics import economics_vector
from .evidence import VerificationContext, result, verify_host_snapshot
from .semantics import normalize_scope


def expected_observations(envelope: dict) -> dict:
    candidates = (envelope["input_bindings"]["candidate_snapshot"]["snapshot"] or {}).get("tools", [])
    requirements = (envelope["input_bindings"]["metadata"]["snapshot"] or {}).get("tool_requirements", {})
    by_id: dict[str, list[dict]] = defaultdict(list)
    for candidate in candidates:
        if isinstance(candidate, dict):
            by_id[str(candidate.get("id") or candidate.get("candidate") or "unknown")].append(candidate)
    expected: dict[str, list[dict]] = {"tools": [], "actors": []}
    seen: Counter[bytes] = Counter()
    for decision in envelope.get("tool_decisions", []):
        if decision.get("decision") != "CALL":
            continue
        ident = decision["candidate"]
        matches = by_id[ident]
        binding = {"decision": decision, "candidate": matches[0] if len(matches) == 1 else None,
                   "requirements": requirements}
        key = canonical_bytes(binding)
        occurrence = seen[key]
        seen[key] += 1
        expected["tools"].append({"kind": "tool", "id": ident, "binding": binding,
                                  "occurrence": occurrence, "ambiguous": len(matches) != 1,
                                  "obligation_ref": obligation_ref(envelope, "tool", binding, occurrence)})
    seen.clear()
    for binding in envelope.get("topology", {}).get("role_bindings", []):
        normalized = {**binding}
        if "scope" in normalized:
            normalized["scope"] = [normalize_scope(value) for value in normalized["scope"]]
        key = canonical_bytes(normalized)
        occurrence = seen[key]
        seen[key] += 1
        expected["actors"].append({"kind": "actor", "id": binding["role_id"],
                                   "binding": normalized, "occurrence": occurrence,
                                   "obligation_ref": obligation_ref(envelope, "actor", normalized, occurrence)})
    return expected


def _dimension(expected: list[dict], observed: list[dict], kind: str,
               revision: int, observation_indices: list[int] | None = None) -> tuple[dict, list[str]]:
    matched: list[str] = []
    absent: list[str] = []
    unexpected: list[int] = []
    duplicates: list[str] = []
    deviations: list[str] = []
    by_ref = {item["obligation_ref"]: item for item in expected}
    by_name: dict[str, list[dict]] = defaultdict(list)
    for item in expected:
        by_name[item["id"]].append(item)
    consumed: set[str] = set()
    for index, event in enumerate(observed):
        original_index = observation_indices[index] if observation_indices is not None else index
        ref = event.get("obligation_ref")
        item = by_ref.get(ref) if ref else None
        name = event.get("candidate" if kind == "tools" else "role_id")
        if revision == 2 and item is None and ref is None and len(by_name.get(name, [])) == 1:
            item = by_name[name][0]
        if item is None:
            unexpected.append(original_index)
            if revision == 3 and ref is None and by_name.get(name):
                deviations.append("TOOL_OBLIGATION_UNBOUND" if kind == "tools"
                                  else "ACTOR_OBLIGATION_UNBOUND")
            elif kind == "tools" and event.get("action") == "CALL":
                deviations.append("UNPLANNED_TOOL_CALL" if not ref else "TOOL_OBLIGATION_MISMATCH")
            elif kind == "actors":
                deviations.append("UNEXPECTED_ACTOR")
            continue
        identity = item["obligation_ref"]
        if identity in consumed:
            duplicates.append(identity)
            deviations.append("DUPLICATE_OBLIGATION_OBSERVATION")
            continue
        consumed.add(identity)
        if name != item["id"]:
            unexpected.append(original_index)
            deviations.append("TOOL_BINDING_MISMATCH" if kind == "tools" else "ACTOR_BINDING_MISMATCH")
            continue
        if kind == "tools":
            if item.get("ambiguous"):
                deviations.append("AMBIGUOUS_TOOL_CANDIDATE")
            elif event.get("action") == "CALL" and event.get("result") != "NOT_CALLED":
                matched.append(identity)
            else:
                absent.append(identity)
                deviations.append("EXPECTED_TOOL_NOT_CALLED")
        else:
            missing_fields = []
            wrong_fields = []
            for field, expected_value in item["binding"].items():
                if field == "role_id":
                    continue
                if field not in event:
                    missing_fields.append(field)
                    continue
                actual_value = event[field]
                if field == "scope":
                    try:
                        actual_value = [normalize_scope(value) for value in actual_value]
                    except (TypeError, ValueError):
                        wrong_fields.append(field)
                        continue
                if actual_value != expected_value:
                    wrong_fields.append(field)
            if wrong_fields:
                deviations.append("ACTOR_BINDING_MISMATCH")
            if event.get("participation") == "REPORTED_NOT_EXECUTED":
                absent.append(identity)
                deviations.append("EXPECTED_ACTOR_NOT_EXECUTED")
                continue
            if revision == 3 and event.get("participation") != "REPORTED_EXECUTED":
                missing_fields.append("participation")
            if wrong_fields:
                matched.append(identity)
            elif not missing_fields:
                matched.append(identity)
    missing = [item["obligation_ref"] for item in expected
               if item["obligation_ref"] not in matched and item["obligation_ref"] not in absent]
    if duplicates:
        missing = sorted(set(missing) | set(duplicates))
    return {"expected": [item["obligation_ref"] for item in expected],
            "matched": matched, "explicitly_absent": absent, "missing": missing,
            "unexpected": unexpected, "duplicates": duplicates,
            "status": "INCOMPLETE" if missing or duplicates else "COMPLETE"}, deviations


def evaluate_material_coverage(envelope: dict, trace: dict) -> tuple[dict, list[str]]:
    obligations = expected_observations(envelope)
    actual = trace.get("actual", {})
    revision = trace.get("contract_revision", 0)
    coverage: dict[str, dict] = {}
    deviations: list[str] = []
    for dimension, field in (("tools", "tool_events"), ("actors", "role_bindings")):
        events = actual.get(field, [])
        indices = list(range(len(events)))
        if dimension == "tools":
            non_executable = {(item["candidate"], item["decision"])
                              for item in envelope.get("tool_decisions", [])
                              if item.get("decision") != "CALL"}
            retained = [(index, event) for index, event in enumerate(events)
                        if event.get("obligation_ref") or
                        (event.get("candidate"), event.get("action")) not in non_executable]
            indices = [index for index, _ in retained]
            events = [event for _, event in retained]
        coverage[dimension], found = _dimension(obligations[dimension], events,
                                                dimension, revision, indices)
        deviations.extend(found)
    for dimension, expected_value in (
        ("executor", envelope.get("executor", {}).get("selected_executor")),
        ("model", envelope.get("model", {}).get("selected_model")),
    ):
        observed = actual.get(dimension)
        required = expected_value is not None
        missing = [dimension] if required and observed is None else []
        unexpected = [dimension] if observed is not None and observed != expected_value else []
        if unexpected:
            deviations.append(dimension.upper() + "_MISMATCH")
        coverage[dimension] = {"expected": [expected_value] if required else [],
                               "matched": [observed] if observed is not None and not unexpected else [],
                               "explicitly_absent": [], "missing": missing,
                               "unexpected": unexpected, "duplicates": [],
                               "status": "INCOMPLETE" if missing else "COMPLETE"}
    return coverage, deviations


def compare_execution(envelope: dict, trace: dict,
                      verification_context: VerificationContext | None = None) -> dict:
    deviations: list[str] = []
    if trace.get("contract_revision") not in {2, 3}:
        deviations.append("TRACE_REVISION_MISMATCH")
    for field in ("execution_id", "work_order_id", "project_id"):
        if trace.get(field) != envelope.get(field):
            deviations.append(field.upper() + "_MISMATCH")
    if trace.get("envelope_ref") != {"scheme": "memory", "locator": envelope.get("execution_id")}:
        deviations.append("ENVELOPE_REF_MISMATCH")
    if trace.get("envelope_digest") != envelope_digest(envelope):
        deviations.append("ENVELOPE_DIGEST_MISMATCH")
    if trace.get("material_digest") != material_digest(envelope):
        deviations.append("MATERIAL_DIGEST_MISMATCH")
    coverage, found = evaluate_material_coverage(envelope, trace)
    deviations.extend(found)
    actual = trace.get("actual", {})
    decisions = {(item["candidate"], item["decision"])
                 for item in envelope.get("tool_decisions", [])}
    for event in actual.get("tool_events", []):
        if event.get("action") == "CALL" and (event.get("candidate"), "SOFT_SUPPRESS") in decisions:
            deviations.append("REDUNDANT_TOOL_CALL")
        if event.get("action") == "SOFT_SUPPRESS" and (event.get("candidate"), "CALL") in decisions:
            deviations.append("FALSE_TOOL_SUPPRESSION")
    dimensions = [name for name in ("tools", "actors", "executor", "model") if coverage[name]["expected"]]
    projection = observation_projection(envelope, trace, dimensions)
    subject = observation_subject(projection)
    if dimensions:
        verified = (verify_host_snapshot(verification_context, "execution:observations", subject,
                                        "EXECUTION_OBSERVATIONS", "project:" + envelope["project_id"],
                                        projection) if verification_context is not None else
                    result("execution:observations", subject, "EXECUTION_OBSERVATIONS",
                           "UNVERIFIED", "TRUST_ROOT_MISSING"))
    else:
        verified = result("execution:observations", subject, "EXECUTION_OBSERVATIONS",
                          "NOT_REQUIRED", "NO_MATERIAL_OBLIGATIONS")
    missing = [name for name, item in coverage.items() if item["status"] == "INCOMPLETE"]
    if trace.get("contract_revision") == 2 and (
        coverage["tools"]["expected"] or coverage["actors"]["expected"]
    ):
        missing.append("legacy_obligation_binding")
    if trace.get("outcome") == "UNKNOWN":
        missing.append("outcome")
    if actual.get("context_events") is None:
        missing.append("historical_reads")
    if dimensions and verified.state != "VERIFIED":
        missing.append("execution_observations")
    if any(item["unexpected"] or item["duplicates"] for item in coverage.values()):
        deviations.append("MATERIAL_OBSERVATION_DEVIATION")
    status = "FAIL" if deviations else "INCOMPLETE" if missing else "PASS"
    return {"execution_id": envelope["execution_id"], "deviations": sorted(set(deviations)),
            "economics": economics_vector(trace), "coverage": coverage,
            "coverage_basis": "REPORTED", "observation_verification": verified.to_dict(),
            "conformance": "DEVIATION" if deviations else "NOT_CERTIFIABLE" if missing else "MATCH",
            "reported_outcome": trace.get("outcome"), "status": status,
            "missing_observations": sorted(set(missing))}
