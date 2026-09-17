from pathlib import Path
from noema.lint import lint_project
from noema.audit import audit_project
from noema.schemas import schema_root


def test_noema_self_lints():
    root = schema_root()
    report = lint_project(root, root)
    assert report.status == "PASS", [c.to_dict() for c in report.checks]


def test_noema_context_audit_passes():
    root = schema_root()
    report, details = audit_project(root, root, "context")
    assert report.status == "PASS"
    assert details["context"]["missing"] == []
    assert details["context"]["files"] >= 1
