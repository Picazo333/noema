import copy
import yaml
from noema.lint import lint_project
from noema.schemas import schema_root


def base_manifest():
    return {
      "noema":{"protocol":"0.1.0-rc.0","contracts":{"project_manifest":1}},
      "project":{"id":"demo","name":"Demo","type":"application","status":"active"},
      "traits":[],
      "authority":{"owns":[],"does_not_own":[]},
      "sources_of_truth":{},
      "context":{"entrypoint":"AGENTS.md","default_mode":"build","modes":{"build":{"required":[]}}},
      "quality_claims":["contract-conformance"],
      "relations":[],"exceptions":[],"extensions":{}
    }


def write_project(tmp_path, data):
    (tmp_path/"AGENTS.md").write_text("# entry", encoding="utf-8")
    (tmp_path/"noema.project.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def test_wrong_protocol_pin_fails(tmp_path):
    data=base_manifest(); data["noema"]["protocol"]="9.9.9"
    write_project(tmp_path, data)
    report=lint_project(tmp_path, schema_root())
    assert report.status == "FAIL"
    assert any(c.rule_id == "NOEMA-VERSION-001" and c.result == "FAIL" for c in report.checks)


def test_unknown_executor_reference_fails(tmp_path):
    write_project(tmp_path, base_manifest())
    reg=tmp_path/"registry"; reg.mkdir()
    (reg/"executors.yaml").write_text("executors:\n  - id: one\n    provider: test\n    status: verified\n", encoding="utf-8")
    (reg/"routing.yaml").write_text("routes:\n  - id: bad-route\n    requires: {capabilities: []}\n    prefer: [missing]\n    fallback: []\n", encoding="utf-8")
    report=lint_project(tmp_path, schema_root())
    assert report.status == "FAIL"
    assert any(c.rule_id == "NOEMA-ROUTE-REG-001" and c.result == "FAIL" for c in report.checks)
