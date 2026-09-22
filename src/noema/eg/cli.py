"""Thin command handlers for the experimental `noema eg` namespace."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator, FormatChecker

from ..loader import dump_yaml, load_json, load_yaml
from ..manifest import load_manifest
from ..schemas import schema_root
from .compare import compare_execution
from .plan import build_execution_envelope
from .provenance import load_work_order
from .profiles import load_host_capabilities
from .recovery import resume_check
from .runtime import classify_runtime_posture
from .scan import scan_harvest
from .trace import create_trace
from .semantics import contract_issues, raise_for_issues, validate_runtime_pressure_semantics


_RUNTIME_SCHEMAS = {
    "host-capabilities": "host-capabilities.v0.schema.json",
    "candidate-snapshot": "candidate-snapshot.v0.schema.json",
    "runtime-pressure": "runtime-pressure.v0.schema.json",
}


def _write(data: dict, output: str | None, as_json: bool) -> None:
    rendered = json.dumps(data, indent=2) if as_json else dump_yaml(data)
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
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
    )
    raise_for_issues(contract_issues("execution-envelope", envelope, schema_root(root)))
    _write(envelope, args.out, args.json)
    return 0


def explain(args) -> int:
    envelope = load_yaml(Path(args.envelope))
    _write({"execution_id": envelope.get("execution_id"), "disposition": envelope.get("disposition"), "reason_codes": envelope.get("reason_codes", []), "control": envelope.get("decision", {}).get("control")}, None, args.json)
    return 0


def validate(args) -> int:
    data = load_yaml(Path(args.path))
    kind = args.kind or ("execution-trace" if "trace_id" in data else "execution-envelope")
    if kind in _RUNTIME_SCHEMAS:
        try:
            _validate_runtime(kind, data, Path(args.root).resolve())
        except ValueError as exc:
            print("FAIL: " + str(exc))
            return 1
        print("PASS")
        return 0
    issues = contract_issues(kind, data, schema_root(Path(args.root).resolve()))
    if issues:
        print(("UNVERIFIED: " if issues[0].severity == "UNVERIFIED" else "FAIL: ") + issues[0].message)
        return 1
    if kind in {"execution-envelope", "execution-trace"} and "contract_version" not in data:
        print("LEGACY_VALID: v0 shape/semantics only; not R4 structural conformance")
    else:
        print("PASS")
    return 0


def record(args) -> int:
    envelope = load_yaml(Path(args.envelope))
    actual = load_yaml(Path(args.actual))
    raise_for_issues(contract_issues("execution-envelope", envelope, schema_root()))
    if envelope.get("contract_version") != "execution-envelope/v1":
        raise ValueError("v0 envelopes are read-only; record requires v1")
    trace = create_trace(envelope, actual)
    raise_for_issues(contract_issues("execution-trace", trace, schema_root()))
    _write(trace, args.out, args.json)
    return 0


def compare(args) -> int:
    _write(compare_execution(load_yaml(Path(args.envelope)), load_yaml(Path(args.trace))), None, args.json)
    return 0


def resume(args) -> int:
    envelope = load_yaml(Path(args.envelope))
    raise_for_issues(contract_issues("execution-envelope", envelope, schema_root()))
    if envelope.get("contract_version") != "execution-envelope/v1":
        raise ValueError("v0 envelopes are read-only; resume-check requires v1")
    report = resume_check(envelope, load_yaml(Path(args.handoff)), load_yaml(Path(args.state)))
    _write(report, None, args.json)
    return 0 if report["status"] == "PASS" else 1


def harvest_scan(args) -> int:
    harvest = load_yaml(Path(args.harvest))
    manifests = [load_yaml(Path(path)) for path in args.manifests]
    _write(scan_harvest(harvest, manifests), args.out, args.json)
    return 0
