from __future__ import annotations

import yaml

from noema.cli import main


def test_harvest_candidate_roundtrip_with_evidence(tmp_path):
    assert (
        main(
            [
                "init",
                "--root",
                str(tmp_path),
                "--id",
                "demo",
                "--name",
                "Demo",
                "--profile",
                "minimal",
            ]
        )
        == 0
    )
    (tmp_path / "evidence.md").write_text("# evidence\n", encoding="utf-8")

    args = [
        "harvest",
        "new",
        str(tmp_path),
        "--finding",
        "Reusable context pattern",
        "--route",
        "noema",
        "--evidence",
        "repo://evidence.md",
    ]
    assert main(args) == 0
    assert main(args) == 0

    files = sorted((tmp_path / "harvest").glob("*.yaml"))
    assert len(files) == 2
    assert files[0].name != files[1].name

    candidate = yaml.safe_load(files[0].read_text(encoding="utf-8"))
    assert candidate["evidence_refs"] == [
        {"scheme": "repo", "locator": "evidence.md"}
    ]
    assert main(["harvest", "validate", str(files[0])]) == 0


def test_harvest_rejects_missing_repo_evidence(tmp_path):
    assert (
        main(
            [
                "init",
                "--root",
                str(tmp_path),
                "--id",
                "demo",
                "--name",
                "Demo",
                "--profile",
                "minimal",
            ]
        )
        == 0
    )
    code = main(
        [
            "harvest",
            "new",
            str(tmp_path),
            "--finding",
            "Missing evidence",
            "--evidence",
            "repo://does-not-exist.md",
        ]
    )
    assert code == 2
