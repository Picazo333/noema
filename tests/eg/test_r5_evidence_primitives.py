"""G0/G2 positive evidence paths using the production verifier."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from copy import deepcopy
import json
import subprocess

import pytest

from noema.eg.bindings import gate_fingerprint, material_digest
from noema.eg.bindings import FIELD_CLASS
from noema.eg.compare import _dimension, evaluate_material_coverage, expected_observations
from noema.eg.evidence import VerificationContext, verify_assertion, verify_content
from noema.eg.persistence import assert_persistable
from noema.eg.plan import build_execution_envelope
from noema.eg import dogfood
from noema.loader import dump_yaml
from noema.loader import load_json


def _t1_script():
    import importlib.util

    path = ROOT / ".github" / "scripts" / "verify_t1.py"
    spec = importlib.util.spec_from_file_location("noema_verify_t1", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[2]


def order() -> dict:
    return {
        "work_order_id": "wo-r5-trust", "project_id": "noema", "objective": "Read",
        "scope": {"allowed": ["src/noema"], "excluded": []}, "context_mode": "patch",
        "inputs": [], "capability_requirements": [], "allowed_writes": [],
        "forbidden_effects": [], "expected_artifacts": [], "quality_claims": [],
        "human_gates": ["review"],
    }


def r2_envelope() -> dict:
    envelope = build_execution_envelope(ROOT, order())
    envelope["contract_revision"] = 2
    envelope["intent"] = {
        "attempt_id": "attempt-1", "action_id": "action-1", "action_effect": "READ",
        "target_ref": None, "planned_executor": None, "planned_model": None,
        "planned_tools": [], "planned_topology": envelope["topology"],
    }
    envelope["verification_requirements"] = []
    envelope["evidence_bindings"] = []
    envelope["material_binding"] = {"algorithm": "EG-C14N-1", "digest": ""}
    envelope["material_binding"]["digest"] = material_digest(envelope)
    return envelope


def test_observed_bytes_verify_only_content(tmp_path: Path) -> None:
    path = tmp_path / "observed.txt"
    path.write_bytes(b"observed bytes")
    expected = "sha256:" + sha256(b"observed bytes").hexdigest()
    checked = verify_content(path, expected, "file", "file:observed")
    assert checked.predicate == "CONTENT_INTEGRITY"
    assert checked.state == "VERIFIED"
    path.write_bytes(b"changed bytes")
    assert verify_content(path, expected, "file", "file:observed").state == "INVALID"


def test_independent_approval_and_external_projection(tmp_path: Path) -> None:
    envelope = r2_envelope()
    gate_subject = gate_fingerprint(envelope, "review")
    tool_subject = "tool:reader:repo-read"
    sources = []
    refs = {}
    for name, predicate, subject, authority, decision in (
        ("approval", "HUMAN_APPROVAL", gate_subject, "operator", "APPROVED"),
        ("qualification", "TOOL_QUALIFICATION", tool_subject, "external-fixture", "VERIFIED"),
    ):
        assertion = {"predicate": predicate, "subject": subject, "scope": "project:noema",
                     "authority": authority, "decision": decision}
        path = tmp_path / f"{name}.yaml"
        path.write_text(dump_yaml(assertion), encoding="utf-8")
        ref = {"scheme": "file", "locator": str(path)}
        refs[name] = ref
        sources.append({"ref": ref, "digest": "sha256:" + sha256(path.read_bytes()).hexdigest(),
                        "predicate": predicate, "subject": subject, "scope": "project:noema",
                        "authority": authority, "valid_until": "2099-01-01T00:00:00Z"})
    context_path = tmp_path / "host-context.yaml"
    context_path.write_text(dump_yaml({"sources": sources}), encoding="utf-8")
    context = VerificationContext.from_host(ROOT, ROOT, context_path)
    assert verify_assertion(context, "review", gate_subject, "HUMAN_APPROVAL",
                            "project:noema", refs["approval"]).state == "VERIFIED"
    assert verify_assertion(context, "reader", tool_subject, "TOOL_QUALIFICATION",
                            "project:noema", refs["qualification"]).state == "VERIFIED"
    assert verify_assertion(context, "review", "wrong-action", "HUMAN_APPROVAL",
                            "project:noema", refs["approval"]).state == "UNVERIFIED"
    assert verify_assertion(context, "reader", "tool:other:repo-read", "TOOL_QUALIFICATION",
                            "project:noema", refs["qualification"]).state == "UNVERIFIED"
    assert verify_assertion(VerificationContext.from_host(ROOT, ROOT), "review",
                            gate_subject, "HUMAN_APPROVAL", "project:noema").state == "UNVERIFIED"


def test_persistence_rejects_defined_credential_families() -> None:
    for value in (
        {"refresh_token": "marker"},
        {"reason_codes": ["Authorization: Bearer marker123"]},
        {"ref": {"scheme": "https", "locator": "example.invalid/e?cookie=marker"}},
        {"nested": [{"id_token": "marker"}]},
    ):
        try:
            assert_persistable(value)
        except ValueError:
            continue
        raise AssertionError("credential-like value passed the EG firewall")


def test_revision_2_schema_fields_are_explicitly_classified() -> None:
    schema = load_json(ROOT / "schemas" / "execution-envelope" / "v1-r2.schema.json")
    assert set(schema["properties"]) == set(FIELD_CLASS)
    assert set(schema["required"]) == set(FIELD_CLASS)
    assert set(FIELD_CLASS.values()) == {"MATERIAL", "EVIDENCE", "DERIVED", "NON_MATERIAL"}
    assert FIELD_CLASS["decision"] == "MATERIAL"
    assert FIELD_CLASS["intent"] == "MATERIAL"
    assert FIELD_CLASS["material_binding"] == "DERIVED"
    assert FIELD_CLASS["evidence_bindings"] == "EVIDENCE"


def test_material_digest_covers_every_classified_material_field() -> None:
    envelope = r2_envelope()
    baseline = material_digest(envelope)
    for field, category in FIELD_CLASS.items():
        changed = deepcopy(envelope)
        value = changed[field]
        if field == "contract_revision":
            changed[field] = 3
            try:
                material_digest(changed)
            except ValueError:
                continue
            raise AssertionError("unknown revision accepted")
        if field == "decision":
            value["action_effect"] = "r5-test-marker"
        elif field == "executor":
            value["selected_executor"] = "r5-test-marker"
        elif field == "model":
            value["selected_model"] = "r5-test-marker"
        elif isinstance(value, dict):
            value["r5-test-marker"] = True
        elif isinstance(value, list):
            value.append("r5-test-marker")
        else:
            changed[field] = "r5-test-marker"
        if category == "MATERIAL":
            assert material_digest(changed) != baseline, field
        else:
            assert material_digest(changed) == baseline, field


@pytest.mark.parametrize("exit_code,output", [
    (1, "1 failed"), (0, "1 passed, 1 skipped"),
    (0, "no tests ran"), (2, "ERROR collecting test.py"),
])
def test_canary_runner_never_passes_failed_skipped_or_empty_required_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int, output: str,
) -> None:
    sha = "a" * 40
    definitions = tmp_path / "definitions.json"
    definitions.write_text(json.dumps({"suite": "R5", "canaries": [{
        "id": "case", "scenario": "fixture", "level": "END_TO_END",
        "public_entrypoint": "python -m noema eg validate", "evidence": "test.py::test_case",
        "expected": "PASS",
    }]}), encoding="utf-8")
    monkeypatch.setattr(dogfood, "_git", lambda root, *args: sha if args[-1] == "HEAD" else "")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "-c" in command:
            return subprocess.CompletedProcess(command, 0,
                stdout=str(ROOT / "src" / "noema" / "__init__.py") + "\n", stderr="")
        return subprocess.CompletedProcess(command, exit_code, stdout=output, stderr="")

    monkeypatch.setattr(dogfood.subprocess, "run", fake_run)
    report = dogfood.run_dogfood(ROOT, definitions, tmp_path / "results", sha)
    assert report["status"] == "FAIL"
    assert (tmp_path / "results" / "CANARY_RESULTS.json").exists()


def test_canary_runner_rejects_wrong_sha_and_zero_cases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    definitions = tmp_path / "definitions.json"
    definitions.write_text('{"canaries": []}', encoding="utf-8")
    monkeypatch.setattr(dogfood, "_git", lambda root, *args: "a" * 40 if args[-1] == "HEAD" else "")
    with pytest.raises(ValueError, match="SHA"):
        dogfood.run_dogfood(ROOT, definitions, tmp_path / "results", "b" * 40)
    with pytest.raises(ValueError, match="At least one"):
        dogfood.run_dogfood(ROOT, definitions, tmp_path / "results", "a" * 40)


def test_canary_runner_rejects_import_outside_checkout_and_tree_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sha = "a" * 40
    definitions = tmp_path / "definitions.json"
    definitions.write_text(json.dumps({"canaries": [{
        "id": "case", "scenario": "fixture", "level": "END_TO_END",
        "public_entrypoint": "python -m noema eg validate", "evidence": "test.py::test_case",
        "expected": "PASS",
    }]}), encoding="utf-8")
    monkeypatch.setattr(dogfood, "_git", lambda root, *args: sha if args[-1] == "HEAD" else "")
    monkeypatch.setattr(dogfood.subprocess, "run", lambda command, **kwargs:
        subprocess.CompletedProcess(command, 0, stdout=str(tmp_path / "foreign.py"), stderr=""))
    with pytest.raises(ValueError, match="import"):
        dogfood.run_dogfood(ROOT, definitions, tmp_path / "results", sha)
    calls = 0

    def changing_git(root: Path, *args: str) -> str:
        nonlocal calls
        if args[-1] == "HEAD":
            return sha
        calls += 1
        return "" if calls == 1 else " M changed.py"

    monkeypatch.setattr(dogfood, "_git", changing_git)

    def good_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        output = (str(ROOT / "src" / "noema" / "__init__.py") + "\n"
                  if "-c" in command else "1 passed")
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    monkeypatch.setattr(dogfood.subprocess, "run", good_run)
    report = dogfood.run_dogfood(ROOT, definitions, tmp_path / "results", sha)
    assert report["status"] == "FAIL"
    assert report["canaries"][0]["reason_codes"] == ["TREE_MUTATION"]


def test_t1_junit_summary_rejects_missing_zero_skip_xfail_and_failure(tmp_path: Path) -> None:
    gate = _t1_script()
    xml = tmp_path / "results.xml"
    assert gate._junit_summary(xml, 0)["status"] == "FAIL"
    xml.write_text("<testsuite/>", encoding="utf-8")
    assert gate._junit_summary(xml, 0)["status"] == "FAIL"
    xml.write_text('<testsuite><testcase name="one"><skipped type="pytest.xfail"/></testcase></testsuite>', encoding="utf-8")
    assert gate._junit_summary(xml, 0)["status"] == "FAIL"
    xml.write_text('<testsuite><testcase name="one"><failure/></testcase></testsuite>', encoding="utf-8")
    assert gate._junit_summary(xml, 0)["status"] == "FAIL"
    xml.write_text('<testsuite><testcase name="one"/></testsuite>', encoding="utf-8")
    assert gate._junit_summary(xml, 1)["status"] == "FAIL"
    assert gate._junit_summary(xml, 0)["status"] == "PASS"


def test_t1_checkout_import_and_result_gate_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gate = _t1_script()
    sha = "a" * 40
    monkeypatch.setattr(gate, "_git", lambda root, *args: "b" * 40 if args[-1] == "HEAD" else "")
    with pytest.raises(ValueError, match="SHA mismatch"):
        gate.verify_checkout(ROOT, sha)
    monkeypatch.setattr(gate.subprocess, "run", lambda command, **kwargs:
        subprocess.CompletedProcess(command, 0, stdout=json.dumps([str(tmp_path / "foreign.py")]), stderr=""))
    with pytest.raises(ValueError, match="outside"):
        gate.verify_imports(ROOT, {})
    results = tmp_path / "results"
    results.mkdir()
    definitions = json.loads((ROOT / "validation/experimental/execution-governance/R5_CANARY_DEFINITIONS.json").read_text(encoding="utf-8"))
    rows = [{**case, "status": "PASS", "observed": "PASS", "sha": sha,
             "exit_code": 0, "test_counts": {"passed": 1, "failed": 0, "errors": 0, "skipped": 0}}
            for case in definitions["canaries"]]
    (results / "CANARY_RESULTS.json").write_text(json.dumps({"tested_sha": sha, "status": "PASS", "canaries": rows}), encoding="utf-8")
    (results / "DOGFOOD_REPORT.md").write_text("Observed", encoding="utf-8")
    assert gate.validate_results(ROOT, results, sha)["passed"] == 32
    rows[0]["status"] = "FAIL"
    (results / "CANARY_RESULTS.json").write_text(json.dumps({"tested_sha": sha, "status": "PASS", "canaries": rows}), encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete or failed"):
        gate.validate_results(ROOT, results, sha)

    old_root = tmp_path / "old-checkout"
    old_definitions = old_root / "validation" / "experimental" / "execution-governance" / "R5_CANARY_DEFINITIONS.json"
    old_definitions.parent.mkdir(parents=True)
    old_definitions.write_text(json.dumps({"canaries": definitions["canaries"][:-1]}), encoding="utf-8")
    with pytest.raises(ValueError, match="absent or duplicated"):
        gate.validate_results(old_root, results, sha)
    rows[0]["status"] = "PASS"
    rows[-1] = rows[0]
    (results / "CANARY_RESULTS.json").write_text(json.dumps({"tested_sha": sha, "status": "PASS", "canaries": rows}), encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete or failed"):
        gate.validate_results(ROOT, results, sha)


def test_final_repeated_tool_occurrences_require_distinct_exact_refs() -> None:
    envelope = r2_envelope()
    envelope["input_bindings"]["candidate_snapshot"]["snapshot"] = {
        "tools": [{"id": "reader", "capabilities": ["read"]}]
    }
    decision = {"candidate": "reader", "decision": "CALL"}
    envelope["tool_decisions"] = [decision, deepcopy(decision)]
    expected = expected_observations(envelope)["tools"]
    assert len(expected) == 2
    assert expected[0]["obligation_ref"] != expected[1]["obligation_ref"]
    event = {"candidate": "reader", "action": "CALL", "result": "SUCCESS"}
    first = {**event, "obligation_ref": expected[0]["obligation_ref"]}
    second = {**event, "obligation_ref": expected[1]["obligation_ref"]}
    cases = (
        ([first, second], "COMPLETE", 2, 0, 0),
        ([second, first], "COMPLETE", 2, 0, 0),
        ([first], "INCOMPLETE", 1, 1, 0),
        ([event, event], "INCOMPLETE", 0, 2, 2),
        ([first, first], "INCOMPLETE", 1, 2, 0),
    )
    for events, status, matched, missing, unexpected in cases:
        coverage, _ = _dimension(expected, events, "tools", 3)
        assert coverage["status"] == status
        assert len(coverage["matched"]) == matched
        assert len(coverage["missing"]) == missing
        assert len(coverage["unexpected"]) == unexpected
    duplicate, deviations = _dimension(expected, [first, first], "tools", 3)
    assert duplicate["duplicates"] == [first["obligation_ref"]]
    assert "DUPLICATE_OBLIGATION_OBSERVATION" in deviations
    wrong_name, deviations = _dimension(expected, [{**first, "candidate": "other"}, second], "tools", 3)
    assert wrong_name["status"] == "INCOMPLETE"
    assert "TOOL_BINDING_MISMATCH" in deviations
    legacy, _ = _dimension(expected, [event], "tools", 2)
    assert legacy["status"] == "INCOMPLETE"


def test_final_original_tool_event_index_survives_nonexecutable_filter() -> None:
    envelope = r2_envelope()
    envelope["tool_decisions"] = [{"candidate": "suppressed", "decision": "SOFT_SUPPRESS"}]
    trace = {"contract_revision": 3, "actual": {"tool_events": [
        {"candidate": "suppressed", "action": "SOFT_SUPPRESS", "result": "NOT_CALLED"},
        {"candidate": "rogue", "action": "CALL", "result": "SUCCESS"},
    ]}}
    coverage, deviations = evaluate_material_coverage(envelope, trace)
    assert coverage["tools"]["unexpected"] == [1]
    assert "UNPLANNED_TOOL_CALL" in deviations


def test_final_actor_occurrence_binding_and_absence_are_explicit() -> None:
    envelope = r2_envelope()
    envelope["topology"]["role_bindings"] = [{
        "role_id": "builder", "workspace": "work", "branch": "topic", "scope": ["src"]
    }]
    expected = expected_observations(envelope)["actors"]
    ref = expected[0]["obligation_ref"]
    actor = {**expected[0]["binding"], "participation": "REPORTED_EXECUTED"}
    complete, deviations = _dimension(expected, [{**actor, "obligation_ref": ref}], "actors", 3)
    assert complete["status"] == "COMPLETE" and not deviations
    unbound, deviations = _dimension(expected, [actor], "actors", 3)
    assert unbound["missing"] == [ref] and unbound["unexpected"] == [0]
    assert "ACTOR_OBLIGATION_UNBOUND" in deviations
    wrong, deviations = _dimension(expected, [{**actor, "obligation_ref": "sha256:" + "f" * 64}], "actors", 3)
    assert wrong["missing"] == [ref] and wrong["unexpected"] == [0]
    assert "UNEXPECTED_ACTOR" in deviations
    duplicate, deviations = _dimension(expected, [{**actor, "obligation_ref": ref}] * 2, "actors", 3)
    assert duplicate["status"] == "INCOMPLETE"
    assert duplicate["duplicates"] == [ref]
    assert "DUPLICATE_OBLIGATION_OBSERVATION" in deviations
    absent, deviations = _dimension(expected, [{**actor, "obligation_ref": ref,
                                                 "participation": "REPORTED_NOT_EXECUTED"}], "actors", 3)
    assert absent["explicitly_absent"] == [ref] and absent["status"] == "COMPLETE"
    assert "EXPECTED_ACTOR_NOT_EXECUTED" in deviations


@pytest.mark.parametrize("field,wrong_value", [
    ("workspace", "other-work"),
    ("branch", "other-topic"),
    ("scope", ["other"]),
    ("executor_id", "other-executor"),
    ("model_id", "other-model"),
])
def test_actor_absence_preserves_material_binding_mismatch(field: str, wrong_value: object) -> None:
    envelope = r2_envelope()
    envelope["topology"]["role_bindings"] = [{
        "role_id": "builder", "workspace": "work", "branch": "topic",
        "scope": ["src"], "executor_id": "executor", "model_id": "model",
    }]
    expected = expected_observations(envelope)["actors"]
    ref = expected[0]["obligation_ref"]
    actor = {**expected[0]["binding"], "obligation_ref": ref,
             "participation": "REPORTED_NOT_EXECUTED", field: wrong_value}
    coverage, deviations = _dimension(expected, [actor], "actors", 3)
    assert coverage["status"] == "COMPLETE"
    assert coverage["explicitly_absent"] == [ref]
    assert "EXPECTED_ACTOR_NOT_EXECUTED" in deviations
    assert "ACTOR_BINDING_MISMATCH" in deviations


def test_actor_absence_exact_and_multiple_wrong_attributes() -> None:
    envelope = r2_envelope()
    envelope["topology"]["role_bindings"] = [{
        "role_id": "builder", "workspace": "work", "branch": "topic", "scope": ["src"],
    }]
    expected = expected_observations(envelope)["actors"]
    ref = expected[0]["obligation_ref"]
    actor = {**expected[0]["binding"], "obligation_ref": ref,
             "participation": "REPORTED_NOT_EXECUTED"}
    exact, deviations = _dimension(expected, [actor], "actors", 3)
    assert exact["status"] == "COMPLETE" and exact["explicitly_absent"] == [ref]
    assert deviations == ["EXPECTED_ACTOR_NOT_EXECUTED"]
    wrong = {**actor, "workspace": "other", "branch": "elsewhere", "scope": ["other"]}
    coverage, deviations = _dimension(expected, [wrong], "actors", 3)
    assert coverage["status"] == "COMPLETE" and coverage["explicitly_absent"] == [ref]
    assert deviations.count("ACTOR_BINDING_MISMATCH") == 1
    assert "EXPECTED_ACTOR_NOT_EXECUTED" in deviations
