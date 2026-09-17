from __future__ import annotations

import yaml

from noema.audit import audit_project
from noema.lint import lint_project
from noema.schemas import schema_root


def base_manifest():
    return {
        "noema": {"protocol": "0.1.0-rc.0", "contracts": {"project_manifest": 1}},
        "project": {"id": "edge-demo", "name": "Edge Demo", "type": "application", "status": "active"},
        "traits": [],
        "authority": {"owns": [], "does_not_own": []},
        "sources_of_truth": {},
        "context": {
            "entrypoint": "AGENTS.md",
            "default_mode": "build",
            "modes": {"build": {"required": []}},
        },
        "quality_claims": ["contract-conformance"],
        "relations": [],
        "exceptions": [],
        "extensions": {},
    }


def write_project(tmp_path, data):
    (tmp_path / "AGENTS.md").write_text("# entry\n", encoding="utf-8")
    (tmp_path / "noema.project.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )


def assert_failed(report, rule_id):
    assert report.status == "FAIL"
    assert any(c.rule_id == rule_id and c.result == "FAIL" for c in report.checks)


def test_entrypoint_cannot_escape_project_root(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("# outside\n", encoding="utf-8")
    data = base_manifest()
    data["context"]["entrypoint"] = f"../{outside.name}"
    write_project(tmp_path, data)

    report = lint_project(tmp_path, schema_root())
    assert_failed(report, "NOEMA-CTX-001")


def test_entrypoint_must_be_file(tmp_path):
    data = base_manifest()
    data["context"]["entrypoint"] = "docs"
    write_project(tmp_path, data)
    (tmp_path / "docs").mkdir()

    report = lint_project(tmp_path, schema_root())
    assert_failed(report, "NOEMA-CTX-001")


def test_default_context_mode_must_be_declared(tmp_path):
    data = base_manifest()
    data["context"]["modes"] = {"audit": {"required": []}}
    write_project(tmp_path, data)

    report = lint_project(tmp_path, schema_root())
    assert_failed(report, "NOEMA-CTX-003")


def test_scalar_executor_item_fails_closed(tmp_path):
    write_project(tmp_path, base_manifest())
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "executors.yaml").write_text(
        "executors:\n  - not-an-object\n", encoding="utf-8"
    )

    report = lint_project(tmp_path, schema_root())
    assert_failed(report, "NOEMA-STACK-001")

    audit, _ = audit_project(tmp_path, schema_root())
    assert audit.status == "FAIL"


def test_scalar_route_item_fails_closed(tmp_path):
    write_project(tmp_path, base_manifest())
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "executors.yaml").write_text(
        "executors:\n  - id: one\n    provider: test\n    status: verified\n",
        encoding="utf-8",
    )
    (registry / "routing.yaml").write_text(
        "routes:\n  - not-an-object\n", encoding="utf-8"
    )

    report = lint_project(tmp_path, schema_root())
    assert_failed(report, "NOEMA-ROUTE-REG-001")


def test_null_prefer_fails_closed(tmp_path):
    write_project(tmp_path, base_manifest())
    registry = tmp_path / "registry"
    registry.mkdir()
    (registry / "executors.yaml").write_text(
        "executors:\n  - id: one\n    provider: test\n    status: verified\n",
        encoding="utf-8",
    )
    (registry / "routing.yaml").write_text(
        "routes:\n"
        "  - id: null-prefer\n"
        "    requires: {capabilities: []}\n"
        "    prefer: null\n"
        "    fallback: []\n",
        encoding="utf-8",
    )

    report = lint_project(tmp_path, schema_root())
    assert_failed(report, "NOEMA-ROUTE-REG-001")
