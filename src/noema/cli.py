from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .audit import audit_project
from .harvest import new_candidate, validate_candidate
from .lint import lint_project
from .loader import dump_yaml, load_yaml
from .refs import safe_project_path
from .schemas import schema_root


def _print_report(report, as_json=False, details=None):
    if as_json:
        payload = report.to_dict()
        if details is not None:
            payload["details"] = details
        print(json.dumps(payload, indent=2))
        return

    print(f"{report.status}: {report.project_id or '-'}")
    for check in report.checks:
        marker = {"PASS": "✓", "FAIL": "✗", "UNASSESSED": "?"}.get(
            check.result, "-"
        )
        print(f"{marker} [{check.severity}] {check.rule_id}: {check.message}")
        if check.path:
            print(f"    {check.path}")

    if details:
        if "context" in details:
            context = details["context"]
            print(
                "Context: "
                f"{context['files']} files, {context['bytes']} bytes, "
                f"~{context['context_units']} Noema Context Units"
            )
        if "context_modes" in details:
            for mode, context in details["context_modes"].items():
                print(
                    f"Context mode {mode}: {context['files']} files, "
                    f"~{context['context_units']} Noema Context Units"
                )
        if "routing" in details:
            for item in details["routing"]:
                print(f"Route {item['route']}: {item['status']} -> {item['executor']}")


def _profile(protocol_root: Path, name: str) -> dict:
    path = protocol_root / "profiles" / f"{name}.yaml"
    if not path.exists():
        raise ValueError(f"Unknown profile: {name}")
    return load_yaml(path)


def _project_template(protocol_root: Path) -> dict:
    path = protocol_root / "templates" / "project" / "noema.project.yaml.tpl"
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ValueError("Project manifest template must be a YAML object")
    return data


def _agent_template(protocol_root: Path) -> str:
    path = protocol_root / "templates" / "project" / "AGENTS.md.tpl"
    return path.read_text(encoding="utf-8")


def cmd_init(args) -> int:
    protocol_root = schema_root()
    target = Path(args.root).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    profile = _profile(protocol_root, args.profile)
    manifest_path = safe_project_path(target, "noema.project.yaml")
    agents_path = safe_project_path(target, "AGENTS.md")

    if not args.force and (manifest_path.exists() or agents_path.exists()):
        print(
            "Refusing to overwrite existing noema.project.yaml or AGENTS.md; use --force.",
            file=sys.stderr,
        )
        return 2

    manifest = _project_template(protocol_root)
    manifest["project"] = {
        "id": args.id,
        "name": args.name,
        "type": profile["type"],
        "status": "active",
    }
    manifest["traits"] = profile.get("traits", [])
    manifest["quality_claims"] = profile.get(
        "quality_claims", ["contract-conformance"]
    )

    manifest_path.write_text(dump_yaml(manifest), encoding="utf-8")
    agents_path.write_text(_agent_template(protocol_root), encoding="utf-8")

    report = lint_project(target, protocol_root)
    _print_report(report, args.json)
    return 0 if report.status == "PASS" else 1


def cmd_lint(args) -> int:
    report = lint_project(Path(args.root), schema_root())
    _print_report(report, args.json)
    return 0 if report.status == "PASS" else 1


def cmd_audit(args) -> int:
    report, details = audit_project(Path(args.root), schema_root(), args.section)
    _print_report(report, args.json, details)
    return 0 if report.status == "PASS" else 1


def cmd_harvest_new(args) -> int:
    target = new_candidate(
        Path(args.root),
        args.finding,
        args.route,
        args.evidence,
        args.confidence,
        args.confidentiality,
        args.scope,
    )
    print(target)
    return 0


def cmd_harvest_validate(args) -> int:
    errors = validate_candidate(Path(args.path), schema_root())
    if errors:
        for error in errors:
            print(f"FAIL: {error.message}", file=sys.stderr)
        return 1
    print("PASS")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="noema", description="Noema protocol conformance toolkit"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    command = sub.add_parser(
        "init", help="Initialize a minimal Noema project manifest and agent entrypoint"
    )
    command.add_argument("--root", default=".")
    command.add_argument("--id", required=True)
    command.add_argument("--name", required=True)
    command.add_argument("--profile", default="minimal")
    command.add_argument("--force", action="store_true")
    command.add_argument("--json", action="store_true")
    command.set_defaults(func=cmd_init)

    command = sub.add_parser("lint", help="Run deterministic conformance checks")
    command.add_argument("root", nargs="?", default=".")
    command.add_argument("--json", action="store_true")
    command.set_defaults(func=cmd_lint)

    command = sub.add_parser("audit", help="Run deeper project diagnostics")
    command.add_argument("root", nargs="?", default=".")
    command.add_argument(
        "--section",
        choices=["all", "context", "claims", "routing"],
        default="all",
    )
    command.add_argument("--json", action="store_true")
    command.set_defaults(func=cmd_audit)

    harvest = sub.add_parser("harvest", help="Create or validate harvest candidates")
    harvest_sub = harvest.add_subparsers(dest="harvest_command", required=True)

    command = harvest_sub.add_parser("new")
    command.add_argument("root", nargs="?", default=".")
    command.add_argument("--finding", required=True)
    command.add_argument("--route", action="append", default=[])
    command.add_argument("--evidence", action="append", default=[])
    command.add_argument(
        "--confidence", choices=["low", "medium", "high"], default="medium"
    )
    command.add_argument(
        "--confidentiality",
        choices=["PUBLIC_SAFE", "INTERNAL", "CLIENT_CONFIDENTIAL", "RESTRICTED"],
        default="INTERNAL",
    )
    command.add_argument("--scope", default="project")
    command.set_defaults(func=cmd_harvest_new)

    command = harvest_sub.add_parser("validate")
    command.add_argument("path")
    command.set_defaults(func=cmd_harvest_validate)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError, KeyError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # defensive CLI boundary
        print(f"Internal Noema error: {exc}", file=sys.stderr)
        return 3
