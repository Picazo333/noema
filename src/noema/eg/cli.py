"""Thin command handlers for the experimental `noema eg` namespace."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator, FormatChecker

from ..loader import dump_yaml, load_json, load_yaml
from ..manifest import load_manifest
from ..schemas import schema_root
from .compare import compare_execution, expected_observations
from .plan import build_execution_envelope
from .provenance import load_work_order
from .profiles import load_host_capabilities
from .recovery import resume_check
from .runtime import classify_runtime_posture
from .scan import scan_harvest
from .trace import create_trace
from .semantics import contract_issues, raise_for_issues, validate_runtime_pressure_semantics
from .semantics import assess_envelope
from .evidence import VerificationContext, context_identity, verify_host_snapshot
from .evidence import verify_trace_read_bindings
from .bindings import material_digest
from .persistence import assert_persistable, atomic_write


_RUNTIME_SCHEMAS = {
    "host-capabilities": "host-capabilities.v0.schema.json",
    "candidate-snapshot": "candidate-snapshot.v0.schema.json",
    "runtime-pressure": "runtime-pressure.v0.schema.json",
}


def _write(data: dict, output: str | None, as_json: bool) -> None:
    assert_persistable(data)
    rendered = json.dumps(data, indent=2) if as_json else dump_yaml(data)
    if output:
        atomic_write(Path(output), rendered)
    else:
        print(rendered, end="" if rendered.endswith("\n") else "\n")


def _validate_runtime(kind: str, data: object, root: Path) -> None:
    path = root / "experimental" / "execution-governance" / "runtime-contracts" / _RUNTIME_SCHEMAS[kind]
    schema = load_json(path)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data), key=str
    )
    if errors:
        raise ValueError(f"Invalid {kind}: {errors[0].message}")
    if kind == "runtime-pressure":
        raise_for_issues(validate_runtime_pressure_semantics(data))


def _optional_runtime(kind: str, value: str | None, root: Path) -> dict | None:
    if not value:
        return None
    data = load_yaml(Path(value))
    _validate_runtime(kind, data, root)
    return data


def _validate_profile(root: Path, profile: str) -> None:
    path = root / "experimental" / "execution-governance" / "profiles" / f"{profile}.yaml"
    if not path.exists():
        raise ValueError(f"Unknown execution-governance profile: {profile}")


def doctor(args) -> int:
    root = Path(args.root).resolve()
    _validate_profile(root, args.profile)
    manifest = load_manifest(root)
    host_data = _optional_runtime("host-capabilities", args.host_capabilities, root)
    pressure = _optional_runtime("runtime-pressure", args.runtime_pressure, root)
    host = load_host_capabilities(Path(args.host_capabilities) if host_data else None, args.profile)
    posture = classify_runtime_posture(pressure)
    _write({
        "project_id": manifest["project"]["id"], "profile": args.profile,
        "protocol": manifest["noema"]["protocol"], "policy_status": "AVAILABLE",
        "host_capabilities": host.get("capabilities", {}), "telemetry": host.get("telemetry", {}),
        "runtime_pressure": {"supplied": bool(args.runtime_pressure), "posture": posture.value},
        "mutates": False,
    }, None, args.json)
    return 0


def plan(args) -> int:
    root = Path(args.root).resolve()
    context = VerificationContext.from_host(
        root, schema_root(), Path(args.trust_context) if args.trust_context else None)
    _validate_profile(root, args.profile)
    work_order_path = Path(args.work_order)
    loaded_work_order = load_work_order(work_order_path)
    work_order = loaded_work_order.data
    raise_for_issues(contract_issues("work-order", work_order, schema_root(root)))
    host_data = _optional_runtime("host-capabilities", args.host_capabilities, root)
    candidates = _optional_runtime("candidate-snapshot", args.candidate_snapshot, root)
    pressure = _optional_runtime("runtime-pressure", args.runtime_pressure, root)
    host = load_host_capabilities(Path(args.host_capabilities) if host_data else None, args.profile)
    receipts = [load_yaml(Path(item)) for item in args.resolver_receipt]
    metadata = load_yaml(Path(args.task_metadata)) if args.task_metadata else None
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        sha = None
    envelope = build_execution_envelope(
        root, work_order, loaded_work_order=loaded_work_order,
        profile=args.profile, host_capabilities=host, candidate_snapshot=candidates,
        runtime_pressure=pressure, resolver_receipts=receipts, task_metadata=metadata,
        baseline_sha=sha,
        revision=2, verification_context=context,
    )
    raise_for_issues(contract_issues("execution-envelope", envelope, context.package_root))
    assessment = assess_envelope(envelope, context)
    _write(envelope, args.out, args.json)
    return 0 if not args.require_ready or assessment["readiness"] == "EXECUTION_READY" else 1


def explain(args) -> int:
    envelope = load_yaml(Path(args.envelope))
    report = {"execution_id": envelope.get("execution_id"),
              "disposition": envelope.get("disposition"),
              "reason_codes": envelope.get("reason_codes", []),
              "control": envelope.get("decision", {}).get("control")}
    if envelope.get("contract_revision") == 2:
        context = VerificationContext.from_host(
            Path(args.root), schema_root(),
            Path(args.trust_context) if args.trust_context else None)
        assessment = assess_envelope(envelope, context)
        report["current_readiness"] = assessment["readiness"]
        report["current_reason_codes"] = assessment["reason_codes"]
        report["pending_requirements"] = [
            result["requirement_id"] for result in assessment["evidence_results"]
            if result["state"] != "VERIFIED"
        ]
        report["expected_observations"] = expected_observations(envelope)
    else:
        report["current_readiness"] = "NOT_EXECUTION_READY"
        report["current_reason_codes"] = ["LEGACY_CONTRACT_UNVERIFIED"]
    _write(report, None, args.json)
    return 0


def validate(args) -> int:
    data = load_yaml(Path(args.path))
    kind = args.kind or ("execution-trace" if "trace_id" in data else "execution-envelope")
    context = VerificationContext.from_host(
        Path(args.root), schema_root(), Path(args.trust_context) if args.trust_context else None)
    if kind in _RUNTIME_SCHEMAS:
        try:
            _validate_runtime(kind, data, Path(args.root).resolve())
        except ValueError:
            print("FAIL: RUNTIME_CONTRACT_INVALID")
            return 1
        print("PASS")
        return 0
    if kind == "execution-envelope" and data.get("contract_revision") == 2:
        assessment = assess_envelope(data, context)
        assessment["trust_root_id"] = context_identity(context)
        if args.json:
            _write(assessment, None, True)
        else:
            print("STRUCTURALLY_VALID" if assessment["structural_valid"] else "STRUCTURALLY_INVALID")
            print("SEMANTICALLY_VALID" if assessment["semantic_valid"] else "SEMANTICALLY_INVALID")
            print(assessment["readiness"])
            for reason in assessment["reason_codes"]:
                print(reason)
        if not assessment["semantic_valid"]:
            return 1
        return 0 if not args.require_ready or assessment["readiness"] == "EXECUTION_READY" else 1
    issues = contract_issues(kind, data, context.package_root)
    if issues:
        print(("UNVERIFIED: " if issues[0].severity == "UNVERIFIED" else "FAIL: ") + issues[0].code)
        return 1
    if kind == "execution-trace" and data.get("contract_revision") in {2, 3}:
        if not args.envelope:
            report = {"status": "INCOMPLETE", "reason_codes": ["EXACT_ENVELOPE_REQUIRED"]}
            _write(report, None, args.json)
            return 1 if args.require_ready else 0
        envelope = load_yaml(Path(args.envelope))
        raise_for_issues(contract_issues("execution-envelope", envelope, context.package_root))
        comparison = compare_execution(envelope, data, context)
        if data.get("read_identity_bindings") and not verify_trace_read_bindings(data, context):
            if comparison["status"] != "FAIL":
                comparison["status"] = "INCOMPLETE"
                comparison["conformance"] = "NOT_CERTIFIABLE"
            comparison.setdefault("missing_observations", []).append("historical_read_identity")
        if args.require_ready and assess_envelope(envelope, context)["readiness"] != "EXECUTION_READY":
            if comparison["status"] != "FAIL":
                comparison["status"] = "INCOMPLETE"
                comparison["conformance"] = "NOT_CERTIFIABLE"
            comparison.setdefault("missing_observations", []).append("envelope_readiness")
        _write(comparison, None, args.json)
        return 0 if comparison["status"] == "PASS" else 1
    if kind in {"execution-envelope", "execution-trace"} and "contract_version" not in data:
        print("LEGACY_VALID: v0 shape/semantics only; no R5 readiness")
    elif kind in {"execution-envelope", "execution-trace"} and data.get("contract_revision") is None:
        print("LEGACY_V1_UNVERIFIED: historical v1 revision 1; no R5 readiness")
        return 1 if args.require_ready else 0
    else:
        print("PASS")
    return 1 if args.require_ready else 0


def record(args) -> int:
    envelope = load_yaml(Path(args.envelope))
    actual = load_yaml(Path(args.actual))
    raise_for_issues(contract_issues("execution-envelope", envelope, schema_root()))
    if envelope.get("contract_version") != "execution-envelope/v1":
        raise ValueError("v0 envelopes are read-only; record requires v1")
    if envelope.get("contract_revision") != 2:
        raise ValueError("Historical v1 is read-only; record requires revision 2")
    context = VerificationContext.from_host(
        Path(args.root), schema_root(),
        Path(args.trust_context) if args.trust_context else None)
    trace = create_trace(envelope, actual, verification_context=context)
    raise_for_issues(contract_issues("execution-trace", trace, schema_root()))
    _write(trace, args.out, args.json)
    return 0


def compare(args) -> int:
    envelope = load_yaml(Path(args.envelope))
    trace = load_yaml(Path(args.trace))
    raise_for_issues(contract_issues("execution-envelope", envelope, schema_root()))
    raise_for_issues(contract_issues("execution-trace", trace, schema_root()))
    if envelope.get("contract_revision") != 2 or trace.get("contract_revision") not in {2, 3}:
        _write({"status": "INCOMPLETE", "reason_codes": ["LEGACY_CONTRACT_UNVERIFIED"]},
               None, args.json)
        return 1
    context = VerificationContext.from_host(
        Path(args.root), schema_root(),
        Path(args.trust_context) if args.trust_context else None)
    report = compare_execution(envelope, trace, context)
    if trace.get("read_identity_bindings"):
        if not verify_trace_read_bindings(trace, context):
            if report["status"] != "FAIL":
                report["status"] = "INCOMPLETE"
                report["conformance"] = "NOT_CERTIFIABLE"
            report.setdefault("missing_observations", []).append("historical_read_identity")
    _write(report, None, args.json)
    return 0 if report.get("status", "PASS") == "PASS" else 1


def resume(args) -> int:
    envelope = load_yaml(Path(args.envelope))
    raise_for_issues(contract_issues("execution-envelope", envelope, schema_root()))
    if envelope.get("contract_version") != "execution-envelope/v1":
        raise ValueError("v0 envelopes are read-only; resume-check requires v1")
    if envelope.get("contract_revision") != 2:
        _write({"status": "INCOMPLETE", "reason_codes": ["LEGACY_V1_UNVERIFIED"]},
               None, args.json)
        return 1
    handoff = load_yaml(Path(args.handoff))
    state = load_yaml(Path(args.state))
    verified_gates: set[str] = set()
    if envelope.get("contract_revision") == 2:
        raise_for_issues(contract_issues("handoff", handoff, schema_root()))
        context = VerificationContext.from_host(
            Path(args.root), schema_root(),
            Path(args.trust_context) if args.trust_context else None)
        assessment = assess_envelope(envelope, context)
        if assessment["readiness"] != "EXECUTION_READY":
            report = {"status": "FAIL", "reason_codes": [
                "ENVELOPE_NOT_EXECUTION_READY", *assessment["reason_codes"]]}
            _write(report, None, args.json)
            return 1
        verified_gates = {
            item["requirement_id"].removeprefix("gate:")
            for item in assessment["evidence_results"]
            if item["predicate"] == "HUMAN_APPROVAL" and item["state"] == "VERIFIED"
            and item["requirement_id"].startswith("gate:")
        }
        observed = verify_host_snapshot(
            context, "resume:state", material_digest(envelope), "RESUME_STATE",
            "project:" + envelope["project_id"], state)
        observed_handoff = verify_host_snapshot(
            context, "resume:handoff", material_digest(envelope), "HANDOFF_STATE",
            "project:" + envelope["project_id"], handoff)
        if observed.state != "VERIFIED" or observed_handoff.state != "VERIFIED":
            codes = []
            if observed.state != "VERIFIED":
                codes.append("RESUME_STATE_UNVERIFIED")
            if observed_handoff.state != "VERIFIED":
                codes.append("HANDOFF_STATE_UNVERIFIED")
            report = {"status": "INCOMPLETE", "reason_codes": codes}
            _write(report, None, args.json)
            return 1
        planned_model = envelope["intent"]["planned_model"]
        if planned_model is not None and state.get("model_id") != planned_model:
            report = {"status": "FAIL", "reason_codes": ["MODEL_MISMATCH"]}
            _write(report, None, args.json)
            return 1
    report = resume_check(envelope, handoff, state, verified_gates=verified_gates)
    _write(report, None, args.json)
    return 0 if report["status"] == "PASS" else 1


def harvest_scan(args) -> int:
    harvest = load_yaml(Path(args.harvest))
    manifests = [load_yaml(Path(path)) for path in args.manifests]
    _write(scan_harvest(harvest, manifests), args.out, args.json)
    return 0
