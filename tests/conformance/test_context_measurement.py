from __future__ import annotations

import yaml

from noema.audit import audit_project
from noema.context import CONTEXT_METRIC
from noema.lint import lint_project
from noema.schemas import schema_root


def manifest():
    return {
        "noema": {"protocol": "0.1.0-rc.0", "contracts": {"project_manifest": 1}},
        "project": {
            "id": "context-demo",
            "name": "Context Demo",
            "type": "application",
            "status": "active",
        },
        "traits": [],
        "authority": {"owns": [], "does_not_own": []},
        "sources_of_truth": {},
        "context": {
            "entrypoint": "AGENTS.md",
            "default_mode": "build",
            "modes": {
                "build": {
                    "required": ["repo://docs/build.md"],
                    "optional": ["repo://docs/optional.md"],
                },
                "audit": {"required": ["repo://docs/audit.md"]},
            },
        },
        "quality_claims": ["contract-conformance"],
        "relations": [],
        "exceptions": [],
        "extensions": {},
    }


def write_project(tmp_path, include_optional=True):
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "AGENTS.md").write_text("# agent\n", encoding="utf-8")
    (docs / "build.md").write_text("build context\n", encoding="utf-8")
    (docs / "audit.md").write_text("audit context\n", encoding="utf-8")
    if include_optional:
        (docs / "optional.md").write_text("optional context\n", encoding="utf-8")
    (tmp_path / "noema.project.yaml").write_text(
        yaml.safe_dump(manifest(), sort_keys=False), encoding="utf-8"
    )


def test_context_audit_counts_manifest_and_reports_every_mode(tmp_path):
    write_project(tmp_path)
    report, details = audit_project(tmp_path, schema_root(), "context")

    assert report.status == "PASS"
    build = details["context_modes"]["build"]
    assert build["paths"] == ["AGENTS.md", "noema.project.yaml", "docs/build.md"]
    assert "docs/optional.md" not in build["paths"]
    assert build["files"] == 3
    assert build["approximation"] == CONTEXT_METRIC
    assert details["context"]["mode"] == "build"

    audit = details["context_modes"]["audit"]
    assert audit["paths"] == ["AGENTS.md", "noema.project.yaml", "docs/audit.md"]


def test_declared_optional_context_is_validated_but_not_cold_loaded(tmp_path):
    write_project(tmp_path, include_optional=False)
    report = lint_project(tmp_path, schema_root())

    assert report.status == "FAIL"
    assert any(
        check.rule_id == "NOEMA-CTX-002" and check.result == "FAIL"
        for check in report.checks
    )
