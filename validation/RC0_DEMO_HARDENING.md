# Noema RC0 — Demo Consumer Hardening

**Trigger:** external consumer demo (`noema-plastic-surgeon-demo`)  
**Scope:** validator hardening only; protocol architecture remains closed.  
**Branch:** `hardening/rc0-demo-edge-cases`

## Result

The demo exposed six deterministic validator edge cases plus one pre-existing CI reproducibility issue. All are treated as hardening defects, not reasons to reopen RC0 architecture.

## Closed edge cases

| ID | Finding | Hardening response |
|---|---|---|
| H-01 | `context.entrypoint` could reference an existing path outside the project root and pass `lint` | Resolve through `safe_project_path`; fail closed on escape |
| H-02 | `context.entrypoint` could be a directory | Require a regular project file |
| H-03 | `context.default_mode` could be absent from `context.modes` | Require the default mode to be explicitly declared |
| H-04 | scalar/non-object executor item could raise during lint | Validate list/item shape before semantic checks |
| H-05 | scalar/non-object route item could raise during lint | Validate list/item shape before semantic checks |
| H-06 | `prefer: null` / non-list route order could raise during lint | Require list-valued `prefer`/`fallback`; fail closed |
| H-07 | CI lint behavior drifted as Ruff releases expanded active rule families | Declare the intended Ruff lint families explicitly and remove stale F401 debt |

## Regression coverage

`tests/conformance/test_demo_regressions.py` contains one regression for each demo-discovered validator case, including an audit smoke check for malformed executor registries.

## CI gate

The hardening branch must pass the repository's normal gate:

1. dependency installation;
2. `ruff check .`;
3. `pytest`;
4. `noema lint .`;
5. `noema audit . --section context`.

At the first green run after hardening, all five stages passed.

## Architectural decision

No schemas, profiles, project types, authority boundaries, domain ontologies, routing architecture, or protocol-version semantics were expanded to address these defects.

**Decision:** keep RC0 architecture closed. Treat this patch as validator/CI hardening before selective migration into Skill Foundry.
