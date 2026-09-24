# Execution Governance — audit rework R2

Status: `READY_FOR_REAUDIT`. This targeted rework starts
from audited SHA `48acc9b56ff778ea4f5a7d8c4fbd34c4a135f574` and modifies only
Noema's experimental Execution Governance implementation.

Tested source SHA: `7507cd03ab4cf4747fb6571bb8a8908635ae6916`.

## R2-01 — resolver BLOCKED terminality

- Severity: P1. Adjudication: confirmed.
- Root cause: receipt presence affected `needs_resolution`, while terminal
  handling was conditional on `resolver_required`.
- Reproduction before: a non-required `BLOCKED` receipt produced `ROUTED`.
- Files modified: `src/noema/eg/plan.py`.
- Corrective action: unexpected receipts no longer activate resolution and add
  `RESOLVER_RECEIPT_NOT_REQUIRED`; required resolution now requires usable
  `RESOLVED`/`PARTIAL` evidence and treats `BLOCKED` as terminal.
- Tests added: `test_r2_01_resolver_participation_is_explicit_and_terminal`.
- Result after: direct/no-receipt remains direct, unexpected receipt is explicit
  but non-influential, and blocked/invalid required resolution is terminal or
  deterministic failure.
- Remaining limitation: receipt content remains opaque; only its typed status
  and reference participate.

## R2-02 — runtime pressure contract parity

- Severity: P1. Adjudication: confirmed.
- Root cause: enforcement consumed fields absent from the public schema.
- Reproduction before: CLI rejected `blocked_resources` as an additional
  property, so tests bypassed the public boundary.
- Files modified: runtime-pressure schema and `src/noema/eg/runtime.py`.
- Corrective action: one closed public contract now carries blocked resources,
  interfaces, global external block, provenance, and posture into enforcement.
- Tests added: runtime CLI matrix and malformed-input case in R2 seams.
- Result after: NORMAL, CONSERVE, THROTTLED, resource/interface/global BLOCKED,
  and malformed input traverse schema → CLI → planner → disposition.
- Remaining limitation: resource identities are supplied by the caller; Noema
  does not infer provider state.

## R2-03 — ReadSet freshness identity

- Severity: P1. Adjudication: confirmed.
- Root cause: the dedupe key ignored `StorageRef.integrity` and treated unknown
  freshness as stable.
- Reproduction before: two integrity revisions of one locator suppressed the
  second read.
- Files modified: `context_plan.py`, `trace.py`, execution-trace schema.
- Corrective action: integrity, version, then explicit freshness form identity;
  unknown identity is always read. Trace context events retain `identity_kind`.
- Tests added: `test_r2_03_readset_requires_evidence_and_trace_records_identity`.
- Result after: only same immutable identity suppresses; changed/unknown refs
  read again.
- Remaining limitation: version is trusted as strong only when supplied by a
  storage reference contract.

## R2-04 — resume constraints and effective executor

- Severity: P1. Adjudication: confirmed.
- Root cause: prohibited scopes were treated as active violations, and recovery
  trusted metadata instead of the routed executor binding.
- Reproduction before: preserving `secrets` failed while removing it passed.
- Files modified: `recovery.py`, `plan.py`, envelope schema.
- Corrective action: resume requires inherited prohibitions as a subset of the
  resumed restrictions, checks effective writes do not broaden, and derives
  expected executor from routing output.
- Tests added: `test_r2_04_resume_preserves_constraints_and_uses_effective_executor`.
- Result after: retained/strengthened restrictions pass; removed restrictions,
  broadened writes, and metadata-only executor identities fail.
- Remaining limitation: v0 uses normalized path-set restrictions rather than a
  richer permission algebra.

## R2-05 — provable parallel isolation

- Severity: P1. Adjudication: confirmed.
- Root cause: runtime accepted drive-qualified/case-colliding paths and schema
  accepted parallel topology without scope/binding evidence.
- Reproduction before: `src/A`/`src/a`, drive paths, and schema-only parallel
  envelopes were accepted.
- Files modified: `topology.py`, execution-envelope schema.
- Corrective action: deterministic case-folded project-relative normalization;
  worker bindings and matching non-empty scopes are mandatory; schema has a
  `PARALLEL_ISOLATED` conditional requirement.
- Tests added: `test_r2_05_topology_runtime_and_schema_both_require_isolation_evidence`.
- Result after: unsafe isolation is rejected by runtime and insufficient public
  envelope evidence fails schema validation.
- Remaining limitation: globs remain rejected rather than heuristically split.

## R2-06 — WorkOrder identity preservation

- Severity: P1. Adjudication: confirmed.
- Root cause: planner substituted the checkout manifest project ID for the
  validated WorkOrder project ID.
- Reproduction before: `foreign-project` WorkOrder emitted `noema` envelope.
- Files modified: `plan.py`, execution-envelope schema.
- Corrective action: envelope preserves `work_order_id` and WorkOrder project;
  current-project mismatch explicitly yields `ROUTE_ELSEWHERE`.
- Tests added: `test_r2_06_work_order_identity_is_preserved_through_cli`.
- Result after: local identity is preserved and foreign authority is not
  rewritten.
- Remaining limitation: cross-authority execution remains deferred to the
  declared authoritative project.

## R2-07 — dogfood evidence reconstruction

- Severity: P1. Adjudication: confirmed.
- Root cause: helper-only tests were called end-to-end and mandatory flows were
  only described in prose.
- Reproduction before: Harvest was labelled E2E while calling `scan_harvest()`
  directly.
- Files modified: `DOGFOOD_REPORT.md`, R2 seam tests.
- Corrective action: a new matrix uses distinct rows, exact public entrypoints,
  test paths, observed results, source SHA, and status.
- Tests added: public CLI seams for router, executor, topology, context/trace,
  resume, secret trace, and Harvest.
- Result after: every mandatory row names evidence that crosses its public
  boundary.
- Remaining limitation: all runs remain deterministic local dogfood; no
  provider-backed effect is claimed.

## R2-08 — unavailable metrics

- Severity: P2. Adjudication: confirmed.
- Root cause: missing observations were defaulted to `MEASURED: 0`.
- Reproduction before: `create_trace(envelope, {})` emitted four measured zeros.
- Files modified: `trace.py`, execution-trace schema.
- Corrective action: only supplied instrumentation yields measured counts;
  absent values are `UNAVAILABLE` and duplicate top-level counts are null.
- Tests added: `test_r2_08_missing_metrics_stay_unavailable_through_public_record_cli`.
- Result after: empty actual input does not invent zero telemetry.
- Remaining limitation: costs and tokens remain unavailable unless host evidence
  is supplied.
