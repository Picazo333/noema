"""Operational exact-SHA T1 gate; writes only external, allowlisted evidence."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from xml.etree import ElementTree


BASE_IDS = {f"R5-C{index:02d}" for index in range(1, 25)}
T1_IDS = {"COV-TOOLS-EMPTY", "COV-ACTOR-EMPTY", "COV-TOOLS-COMPLETE",
          "COV-ACTORS-COMPLETE", "RESOLVER-DRIFT", "RESOLVER-NO-INTEGRITY"}
FINAL_REPAIR_IDS = {"COV-TOOLS-UNBOUND-R3", "COV-ACTOR-ABSENCE-BINDING"}
REQUIRED_IDS = BASE_IDS | T1_IDS | FINAL_REPAIR_IDS
ARTIFACTS = ("CANARY_RESULTS.json", "DOGFOOD_REPORT.md", "TEST_SUMMARY.json", "VERIFICATION.json")


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True,
                                   stderr=subprocess.DEVNULL).strip()


def verify_checkout(root: Path, sha: str) -> dict:
    if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise ValueError("expected SHA must be a full Git SHA-1")
    observed = _git(root, "rev-parse", "HEAD")
    if observed != sha:
        raise ValueError("checkout SHA mismatch")
    if _git(root, "status", "--porcelain"):
        raise ValueError("checkout tree is not clean")
    tracked = set(_git(root, "ls-files").splitlines())
    for required in ("src/noema/eg/compare.py", "src/noema/eg/dogfood.py",
                     "validation/experimental/execution-governance/R5_CANARY_DEFINITIONS.json",
                     ".github/scripts/verify_t1.py", ".github/workflows/ci.yml"):
        if required not in tracked:
            raise ValueError(f"required checkout input is untracked: {required}")
    return {"sha": observed, "parent": _git(root, "rev-parse", "HEAD^")}


def verify_imports(root: Path, environment: dict[str, str]) -> dict:
    script = ("import json, pathlib, noema, noema.eg.compare, noema.eg.dogfood; "
              "print(json.dumps([str(pathlib.Path(module.__file__).resolve()) for module in "
              "(noema, noema.eg.compare, noema.eg.dogfood)]))")
    checked = subprocess.run([sys.executable, "-c", script], cwd=root, env=environment,
                             capture_output=True, text=True, check=False)
    if checked.returncode:
        raise ValueError("checkout import failed")
    try:
        paths = [Path(value).resolve() for value in json.loads(checked.stdout)]
    except (ValueError, TypeError) as exc:
        raise ValueError("checkout import report invalid") from exc
    source = (root / "src").resolve()
    if not paths or not all(path.is_relative_to(source) for path in paths):
        raise ValueError("Noema was imported outside the tested checkout")
    return {"source_root": str(source), "module_count": len(paths)}


def _junit_summary(path: Path, exit_code: int) -> dict:
    try:
        tree = ElementTree.parse(path)
        cases = list(tree.getroot().iter("testcase"))
    except (OSError, ElementTree.ParseError):
        return {"status": "FAIL", "reason": "JUNIT_MISSING_OR_INVALID", "exit_code": exit_code,
                "total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    failed = sum(case.find("failure") is not None for case in cases)
    errors = sum(case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    passed = len(cases) - failed - errors - skipped
    status = "PASS" if exit_code == 0 and passed > 0 and not (failed or errors or skipped) else "FAIL"
    return {"status": status, "exit_code": exit_code, "total": len(cases),
            "passed": passed, "failed": failed, "errors": errors, "skipped": skipped}


def validate_results(root: Path, output: Path, sha: str) -> dict:
    definitions = json.loads((root / "validation/experimental/execution-governance/R5_CANARY_DEFINITIONS.json").read_text(encoding="utf-8"))
    ids = [item["id"] for item in definitions["canaries"]]
    if len(ids) != len(REQUIRED_IDS) or set(ids) != REQUIRED_IDS or len(set(ids)) != len(REQUIRED_IDS):
        raise ValueError("required canary definitions are absent or duplicated")
    observed = json.loads((output / "CANARY_RESULTS.json").read_text(encoding="utf-8"))
    rows = observed.get("canaries", [])
    observed_ids = [item.get("id") for item in rows]
    if (observed.get("tested_sha") != sha or observed.get("status") != "PASS"
            or observed_ids != ids or any(item.get("sha") != sha or item.get("status") != "PASS"
                                   or item.get("observed") != "PASS" or item.get("exit_code") != 0
                                   or not item.get("test_counts") or item["test_counts"].get("passed", 0) < 1
                                   or item["test_counts"].get("skipped", 0)
                                   or item["test_counts"].get("errors", 0)
                                   or item["test_counts"].get("failed", 0) for item in rows)):
        raise ValueError("required canary result is incomplete or failed")
    if not (output / "DOGFOOD_REPORT.md").is_file():
        raise ValueError("dogfood report is missing")
    return {"status": "PASS", "required": len(REQUIRED_IDS), "passed": len(rows)}


def write_evidence(output: Path, verification: dict, test_summary: dict) -> None:
    (output / "TEST_SUMMARY.json").write_text(json.dumps(test_summary, indent=2) + "\n", encoding="utf-8")
    verification["artifact_digests"] = {
        name: "sha256:" + sha256((output / name).read_bytes()).hexdigest()
        for name in ARTIFACTS[:-1] if (output / name).is_file()
    }
    (output / "VERIFICATION.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")


def main(root: Path, expected_sha: str, output: Path) -> int:
    root = root.resolve()
    output = output.resolve()
    if output == root or root in output.parents or output.exists() and any(output.iterdir()):
        raise ValueError("evidence directory must be empty and outside the checkout")
    output.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, "PYTHONPATH": str((root / "src").resolve())}
    verification: dict = {"expected_sha": expected_sha, "status": "FAIL",
                          "runner_os": platform.platform(), "python": platform.python_version(),
                          "runner_image": os.environ.get("ImageOS"),
                          "runner_image_version": os.environ.get("ImageVersion"),
                          "run_id": os.environ.get("GITHUB_RUN_ID"),
                          "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
                          "contract_revisions": {"execution-envelope/v1": 2,
                                                 "execution-trace/v1": 3},
                          "policy_revision": "eg-policy-v1", "verifier_revision": "r5",
                          "commands": []}
    test_summary: dict = {"status": "NOT_RUN"}
    try:
        checkout = verify_checkout(root, expected_sha)
        verification.update(checkout)
        verification["input_digests"] = {
            name: "sha256:" + sha256((root / name).read_bytes()).hexdigest()
            for name in (".github/workflows/ci.yml", ".github/scripts/verify_t1.py",
                         "constraints/ci.txt",
                         "validation/experimental/execution-governance/R5_CANARY_DEFINITIONS.json")
        }
        verification["imports"] = verify_imports(root, environment)
        commands = [("ruff", ["ruff", "check", "."]),
                    ("pytest", [sys.executable, "-m", "pytest"]),
                    ("lint", [sys.executable, "-m", "noema", "lint", "."]),
                    ("audit", [sys.executable, "-m", "noema", "audit", "."]),
                    ("diff_check", ["git", "diff", "--check"])]
        with TemporaryDirectory(prefix="noema-t1-") as temporary:
            for name, command in commands:
                if name == "pytest":
                    command = [*command, f"--junitxml={Path(temporary) / 'tests.xml'}"]
                process = subprocess.run(command, cwd=root, env=environment,
                                         capture_output=True, text=True, check=False)
                verification["commands"].append({"name": name, "exit_code": process.returncode})
                if name == "pytest":
                    test_summary = _junit_summary(Path(temporary) / "tests.xml", process.returncode)
                verify_checkout(root, expected_sha)
                if process.returncode != 0 or name == "pytest" and test_summary["status"] != "PASS":
                    raise ValueError(f"required {name} check failed")
        process = subprocess.run([sys.executable, "-m", "noema.eg.dogfood", str(root),
                                  "validation/experimental/execution-governance/R5_CANARY_DEFINITIONS.json",
                                  str(output), "--expected-sha", expected_sha],
                                 cwd=root, env=environment, capture_output=True, text=True, check=False)
        verification["commands"].append({"name": "canaries", "exit_code": process.returncode})
        verify_checkout(root, expected_sha)
        if process.returncode:
            raise ValueError("canary runner failed")
        verification["canaries"] = validate_results(root, output, expected_sha)
        verification["status"] = "PASS"
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        verification["failure"] = type(exc).__name__ + ": " + str(exc)[:160]
        return 1
    finally:
        write_evidence(output, verification, test_summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    raise SystemExit(main(args.root, args.expected_sha, args.output_dir))
