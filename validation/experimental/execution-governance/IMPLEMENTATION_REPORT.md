# Execution Governance v0 implementation report

## Scope delivered

- Exactly two protocol schemas: `execution-envelope/v0` and
  `execution-trace/v0`.
- Deterministic decision/control axes, DIRECT fast path, per-execution context
  load tiers, runtime-pressure conservation, opaque resolver receipts, tool
  suppression, RC0 executor-router reuse, runtime model filtering, topology,
  evaluation constraints, recovery/resume, trace/economics, and read-only
  Harvest scanning.
- Thin `noema eg` commands: doctor, plan, explain, validate, record, compare,
  resume-check, and scan-harvest.

## Evidence index

- Baseline/drift: `G0_BASELINE.md`
- Canary matrix: `CANARY_MANIFEST.yaml`
- Deterministic self-dogfood: `DOGFOOD_REPORT.md` and `tests/eg/`
- Deviations: `DEVIATIONS.md`
- Durable continuation: `experimental/execution-governance/program/`
- Downstream boundary: `DOWNSTREAM_ADOPTION_HANDOFF.md`

## Validation command set

```text
python -m ruff check .
pytest
python -m noema lint .
python -m noema audit .
python -m noema eg plan validation/experimental/execution-governance/corpus/C01/work-order.yaml --root . --json
python -m noema eg scan-harvest harvest/harvest-20260921-reference-authority-layering.yaml noema.project.yaml --json
```

The full audit retains the pre-existing, honest `UNASSESSED` quality-claim
notices and no-verified-executor warning. It remains a `PASS`; neither is
suppressed by EG.

## Auditor focus

Verify that EG remains opt-in and derived; external receipts/candidates are not
catalogue truth; DIRECT skips unnecessary candidate routing; traces reject
secret-like values; and no external repository is modified or required.
