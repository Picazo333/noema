from __future__ import annotations

from pathlib import Path

from .claims import claim_catalog
from .context import context_stats, resolve_context_paths
from .lint import lint_project
from .loader import load_yaml
from .result import Check, Report
from .routing import load_executors, load_routes, load_runtime_availability, select_executor
from .schemas import schema_root


def audit_project(
    root: Path,
    protocol_root: Path | None = None,
    section: str = "all",
) -> tuple[Report, dict]:
    protocol_root = schema_root(protocol_root)
    root = root.resolve()
    base = lint_project(root, protocol_root)
    checks = list(base.checks)
    details: dict = {}
    if base.status == "FAIL":
        return Report("FAIL", base.project_id, checks), details

    manifest = load_yaml(root / "noema.project.yaml")

    if section in {"all", "context"}:
        try:
            context_cfg = manifest.get("context", {})
            modes = context_cfg.get("modes", {}) or {}
            default_mode = context_cfg.get("default_mode")
            mode_details: dict[str, dict] = {}

            for mode in modes:
                # Optional context must be valid (lint enforces that) but is not part
                # of cold-start cost until a task explicitly requests it.
                paths = resolve_context_paths(
                    root,
                    manifest,
                    mode,
                    include_optional=False,
                    include_manifest=True,
                )
                stats = context_stats(paths)
                detail = {
                    **stats,
                    "paths": [
                        str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
                        for path in paths
                    ],
                }
                mode_details[mode] = detail
                if stats["missing"]:
                    checks.append(
                        Check(
                            "NOEMA-AUDIT-CTX",
                            "ERROR",
                            "FAIL",
                            f"Context mode `{mode}` contains missing paths.",
                        )
                    )
                else:
                    checks.append(
                        Check(
                            "NOEMA-AUDIT-CTX-MODE",
                            "INFO",
                            "PASS",
                            f"Context mode `{mode}` resolves {stats['files']} files "
                            f"(~{stats['context_units']} Noema Context Units).",
                        )
                    )

            details["context_modes"] = mode_details
            if default_mode in mode_details:
                details["context"] = {
                    **mode_details[default_mode],
                    "mode": default_mode,
                }
                checks.append(
                    Check(
                        "NOEMA-AUDIT-CTX",
                        "INFO",
                        "PASS",
                        f"Default cold-start `{default_mode}` resolves "
                        f"{mode_details[default_mode]['files']} files "
                        f"(~{mode_details[default_mode]['context_units']} Noema Context Units).",
                    )
                )
        except Exception as exc:
            checks.append(
                Check("NOEMA-AUDIT-CTX", "ERROR", "FAIL", f"Context audit failed: {exc}")
            )

    if section in {"all", "claims"}:
        catalog = claim_catalog(protocol_root)
        details["claims"] = []
        for claim in manifest.get("quality_claims", []):
            details["claims"].append(
                {
                    "claim": claim,
                    "status": "UNASSESSED",
                    "recommended_graders": catalog.get(claim, {}).get(
                        "recommended_graders", []
                    ),
                }
            )
            checks.append(
                Check(
                    f"NOEMA-CLAIM-{claim}",
                    "INFO",
                    "UNASSESSED",
                    f"Quality claim `{claim}` requires project evidence; "
                    "conformance does not imply quality.",
                )
            )

    if section in {"all", "routing"}:
        routes = load_routes(protocol_root)
        executors = load_executors(protocol_root)
        runtime = load_runtime_availability()
        results = []
        for route in routes:
            req = dict(route.get("requires", {}))
            result = select_executor(req, executors, route, runtime)
            results.append({"route": route.get("id"), **result})
            if result["status"] == "ROUTED":
                checks.append(
                    Check(
                        "NOEMA-ROUTE-001",
                        "INFO",
                        "PASS",
                        f"Route `{route.get('id')}` resolves to `{result['executor']}`.",
                    )
                )
            else:
                checks.append(
                    Check(
                        "NOEMA-ROUTE-001",
                        "WARNING",
                        "UNASSESSED",
                        f"Route `{route.get('id')}` has no verified eligible executor; "
                        "expected before global AI configuration.",
                    )
                )
        details["routing"] = results

    status = (
        "FAIL"
        if any(check.severity == "ERROR" and check.result == "FAIL" for check in checks)
        else "PASS"
    )
    return Report(status, base.project_id, checks), details
