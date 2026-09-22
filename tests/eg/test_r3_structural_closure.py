"""Invariant matrices for the R3 semantic-contract kernel."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from noema.cli import main
from noema.eg.context_plan import ReadSet
from noema.eg.dogfood import render_dogfood_report
from noema.eg.plan import build_execution_envelope
from noema.eg.semantics import contract_issues, validate_metric_semantics, validate_resolver_receipt_semantics
from noema.eg.trace import create_trace
from noema.loader import dump_yaml
from noema.schemas import validation_errors


ROOT = Path(__file__).resolve().parents[2]


def work_order(**overrides) -> dict:
    data = {
        "work_order_id": "wo-r3", "project_id": "noema", "objective": "structural closure",
        "scope": {"allowed": ["src/noema"], "excluded": ["secrets"]}, "context_mode": "patch",
        "inputs": [], "capability_requirements": [], "allowed_writes": [], "forbidden_effects": [],
        "expected_artifacts": [], "quality_claims": ["contract-conformance"], "human_gates": [],
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("status,ref,unresolved,valid", [
    ("NOT_REQUIRED", None, [], True),
    ("RESOLVED", None, [], False),
    ("RESOLVED", {"scheme": "repo", "locator": "result.yaml"}, [], True),
    ("PARTIAL", None, ["capability"], False),
    ("PARTIAL", {"scheme": "repo", "locator": "result.yaml"}, [], False),
    ("PARTIAL", {"scheme": "repo", "locator": "result.yaml"}, ["capability"], True),
    ("UNRESOLVED", None, [], True),
    ("BLOCKED", None, [], True),
])
def test_r3_resolver_state_matrix(status, ref, unresolved, valid):
    receipt = {"resolver": "project:resolver", "status": status, "resolution_ref": ref, "unresolved_capabilities": unresolved}
    assert (not validate_resolver_receipt_semantics(receipt)) is valid


@pytest.mark.parametrize("status,value,methodology,valid", [
    ("UNAVAILABLE", None, None, True), ("UNAVAILABLE", 0, None, False),
    ("MEASURED", 0, None, True), ("MEASURED", 1.5, None, True),
    ("MEASURED", "1", None, False), ("MEASURED", True, None, False),
    ("MEASURED", None, None, False), ("MEASURED", math.nan, None, False),
    ("MEASURED", math.inf, None, False),
    ("ESTIMATED", 1, None, False),
    ("ESTIMATED", 1, {"scheme": "repo", "locator": "method.yaml"}, True),
])
def test_r3_metric_state_matrix(status, value, methodology, valid):
    metric = {"status": status, "value": value}
    if methodology is not None:
        metric["methodology_ref"] = methodology
    assert (not validate_metric_semantics(metric, "metric")) is valid


@pytest.mark.parametrize("pressure,metadata,expected", [
    ({"posture_hint": "BLOCKED", "block_all_external": True}, {}, "DIRECT_EXECUTION"),
    ({"posture_hint": "BLOCKED", "block_all_external": True}, {"tool_requirements": {"capabilities": ["read"]}}, "BLOCKED"),
    ({"posture_hint": "THROTTLED", "block_all_external": True}, {"tool_requirements": {"capabilities": ["read"]}}, "DEFER"),
    ({"posture_hint": "BLOCKED", "blocked_interfaces": ["github"]}, {"tool_requirements": {"interfaces": ["github"]}}, "BLOCKED"),
])
def test_r3_runtime_dependency_matrix(pressure, metadata, expected):
    env = build_execution_envelope(
        ROOT, work_order(), task_metadata=metadata,
        candidate_snapshot={"tools": [{"id": "reader", "capabilities": ["read"]}]},
        runtime_pressure=pressure,
    )
    assert env["disposition"] == expected
    assert not (expected == "BLOCKED" and any(item["decision"] == "CALL" for item in env["tool_decisions"]))


@pytest.mark.parametrize("first,second,suppressed", [
    ({"scheme": "repo", "locator": "a", "integrity": "one"}, {"scheme": "repo", "locator": "a", "integrity": "one"}, True),
    ({"scheme": "repo", "locator": "a", "integrity": "one"}, {"scheme": "repo", "locator": "a", "integrity": "two"}, False),
    ({"scheme": "repo", "locator": "a"}, {"scheme": "repo", "locator": "a"}, False),
    ({"scheme": "repo", "locator": "a", "integrity": "one"}, {"scheme": "repo", "locator": "b", "integrity": "one"}, False),
])
def test_r3_read_identity_matrix(first, second, suppressed):
    reads = ReadSet()
    reads.record(first)
    result = reads.record(second)
    assert (result["reason_code"] == "DUPLICATE_READ_SUPPRESSED") is suppressed
    if result["identity_kind"] != "UNKNOWN":
        assert result["identity_fingerprint"]


@pytest.mark.parametrize("bindings,scopes", [
    ([{"role_id": "a", "scope": ["src/a"]}, {"role_id": "b", "scope": ["src/a"]}], ["src/a", "src/a"]),
    ([{"role_id": "a", "scope": ["src/A"]}, {"role_id": "b", "scope": ["src/a"]}], ["src/A", "src/a"]),
    ([{"role_id": "a", "scope": ["src"]}, {"role_id": "b", "scope": ["src/noema"]}], ["src", "src/noema"]),
    ([{"role_id": "a", "scope": ["C:/a"]}, {"role_id": "b", "scope": ["src/b"]}], ["C:/a", "src/b"]),
])
def test_r3_public_validation_rejects_unprovable_parallel_topology(tmp_path, bindings, scopes):
    env = build_execution_envelope(ROOT, work_order())
    env["topology"] = {"mode": "PARALLEL_ISOLATED", "max_parallelism": 2, "role_bindings": bindings, "write_scopes": scopes}
    # This asserts the seam: structural JSON can be valid while the public
    # boundary rejects the same object for a semantic invariant.
    assert not validation_errors("execution-envelope", env, ROOT)
    path = tmp_path / "invalid-envelope.yaml"
    path.write_text(dump_yaml(env), encoding="utf-8")
    assert main(["eg", "validate", str(path), "--root", str(ROOT), "--kind", "execution-envelope"]) == 1


def test_r3_provenance_is_derived_and_trace_preserves_read_evidence():
    env = build_execution_envelope(ROOT, work_order(), work_order_ref="repo://caller-controlled.yaml")
    assert env["work_order_ref"]["scheme"] == "memory"
    assert env["work_order_ref"]["integrity"]
    trace = create_trace(env, {"context_reads": [
        {"ref": {"scheme": "repo", "locator": "a.md"}, "freshness": "etag-a"},
        {"ref": {"scheme": "repo", "locator": "a.md"}, "freshness": "etag-a"},
    ]})
    assert trace["actual"]["context_events"][1]["identity_fingerprint"]
    assert not contract_issues("execution-trace", trace, ROOT)


def test_r3_dogfood_report_is_rendered_from_machine_evidence():
    evidence_path = ROOT / "validation" / "experimental" / "execution-governance" / "CANARY_RESULTS.json"
    report_path = evidence_path.with_name("DOGFOOD_REPORT.md")
    results = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert render_dogfood_report(results) == report_path.read_text(encoding="utf-8")
