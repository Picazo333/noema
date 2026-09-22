"""Observed, post-commit EG canary evidence (never a tracked PASS claim)."""

from __future__ import annotations

import json
from pathlib import Path
import argparse
import subprocess
import sys


def render_dogfood_report(results: dict) -> str:
    rows = results.get("canaries", [])
    lines = [
        "# Execution Governance R4 dogfood evidence",
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


def run_dogfood(root: Path, definitions: Path, output_dir: Path) -> dict:
    """Run each declared canary against a clean commit and write external evidence."""
    root = root.resolve()
    output_dir = output_dir.resolve()
    if output_dir == root or root in output_dir.parents:
        raise ValueError("Canary results must be written outside the repository")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        raise ValueError("Canary evidence requires a clean committed worktree")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    cases = json.loads(definitions.read_text(encoding="utf-8"))["canaries"]
    rows = []
    for case in cases:
        process = subprocess.run([sys.executable, "-m", "pytest", "-q", case["evidence"]],
                                 cwd=root, capture_output=True, text=True, check=False)
        rows.append({**case, "observed": "PASS" if process.returncode == 0 else "FAIL",
                     "sha": sha, "status": "PASS" if process.returncode == 0 else "FAIL",
                     "exit_code": process.returncode})
    results = {"tested_sha": sha, "canaries": rows}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "CANARY_RESULTS.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    (output_dir / "DOGFOOD_REPORT.md").write_text(render_dogfood_report(results), encoding="utf-8")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run committed EG canaries into an external directory")
    parser.add_argument("root", type=Path)
    parser.add_argument("definitions", type=Path)
    parser.add_argument("output_dir", type=Path)
    options = parser.parse_args()
    run_dogfood(options.root, options.definitions, options.output_dir)
