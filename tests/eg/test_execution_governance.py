from pathlib import Path

from noema.eg.context_plan import ReadSet
from noema.eg.plan import build_execution_envelope
from noema.eg.recovery import resume_check
from noema.eg.runtime import classify_runtime_posture, derive_resource_policy
from noema.eg.tooling import decide_tools
from noema.eg.trace import create_trace
from noema.schemas import validation_errors


ROOT = Path(__file__).resolve().parents[2]


def work_order():
    return {
        "work_order_id": "wo-eg-read", "project_id": "noema", "objective": "read known file",
        "scope": {"allowed": ["src/noema"], "excluded": []}, "context_mode": "patch",
        "allowed_writes": [], "forbidden_effects": [], "expected_artifacts": [],
        "quality_claims": ["contract-conformance"], "inputs": [],
    }


def test_direct_envelope_is_valid_and_skips_tool_routing():
    envelope = build_execution_envelope(
        ROOT, work_order(), work_order_ref="repo://tests/eg/work-order.yaml",
        candidate_snapshot={"tools": [{"id": "crawler", "capabilities": ["read"]}]},
    )
    assert envelope["disposition"] == "DIRECT_EXECUTION"
    assert envelope["tool_decisions"] == []
    assert not validation_errors("execution-envelope", envelope, ROOT)


def test_tool_selector_suppresses_broader_duplicate_source():
    decisions = decide_tools([
        {"id": "repo", "capabilities": ["read"], "source_relation": "DIRECT"},
        {"id": "crawler", "capabilities": ["read"], "source_relation": "BROAD"},
    ], {"capabilities": ["read"]})
    assert decisions[0]["decision"] == "CALL"
    assert decisions[1]["decision"] == "SOFT_SUPPRESS"


def test_read_set_and_runtime_pressure_are_conservative():
    read_set = ReadSet()
    ref = {"scheme": "repo", "locator": "PROTOCOL.md"}
    assert read_set.record(ref)["read"]
    assert read_set.record(ref)["reason_code"] == "DUPLICATE_READ_SUPPRESSED"
    posture = classify_runtime_posture({"posture_hint": "CONSERVE"})
    assert derive_resource_policy(posture)["optional_external_calls"] == "CONSERVE"


def test_resume_rejects_stale_sha():
    envelope = build_execution_envelope(ROOT, work_order(), work_order_ref="repo://tests/eg/work-order.yaml", baseline_sha="old")
    report = resume_check(envelope, {"work_order_ref": envelope["work_order_ref"], "status": "partial"}, "new")
    assert report["status"] == "FAIL"
    assert "STALE_SHA" in report["reason_codes"]


def test_trace_marks_missing_telemetry_unavailable():
    envelope = build_execution_envelope(ROOT, work_order(), work_order_ref="repo://tests/eg/work-order.yaml")
    trace = create_trace(envelope, {"metrics": {"context_units": 12}})
    assert trace["metrics"]["context_units"]["status"] == "OBSERVED"
    assert not validation_errors("execution-trace", trace, ROOT)
