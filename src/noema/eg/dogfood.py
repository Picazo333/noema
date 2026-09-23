"""Observed, post-commit EG canary evidence (never a tracked PASS claim)."""

from __future__ import annotations

import json
import os
from pathlib import Path
import argparse
import re
import subprocess
import sys

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
    environment = {**os.environ, "PYTHONPATH": str(root / "src")}
    imported = subprocess.run(
        [sys.executable, "-c", "import pathlib, noema; print(pathlib.Path(noema.__file__).resolve())"],
        cwd=root, env=environment, capture_output=True, text=True, check=False,
    )
    if (imported.returncode != 0 or not imported.stdout.strip()
            or not Path(imported.stdout.strip()).resolve().is_relative_to(root / "src")):
        raise ValueError("Canary import does not resolve to the tested checkout")
    rows = []
    for case in cases:
        process = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-rs", case["evidence"]],
            cwd=root, env=environment, capture_output=True, text=True, check=False,
        )
        output = process.stdout + process.stderr
        skipped = bool(re.search(r"\b\d+ skipped\b|\bSKIPPED\b", output))
        zero = "no tests ran" in output or "0 passed" in output
        unchanged = _git(root, "rev-parse", "HEAD") == sha and not _git(root, "status", "--porcelain")
        passed = process.returncode == 0 and not skipped and not zero and unchanged
        rows.append({**case, "observed": "PASS" if passed else "FAIL",
                     "sha": sha, "status": "PASS" if passed else "FAIL",
                     "exit_code": process.returncode,
                     "reason_codes": ([] if passed else [
                         "REQUIRED_SKIP" if skipped else
                         "ZERO_TESTS" if zero else
                         "TREE_MUTATION" if not unchanged else "CANARY_FAILED"
                     ])})
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
