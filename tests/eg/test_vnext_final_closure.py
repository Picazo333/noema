"""RED regressions for the frozen vNext final-closure gates."""

from __future__ import annotations

from copy import deepcopy
import json
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

import pytest

from noema.loader import dump_yaml, load_yaml
from noema.eg.persistence import project_r2_inputs
from noema.eg.semantics import contract_issues
from noema.eg.tooling import decide_tools
from noema.eg.context_plan import ReadSet
from noema.eg.plan import build_execution_envelope
from noema.eg.evaluation import derive_evaluation_constraints
from noema.eg.recovery import recovery_requirements
from noema.manifest import resolve_state_scope, state_scopes


ROOT = Path(__file__).resolve().parents[2]


def _invoke(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "noema", "eg", *map(str, args)],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def _write(root: Path, name: str, data: object) -> Path:
    path = root / name
    path.write_text(dump_yaml(data), encoding="utf-8")
    return path


def _order() -> dict:
    return {
        "work_order_id": "wo-final-closure", "project_id": "noema",
        "objective": "Inspect project state", "scope": {"allowed": ["src/noema"], "excluded": []},
        "context_mode": "patch", "inputs": [], "capability_requirements": [],
        "allowed_writes": [], "forbidden_effects": [], "expected_artifacts": [],
        "quality_claims": [], "human_gates": [],
    }


@pytest.mark.parametrize("category", ["tools", "models", "resources", "interfaces"])
@pytest.mark.parametrize("variant", ["exact", "contradictory", "reversed"])
def test_candidate_ids_are_unique_within_category(category: str, variant: str) -> None:
    first = {"id": "collision", "allowed": False}
    second = deepcopy(first) if variant == "exact" else {"id": "collision", "allowed": True}
    values = [second, first] if variant == "reversed" else [first, second]
    with pytest.raises(ValueError):
        project_r2_inputs({}, {category: values})


@pytest.mark.parametrize("category", ["tools", "models", "resources", "interfaces"])
@pytest.mark.parametrize("value", [{}, {"id": ""}, {"id": "   "}])
def test_candidate_id_is_required_and_nonempty(category: str, value: dict) -> None:
    with pytest.raises(ValueError):
        project_r2_inputs({}, {category: [value]})


def test_duplicate_yaml_mapping_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.yaml"
    path.write_text("outer:\n  id: first\n  id: second\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_yaml(path)


def test_candidate_collision_rejected_at_public_planning_and_validation(tmp_path: Path) -> None:
    snapshot = {"models": [{"id": "same", "qualification": "UNAVAILABLE"},
                           {"id": "same", "qualification": "VERIFIED"}]}
    candidate_path = _write(tmp_path, "candidates.yaml", snapshot)
    validated = _invoke("validate", candidate_path, "--kind", "candidate-snapshot", "--root", ROOT)
    assert validated.returncode != 0
    planned = _invoke("plan", _write(tmp_path, "order.yaml", _order()),
                      "--root", ROOT, "--candidate-snapshot", candidate_path,
                      "--out", tmp_path / "envelope.yaml")
    assert planned.returncode != 0
    assert not (tmp_path / "envelope.yaml").exists()


def test_handcrafted_envelope_cannot_bypass_candidate_identity(tmp_path: Path) -> None:
    output = tmp_path / "envelope.yaml"
    result = _invoke("plan", _write(tmp_path, "order.yaml", _order()),
                     "--root", ROOT, "--out", output)
    assert result.returncode == 0, result.stderr
    envelope = load_yaml(output)
    envelope["input_bindings"]["candidate_snapshot"]["snapshot"] = {
        "resources": [{"id": "same"}, {"id": "same"}]}
    problems = contract_issues("execution-envelope", envelope, ROOT)
    assert any(item.code == "EG-CANDIDATE-ID-DUPLICATE" for item in problems)


def test_programmatic_planning_cannot_bypass_candidate_identity() -> None:
    with pytest.raises(ValueError):
        build_execution_envelope(
            ROOT, _order(), candidate_snapshot={"tools": [{"id": "same"}, {"id": "same"}]}
        )


def test_no_tool_need_never_produces_call() -> None:
    candidates = [{"id": "broad", "allowed": True, "available": True,
                   "availability": "AVAILABLE", "qualification": "VERIFIED",
                   "capabilities": ["read"]}]
    decisions = decide_tools(candidates, {}, control="ALLOW")
    assert all(item["decision"] != "CALL" for item in decisions)


def test_public_non_tool_route_has_no_tool_call(tmp_path: Path) -> None:
    candidate = {"id": "reader", "allowed": True, "available": True,
                 "availability": "AVAILABLE", "qualification": "VERIFIED",
                 "capabilities": ["read"]}
    output = tmp_path / "envelope.yaml"
    result = _invoke("plan", _write(tmp_path, "order.yaml", _order()),
                     "--root", ROOT, "--task-metadata",
                     _write(tmp_path, "metadata.yaml", {"complex_context": True}),
                     "--candidate-snapshot",
                     _write(tmp_path, "candidates.yaml", {"tools": [candidate]}),
                     "--out", output)
    assert result.returncode == 0, result.stderr
    envelope = load_yaml(output)
    assert envelope["disposition"] == "ROUTED"
    assert all(item["decision"] != "CALL" for item in envelope["tool_decisions"])


def test_recover_command_reports_incomplete_without_checkpoint(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "noema.project.yaml").write_text(
        "project:\n  id: missing-checkpoint\nnoema:\n  protocol: '0.1'\n"
        "sources_of_truth:\n  state.execution: repo://state/execution-current.yaml\n",
        encoding="utf-8",
    )
    result = _invoke("recover", project, "--json")
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == "INCOMPLETE"


def _recovery_project(tmp_path: Path) -> tuple[Path, str]:
    project = tmp_path / "recovery-project"
    project.mkdir()
    (project / "state").mkdir()
    _write(project, "noema.project.yaml", {
        "project": {"id": "noema"},
        "sources_of_truth": {"state.execution": {
            "scheme": "repo", "locator": "state/execution-current.yaml"}},
    })
    _write(project, "work-order.yaml", _order())
    _write(project, "handoff.yaml", {
        "handoff_id": "handoff-final-closure", "work_order_ref": "repo://work-order.yaml",
        "status": "partial", "summary": "Ready for verification", "changes": [],
        "artifacts": [], "evidence": [], "remaining": [],
        "next_action": "Verify", "intentionally_unchanged": [], "decisions": [],
    })
    subprocess.run(["git", "init", "-q", project], check=True)
    subprocess.run(["git", "-C", str(project), "add", "."], check=True)
    subprocess.run(["git", "-C", str(project), "-c", "user.name=Noema Test",
                    "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"], check=True)
    sha = subprocess.check_output(["git", "-C", str(project), "rev-parse", "HEAD"], text=True).strip()
    branch = subprocess.check_output(["git", "-C", str(project), "branch", "--show-current"], text=True).strip()
    _write(project / "state", "execution-current.yaml", {
        "project_id": "noema", "role_id": "verifier", "branch": branch,
        "workspace": str(project), "sha": sha, "frontier_ref": None,
        "closed_claims": [], "closed_evidence_refs": [], "active_blockers": [],
        "outstanding_human_gates": [], "prohibited_scope": [],
        "effective_allowed_writes": [], "next_action": "Verify",
        "next_action_kind": "VERIFY", "handoff_ref": {
            "scheme": "repo", "locator": "handoff.yaml"}, "envelope_ref": None,
    })
    return project, sha


def test_scoped_state_cursor_and_recovery_without_transcript(tmp_path: Path) -> None:
    project, sha = _recovery_project(tmp_path)
    manifest = load_yaml(project / "noema.project.yaml")
    assert state_scopes(manifest) == ("execution",)
    assert resolve_state_scope(project, manifest, "execution") == project / "state/execution-current.yaml"
    recovered = _invoke("recover", project, "--last-seen-sha", sha, "--json")
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    report = json.loads(recovered.stdout)
    assert report["session_freshness"] == "CURRENT"
    assert report["context_plan"]["mode"] == "recover"
    assert report["checkpoint_ready"] is True
    assert len(report["context_plan"]["refs"]) == 4
    assert report["decision_ids"] == []


@pytest.mark.parametrize("foreign_checkpoint", [False, True])
def test_recover_project_identity_bound_to_manifest(
    tmp_path: Path, foreign_checkpoint: bool,
) -> None:
    project, _ = _recovery_project(tmp_path)
    order_path = project / "work-order.yaml"
    order = load_yaml(order_path)
    order["project_id"] = "foreign-project"
    order_path.write_text(dump_yaml(order), encoding="utf-8")
    if foreign_checkpoint:
        checkpoint = project / "state/execution-current.yaml"
        state = load_yaml(checkpoint)
        state["project_id"] = "foreign-project"
        checkpoint.write_text(dump_yaml(state), encoding="utf-8")

    result = _invoke("recover", project, "--json")
    report = json.loads(result.stdout)
    assert result.returncode != 0
    assert report["status"] != "PASS"
    assert report["continuation"] != "PASS"
    assert "RECOVERY_PROJECT_MISMATCH" in report["reason_codes"]


@pytest.mark.parametrize("scope", [
    "C:/outside-project", "C:\\outside-project", "D:/other",
    "\\\\server\\share", "//server/share", "/outside-project",
    "../outside", "src/../../outside",
])
def test_recover_rejects_non_project_relative_write_scope(
    tmp_path: Path, scope: str,
) -> None:
    project, _ = _recovery_project(tmp_path)
    order_path = project / "work-order.yaml"
    order = load_yaml(order_path)
    order["allowed_writes"] = [scope]
    order_path.write_text(dump_yaml(order), encoding="utf-8")
    checkpoint = project / "state/execution-current.yaml"
    state = load_yaml(checkpoint)
    state["effective_allowed_writes"] = [scope]
    checkpoint.write_text(dump_yaml(state), encoding="utf-8")

    result = _invoke("recover", project, "--json")
    report = json.loads(result.stdout)
    assert result.returncode != 0
    assert report["status"] != "PASS"
    assert report["continuation"] != "PASS"
    assert "RECOVERY_SCOPE_INVALID" in report["reason_codes"]


@pytest.mark.parametrize("scope", ["src", "src/noema", "validation/process-audits"])
def test_recover_accepts_authorized_relative_write_scope(tmp_path: Path, scope: str) -> None:
    project, _ = _recovery_project(tmp_path)
    order_path = project / "work-order.yaml"
    order = load_yaml(order_path)
    order["allowed_writes"] = [scope]
    order_path.write_text(dump_yaml(order), encoding="utf-8")
    checkpoint = project / "state/execution-current.yaml"
    state = load_yaml(checkpoint)
    state["effective_allowed_writes"] = [scope]
    checkpoint.write_text(dump_yaml(state), encoding="utf-8")

    result = _invoke("recover", project, "--json")
    report = json.loads(result.stdout)
    assert result.returncode == 0, result.stdout + result.stderr
    assert report["status"] == "PASS"
    assert report["continuation"] == "PASS"


def test_stale_session_and_checkpoint_fail_closed(tmp_path: Path) -> None:
    project, sha = _recovery_project(tmp_path)
    stale_session = _invoke("recover", project, "--last-seen-sha", "0" * 40, "--json")
    assert stale_session.returncode != 0
    assert json.loads(stale_session.stdout)["session_freshness"] == "STALE"
    checkpoint = project / "state/execution-current.yaml"
    state = load_yaml(checkpoint)
    state["sha"] = "f" * 40
    checkpoint.write_text(dump_yaml(state), encoding="utf-8")
    stale = _invoke("recover", project, "--last-seen-sha", sha, "--json")
    assert stale.returncode != 0
    assert json.loads(stale.stdout)["status"] == "STALE_CHECKPOINT"
    assert json.loads(stale.stdout)["checkpoint_ready"] is False


def test_recover_preserves_human_gate(tmp_path: Path) -> None:
    project, _ = _recovery_project(tmp_path)
    checkpoint = project / "state/execution-current.yaml"
    state = load_yaml(checkpoint)
    state["outstanding_human_gates"] = ["independent-audit"]
    checkpoint.write_text(dump_yaml(state), encoding="utf-8")
    recovered = _invoke("recover", project, "--json")
    assert recovered.returncode != 0
    report = json.loads(recovered.stdout)
    assert report["continuation"] != "PASS"
    assert "OUTSTANDING_HUMAN_GATES" in report["reason_codes"]


def test_recover_cannot_drop_work_order_gate_or_widen_writes(tmp_path: Path) -> None:
    project, _ = _recovery_project(tmp_path)
    order_path = project / "work-order.yaml"
    work_order = load_yaml(order_path)
    work_order["human_gates"] = ["approval"]
    work_order["allowed_writes"] = ["src/noema"]
    order_path.write_text(dump_yaml(work_order), encoding="utf-8")
    checkpoint = project / "state/execution-current.yaml"
    state = load_yaml(checkpoint)
    state["effective_allowed_writes"] = ["src"]
    checkpoint.write_text(dump_yaml(state), encoding="utf-8")
    recovered = _invoke("recover", project, "--json")
    assert recovered.returncode != 0
    codes = json.loads(recovered.stdout)["reason_codes"]
    assert "HUMAN_GATE_DROPPED_WITHOUT_EVIDENCE" in codes
    assert "EFFECTIVE_WRITES_BROADENED" in codes


@pytest.mark.parametrize("mutation,expected", [
    ({"branch": "other-branch"}, "STALE_CHECKPOINT"),
    ({"sha": None}, "INCOMPLETE"),
    ({"handoff_ref": {"scheme": "repo", "locator": "absent.yaml"}}, "INCOMPLETE"),
    ({"handoff_ref": {"scheme": "file", "locator": "C:/outside.yaml"}}, "INCOMPLETE"),
    ({"next_action_kind": "EXECUTE"}, "INCOMPLETE"),
])
def test_recovery_missing_or_stale_material_fails_closed(
    tmp_path: Path, mutation: dict, expected: str,
) -> None:
    project, _ = _recovery_project(tmp_path)
    checkpoint = project / "state/execution-current.yaml"
    state = load_yaml(checkpoint)
    state.update(mutation)
    checkpoint.write_text(dump_yaml(state), encoding="utf-8")
    result = _invoke("recover", project, "--json")
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["status"] == expected
    assert report["continuation"] != "PASS"


def test_invalid_state_scope_is_rejected() -> None:
    for name in ("state", "state.Execution", "state.bad scope", "State.execution"):
        with pytest.raises(ValueError):
            state_scopes({"sources_of_truth": {name: {"scheme": "repo", "locator": "x"}}})


def test_state_ref_alone_does_not_prove_session_freshness(tmp_path: Path) -> None:
    project, _ = _recovery_project(tmp_path)
    result = _invoke("recover", project, "--last-seen-state-ref",
                     "repo://state/execution-current.yaml", "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout)["session_freshness"] == "UNKNOWN"


@pytest.mark.parametrize("level,recommendation", [
    ("LOW", "CONTINUE"), ("MODERATE", "CONTINUE"),
    ("HIGH", "PREPARE_NEW_SESSION"), ("CRITICAL", "MIGRATE_NOW"),
])
def test_context_pressure_is_advisory(tmp_path: Path, level: str, recommendation: str) -> None:
    project, _ = _recovery_project(tmp_path)
    pressure = _write(tmp_path, "pressure.yaml", {"context_pressure": level})
    result = _invoke("recover", project, "--runtime-pressure", pressure, "--json")
    assert result.returncode == 0
    assert json.loads(result.stdout)["context_pressure"]["recommendation"] == recommendation
    assert json.loads(result.stdout)["checkpoint_ready"] is True


def test_proven_repeat_read_and_broader_candidate_are_suppressed() -> None:
    ref = {"scheme": "repo", "locator": "PROTOCOL.md",
           "integrity": "sha256:" + sha256((ROOT / "PROTOCOL.md").read_bytes()).hexdigest()}
    reads = ReadSet()
    assert reads.record(ref)["read"] is True
    assert reads.record(ref)["read"] is False
    base = {"allowed": True, "available": True, "availability": "AVAILABLE",
            "qualification": "VERIFIED", "capabilities": ["read"]}
    decisions = decide_tools([
        {**base, "id": "direct", "source_relation": "DIRECT"},
        {**base, "id": "broad", "source_relation": "BROAD"},
    ], {"capabilities": ["read"]})
    assert [item["decision"] for item in decisions] == ["CALL", "SOFT_SUPPRESS"]


def test_role_executor_model_and_independent_review_remain_distinct() -> None:
    requirements = recovery_requirements(
        _order(), "a" * 40, {"role_id": "producer"}, effective_executor="executor-a"
    )
    assert requirements["expected_role"] == "producer"
    assert requirements["expected_executor"] == "executor-a"
    assert "model_id" not in requirements
    before = derive_evaluation_constraints(_order(), {"independent_review_required": True})
    after_model_change = derive_evaluation_constraints(
        _order(), {"independent_review_required": True,
                   "model_requirements": {"modalities": ["text"]}}
    )
    assert before["independent_review_required"] is True
    assert after_model_change["independent_review_required"] is True
