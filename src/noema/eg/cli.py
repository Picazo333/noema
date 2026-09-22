"""Thin command handlers for the experimental `noema eg` namespace."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from ..loader import dump_yaml, load_yaml
from ..manifest import load_manifest
from ..schemas import schema_root, validation_errors
from .compare import compare_execution
from .plan import build_execution_envelope
from .profiles import load_host_capabilities
from .recovery import resume_check
from .runtime import classify_runtime_posture
from .scan import scan_harvest
from .trace import create_trace


def _write(data: dict, output: str | None, as_json: bool) -> None:
    rendered = json.dumps(data, indent=2) if as_json else dump_yaml(data)
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="" if rendered.endswith("\n") else "\n")


def doctor(args) -> int:
    root = Path(args.root).resolve()
    manifest = load_manifest(root)
    host = load_host_capabilities(Path(args.host_capabilities) if args.host_capabilities else None, args.profile)
    posture = classify_runtime_posture(load_yaml(Path(args.runtime_pressure)) if args.runtime_pressure else None)
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
    work_order_path = Path(args.work_order)
    work_order = load_yaml(work_order_path)
    host = load_host_capabilities(Path(args.host_capabilities) if args.host_capabilities else None, args.profile)
    candidates = load_yaml(Path(args.candidate_snapshot)) if args.candidate_snapshot else None
    pressure = load_yaml(Path(args.runtime_pressure)) if args.runtime_pressure else None
    receipts = [load_yaml(Path(item)) for item in args.resolver_receipt]
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        sha = None
    envelope = build_execution_envelope(
        root, work_order, work_order_ref={"scheme": "file", "locator": str(work_order_path)},
        profile=args.profile, host_capabilities=host, candidate_snapshot=candidates,
        runtime_pressure=pressure, resolver_receipts=receipts, baseline_sha=sha,
    )
    errors = validation_errors("execution-envelope", envelope, schema_root(root))
    if errors:
        raise ValueError("Generated invalid ExecutionEnvelope: " + errors[0].message)
    _write(envelope, args.out, args.json)
    return 0


def explain(args) -> int:
    envelope = load_yaml(Path(args.envelope))
    _write({"execution_id": envelope.get("execution_id"), "disposition": envelope.get("disposition"), "reason_codes": envelope.get("reason_codes", []), "control": envelope.get("decision", {}).get("control")}, None, args.json)
    return 0


def validate(args) -> int:
    data = load_yaml(Path(args.path))
    kind = args.kind or ("execution-trace" if "trace_id" in data else "execution-envelope")
    errors = validation_errors(kind, data, schema_root())
    if errors:
        print("FAIL: " + errors[0].message)
        return 1
    print("PASS")
    return 0


def record(args) -> int:
    envelope = load_yaml(Path(args.envelope))
    actual = load_yaml(Path(args.actual))
    trace = create_trace(envelope, actual)
    errors = validation_errors("execution-trace", trace, schema_root())
    if errors:
        raise ValueError("Generated invalid ExecutionTrace: " + errors[0].message)
    _write(trace, args.out, args.json)
    return 0


def compare(args) -> int:
    _write(compare_execution(load_yaml(Path(args.envelope)), load_yaml(Path(args.trace))), None, args.json)
    return 0


def resume(args) -> int:
    envelope = load_yaml(Path(args.envelope))
    current_sha = None
    try:
        current_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(args.root), text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    report = resume_check(envelope, load_yaml(Path(args.handoff)), current_sha)
    _write(report, None, args.json)
    return 0 if report["status"] == "PASS" else 1


def harvest_scan(args) -> int:
    harvest = load_yaml(Path(args.harvest))
    manifests = [load_yaml(Path(path)) for path in args.manifests]
    _write(scan_harvest(harvest, manifests), args.out, args.json)
    return 0
