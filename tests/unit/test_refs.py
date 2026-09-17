from pathlib import Path
import pytest
from noema.refs import safe_project_path, parse_ref


def test_parse_ref():
    ref = parse_ref("repo://spec/file.md")
    assert ref.scheme == "repo"
    assert ref.locator == "spec/file.md"


def test_path_traversal_blocked(tmp_path):
    with pytest.raises(ValueError):
        safe_project_path(tmp_path, "../escape.txt")
