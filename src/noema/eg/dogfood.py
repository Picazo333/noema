"""Observed, post-commit EG canary evidence (never a tracked PASS claim)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import argparse
import subprocess
import sys
import tempfile
from xml.etree import ElementTree

from .persistence import assert_persistable, atomic_write


def render_dogfood_report(results: dict) -> str:
    rows = results.get("canaries", [])
    lines = [
        f"# Execution Governance {results.get('suite', 'R5')} dogfood evidence",
        "",
        "Generated from observed test processes; do not edit this report manually.",
        f"Tested SHA: `{results['tested_sha']}`.",
        "",
        "| ID | Scenario | Level | Public entrypoint | Test/evidence | Expected / observed | SHA | Status |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {id} | {scenario} | {level} | {public_entrypoint} | {evidence} | {expected} / {observed} | {sha} | {status} |".format(**row)
        )
    return "\n".join(lines) + "\n"


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _junit_counts(path: Path) -> dict[str, int] | None:
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError):
        return None
    cases = list(root.iter("testcase"))
    failed = sum(case.find("failure") is not None for case in cases)
    errors = sum(case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    return {"passed": len(cases) - failed - errors - skipped,
            "failed": failed, "errors": errors, "skipped": skipped,
            "total": len(cases)}


def run_dogfood(root: Path, definitions: Path, output_dir: Path,
                expected_sha: str) -> dict:
    """Run each declared canary against a clean commit and write external evidence."""
    root = root.resolve()
    output_dir = output_dir.resolve()
    if output_dir == root or root in output_dir.parents:
        raise ValueError("Canary results must be written outside the repository")
    if _git(root, "status", "--porcelain"):
        raise ValueError("Canary evidence requires a clean committed worktree")
    sha = _git(root, "rev-parse", "HEAD")
    if sha != expected_sha:
        raise ValueError("Canary checkout SHA does not match expected SHA")
    definition = json.loads(definitions.read_text(encoding="utf-8"))
    cases = definition["canaries"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("At least one required canary is needed")
    identifiers = [case.get("id") for case in cases]
    if any(not isinstance(ident, str) or not ident for ident in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("Required canary IDs must be unique and non-empty")
    environment = {**os.environ, "PYTHONPATH": str(root / "src")}
    imported = subprocess.run(
        [sys.executable, "-c", "import pathlib, noema; print(pathlib.Path(noema.__file__).resolve())"],
        cwd=root, env=environment, capture_output=True, text=True, check=False,
    )
    if (imported.returncode != 0 or not imported.stdout.strip()
            or not Path(imported.stdout.strip()).resolve().is_relative_to(root / "src")):
        raise ValueError("Canary import does not resolve to the tested checkout")
    rows = []
    with tempfile.TemporaryDirectory(prefix="noema-canary-") as temporary:
        for index, case in enumerate(cases):
            xml = Path(temporary) / f"case-{index}.xml"
            process = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", f"--junitxml={xml}", case["evidence"]],
                cwd=root, env=environment, capture_output=True, text=True, check=False,
            )
            counts = _junit_counts(xml)
            unchanged = _git(root, "rev-parse", "HEAD") == sha and not _git(root, "status", "--porcelain")
            passed = (process.returncode == 0 and unchanged and counts is not None
                      and counts["passed"] > 0 and counts["failed"] == counts["errors"] == counts["skipped"] == 0)
            reason = ("TREE_MUTATION" if not unchanged else "CANARY_RESULTS_MISSING" if counts is None
                      else "REQUIRED_SKIP_OR_XFAIL" if counts["skipped"] else
                      "ZERO_TESTS" if not counts["passed"] else "CANARY_FAILED")
            rows.append({**case, "observed": "PASS" if passed else "FAIL",
                         "sha": sha, "status": "PASS" if passed else "FAIL",
                         "exit_code": process.returncode, "test_counts": counts,
                         "reason_codes": [] if passed else [reason]})
    results = {"suite": definition.get("suite", "R5"), "tested_sha": sha, "status": "PASS" if all(
        row["status"] == "PASS" for row in rows) else "FAIL", "canaries": rows}
    assert_persistable(results)
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(output_dir / "CANARY_RESULTS.json", json.dumps(results, indent=2) + "\n")
    atomic_write(output_dir / "DOGFOOD_REPORT.md", render_dogfood_report(results))
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run committed EG canaries into an external directory")
    parser.add_argument("root", type=Path)
    parser.add_argument("definitions", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--expected-sha", required=True)
    options = parser.parse_args()
    observed = run_dogfood(options.root, options.definitions, options.output_dir,
                           options.expected_sha)
    raise SystemExit(0 if observed["status"] == "PASS" else 1)
