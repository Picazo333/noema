from __future__ import annotations

from pathlib import Path
from .claims import claim_catalog, project_types, traits as known_traits
from .context import resolve_context_paths
from .loader import load_yaml
from .manifest import validate_manifest
from .refs import repo_ref_exists, safe_project_path
from .result import Check, Report
from .schemas import schema_root, validation_errors
from . import __version__


def _errpath(error) -> str:
    return ".".join(str(p) for p in error.absolute_path) or "<root>"


def lint_project(root: Path, protocol_root: Path | None = None) -> Report:
    root = root.resolve()
    protocol_root = schema_root(protocol_root)
    checks: list[Check] = []
    manifest_path = root / "noema.project.yaml"
    if not manifest_path.exists():
        return Report("FAIL", None, [Check("NOEMA-MANIFEST-001", "ERROR", "FAIL", "Missing noema.project.yaml", str(manifest_path), "Run `noema init` or add a project manifest.")])

    try:
        manifest, errors = validate_manifest(root, protocol_root)
    except Exception as exc:
        return Report("FAIL", None, [Check("NOEMA-MANIFEST-002", "ERROR", "FAIL", f"Cannot load/validate manifest: {exc}", str(manifest_path))])

    project_id = (manifest or {}).get("project", {}).get("id") if isinstance(manifest, dict) else None
    if errors:
        for error in errors:
            checks.append(Check("NOEMA-MANIFEST-003", "ERROR", "FAIL", error.message, _errpath(error)))
        return Report("FAIL", project_id, checks)
    checks.append(Check("NOEMA-MANIFEST-003", "INFO", "PASS", "Project manifest matches schema."))

    pinned = manifest.get("noema", {}).get("protocol")
    if pinned != __version__:
        checks.append(Check("NOEMA-VERSION-001", "ERROR", "FAIL", f"Project pins Noema protocol `{pinned}` but this RC0 validator supports `{__version__}`.", "noema.protocol"))
    else:
        checks.append(Check("NOEMA-VERSION-001", "INFO", "PASS", f"Project explicitly pins supported Noema protocol `{pinned}`."))

    ptype = manifest["project"]["type"]
    if ptype not in project_types(protocol_root):
        checks.append(Check("NOEMA-COMP-001", "ERROR", "FAIL", f"Unknown project type: {ptype}", "project.type"))
    else:
        checks.append(Check("NOEMA-COMP-001", "INFO", "PASS", f"Known project type: {ptype}"))

    known = known_traits(protocol_root)
    unknown_traits = sorted(set(manifest.get("traits", [])) - known)
    if unknown_traits:
        checks.append(Check("NOEMA-COMP-002", "ERROR", "FAIL", f"Unknown traits: {', '.join(unknown_traits)}", "traits"))
    else:
        checks.append(Check("NOEMA-COMP-002", "INFO", "PASS", "All traits are known."))

    claims = claim_catalog(protocol_root)
    unknown_claims = [c for c in manifest.get("quality_claims", []) if c not in claims]
    if unknown_claims:
        checks.append(Check("NOEMA-QLT-002", "ERROR", "FAIL", f"Unknown quality claims: {', '.join(unknown_claims)}", "quality_claims"))
    else:
        checks.append(Check("NOEMA-QLT-002", "INFO", "PASS", "All quality claims are known."))

    owns = set(manifest["authority"].get("owns", []))
    excludes = set(manifest["authority"].get("does_not_own", []))
    overlap = sorted(owns & excludes)
    if overlap:
        checks.append(Check("NOEMA-AUTH-001", "ERROR", "FAIL", f"Authority appears in both owns and does_not_own: {', '.join(overlap)}", "authority"))
    else:
        checks.append(Check("NOEMA-AUTH-001", "INFO", "PASS", "Authority boundaries do not conflict."))

    try:
        entry = safe_project_path(root, manifest["context"]["entrypoint"])
    except ValueError as exc:
        entry = None
        checks.append(Check("NOEMA-CTX-001", "ERROR", "FAIL", f"Invalid context entrypoint: {exc}", "context.entrypoint"))
    if entry is not None:
        if not entry.exists():
            checks.append(Check("NOEMA-CTX-001", "ERROR", "FAIL", "Context entrypoint does not exist.", str(entry)))
        elif not entry.is_file():
            checks.append(Check("NOEMA-CTX-001", "ERROR", "FAIL", "Context entrypoint must resolve to a file.", str(entry)))
        else:
            checks.append(Check("NOEMA-CTX-001", "INFO", "PASS", "Context entrypoint resolves to a project file."))

    context = manifest.get("context", {})
    modes = context.get("modes", {}) or {}
    default_mode = context.get("default_mode")
    if default_mode not in modes:
        checks.append(Check("NOEMA-CTX-003", "ERROR", "FAIL", f"Default context mode `{default_mode}` is not declared in context.modes.", "context.default_mode"))
    else:
        checks.append(Check("NOEMA-CTX-003", "INFO", "PASS", f"Default context mode `{default_mode}` is declared."))

    for name, ref in manifest.get("sources_of_truth", {}).items():
        if ref.get("scheme") == "repo":
            value = f"repo://{ref['locator']}"
            if not repo_ref_exists(root, value):
                checks.append(Check("NOEMA-REF-001", "ERROR", "FAIL", f"Broken repo source_of_truth `{name}`: {value}", f"sources_of_truth.{name}"))
    for mode in modes:
        try:
            for path in resolve_context_paths(root, manifest, mode):
                if not path.exists():
                    checks.append(Check("NOEMA-CTX-002", "ERROR", "FAIL", f"Missing context path for mode `{mode}`: {path}", f"context.modes.{mode}"))
        except Exception as exc:
            checks.append(Check("NOEMA-CTX-002", "ERROR", "FAIL", f"Invalid context reference in mode `{mode}`: {exc}", f"context.modes.{mode}"))

    extensions = manifest.get("extensions", {})
    bad_ext = [k for k in extensions if not k.startswith("x-")]
    if bad_ext:
        checks.append(Check("NOEMA-EXT-001", "ERROR", "FAIL", f"Extension keys must start with x-: {', '.join(bad_ext)}", "extensions"))

    # Validate executor and routing registries when present. Malformed registries
    # must fail closed rather than raising from optimistic `.get()`/`list()` calls.
    executors_path = root / "registry/executors.yaml"
    routes_path = root / "registry/routing.yaml"
    ids: list[str] = []
    if executors_path.exists():
        try:
            data = load_yaml(executors_path) or {}
        except Exception as exc:
            checks.append(Check("NOEMA-STACK-001", "ERROR", "FAIL", f"Cannot load executor registry: {exc}", str(executors_path)))
        else:
            executors = data.get("executors", []) if isinstance(data, dict) else None
            if not isinstance(executors, list):
                checks.append(Check("NOEMA-STACK-001", "ERROR", "FAIL", "Executor registry `executors` must be a list.", str(executors_path)))
            elif any(not isinstance(e, dict) for e in executors):
                checks.append(Check("NOEMA-STACK-001", "ERROR", "FAIL", "Every executor registry item must be an object.", str(executors_path)))
            else:
                raw_ids = [e.get("id") for e in executors]
                if any(not isinstance(eid, str) or not eid for eid in raw_ids) or len(raw_ids) != len(set(raw_ids)):
                    checks.append(Check("NOEMA-STACK-001", "ERROR", "FAIL", "Executor registry requires unique non-empty string ids.", str(executors_path)))
                else:
                    ids = raw_ids
                    allowed_status = {"verified", "needs-verification", "disabled", "deprecated"}
                    bad = [e.get("id") for e in executors if e.get("status") not in allowed_status]
                    if bad:
                        checks.append(Check("NOEMA-STACK-001", "ERROR", "FAIL", f"Executors with invalid status: {', '.join(bad)}", str(executors_path)))
                    else:
                        checks.append(Check("NOEMA-STACK-001", "INFO", "PASS", "Executor registry structure is valid."))

    if routes_path.exists():
        try:
            data = load_yaml(routes_path) or {}
        except Exception as exc:
            checks.append(Check("NOEMA-ROUTE-REG-001", "ERROR", "FAIL", f"Cannot load routing registry: {exc}", str(routes_path)))
        else:
            routes = data.get("routes", []) if isinstance(data, dict) else None
            problems: list[str] = []
            if not isinstance(routes, list):
                problems.append("routing registry `routes` must be a list")
                routes = []
            elif any(not isinstance(route, dict) for route in routes):
                problems.append("every routing registry item must be an object")
                routes = [route for route in routes if isinstance(route, dict)]

            route_ids = [route.get("id") for route in routes]
            if any(not isinstance(rid, str) or not rid for rid in route_ids) or len(route_ids) != len(set(route_ids)):
                problems.append("route ids must be unique non-empty strings")

            known_ids = set(ids)
            for route in routes:
                refs: list[str] = []
                for field in ("prefer", "fallback"):
                    value = route.get(field, [])
                    if not isinstance(value, list):
                        problems.append(f"route `{route.get('id')}` field `{field}` must be a list")
                        continue
                    if any(not isinstance(item, str) or not item for item in value):
                        problems.append(f"route `{route.get('id')}` field `{field}` requires non-empty string executor ids")
                        continue
                    refs.extend(value)
                missing = sorted(set(refs) - known_ids)
                if missing:
                    problems.append(f"route `{route.get('id')}` references unknown executors: {', '.join(missing)}")
            if problems:
                checks.append(Check("NOEMA-ROUTE-REG-001", "ERROR", "FAIL", "; ".join(problems), str(routes_path)))
            else:
                checks.append(Check("NOEMA-ROUTE-REG-001", "INFO", "PASS", "Routing registry structure is valid."))

    # Validate ecosystem index when the project contains Noema's registry.
    ecosystem_path = root / "registry/ecosystem.yaml"
    if ecosystem_path.exists():
        try:
            eco = load_yaml(ecosystem_path)
            errors = validation_errors("ecosystem-index", eco, protocol_root)
            for error in errors:
                checks.append(Check("NOEMA-ECO-001", "ERROR", "FAIL", error.message, f"registry/ecosystem.yaml:{_errpath(error)}"))
            if not errors:
                eco_ids = [item.get("project_id") for item in eco.get("ecosystem", [])]
                if len(eco_ids) != len(set(eco_ids)):
                    checks.append(Check("NOEMA-ECO-001", "ERROR", "FAIL", "Ecosystem index contains duplicate project ids.", str(ecosystem_path)))
                else:
                    checks.append(Check("NOEMA-ECO-001", "INFO", "PASS", "Ecosystem index is valid."))
        except Exception as exc:
            checks.append(Check("NOEMA-ECO-001", "ERROR", "FAIL", f"Cannot validate ecosystem index: {exc}", str(ecosystem_path)))

    status = "FAIL" if any(c.severity == "ERROR" and c.result == "FAIL" for c in checks) else "PASS"
    return Report(status, project_id, checks)
