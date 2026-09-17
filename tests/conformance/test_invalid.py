import yaml
from noema.lint import lint_project
from noema.schemas import schema_root


def base_manifest():
    return {
      "noema":{"protocol":"0.1.0-rc.0","contracts":{"project_manifest":1}},
      "project":{"id":"bad","name":"Bad","type":"application","status":"active"},
      "traits":[],
      "authority":{"owns":["state"],"does_not_own":[]},
      "sources_of_truth":{},
      "context":{"entrypoint":"AGENTS.md","default_mode":"build","modes":{"build":{"required":[]}}},
      "quality_claims":["contract-conformance"],
      "relations":[],"exceptions":[],"extensions":{}
    }


def test_missing_manifest_fails(tmp_path):
    assert lint_project(tmp_path, schema_root()).status == "FAIL"


def test_authority_overlap_fails(tmp_path):
    data=base_manifest()
    data["authority"]["does_not_own"]=["state"]
    (tmp_path/"AGENTS.md").write_text("# agent", encoding="utf-8")
    (tmp_path/"noema.project.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    report=lint_project(tmp_path, schema_root())
    assert report.status == "FAIL"
    assert any(c.rule_id == "NOEMA-AUTH-001" and c.result == "FAIL" for c in report.checks)


def test_unknown_claim_fails(tmp_path):
    data=base_manifest()
    data["quality_claims"]=["made-up-claim"]
    (tmp_path/"AGENTS.md").write_text("# agent", encoding="utf-8")
    (tmp_path/"noema.project.yaml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    report=lint_project(tmp_path, schema_root())
    assert report.status == "FAIL"
