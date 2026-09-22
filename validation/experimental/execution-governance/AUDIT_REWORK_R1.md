# Execution Governance — audit rework R1

Status: `READY_FOR_REAUDIT` pending the final frozen commit. This report records
the implementation adjudication for the independent audit's R1 findings. The
work remains on `codex/noema-vnext-execution-governance`; no downstream
repository was accessed or modified.

Tested implementation SHA: `c61fcb8f4f02e1f65d0f58b6ac3ca064cc3a4684`.

## R1-01 — execution-trace secret safety

- Audit severity: P1. Adjudication: confirmed.
- Root cause: the trace accepted open-shaped event data and only applied a shallow denylist.
- Affected files: `src/noema/eg/trace.py`, `schemas/execution-trace/v0.schema.json`.
- Fix: persist only known, closed event/ref/role structures; recursively reject payload-like structures and normalized secret/key/token/cookie/password fields; retain private outputs only as typed evidence references.
- Tests added: `test_trace_rejects_secret_variants_everywhere`; `test_e2e_12_secret_bearing_trace_is_rejected`.
- Before reproduction: an unknown nested event field (including `authorization`) could reach an ExecutionTrace.
- After result: top-level, nested, and array-contained secret-bearing mappings deterministically raise `ValueError` before trace creation.
- Remaining limitation: Noema rejects secret-like content; it does not inspect an authorized evidence `StorageRef`.

## R1-02 — runtime BLOCKED precedence

- Audit severity: P1. Adjudication: confirmed.
- Root cause: posture affected advisory policy but not final disposition.
- Affected files: `src/noema/eg/runtime.py`, `src/noema/eg/plan.py`.
- Fix: resource matching occurs before final disposition; only required blocked resources are terminal, preserving the pure/local path.
- Tests added: `test_blocked_runtime_and_resolver_are_terminal_only_when_required`; `test_e2e_04_runtime_blocked_required_resource_is_terminal`.
- Before reproduction: a blocked GitHub-dependent task could be direct.
- After result: required blocked resources yield `BLOCKED` (or `DEFER` when throttled); unrelated blocked resources leave pure/local work direct.
- Remaining limitation: resource identity is supplied by task/runtime contract; Noema does not infer it from external systems.

## R1-03 — orchestrator router use

- Audit severity: P1. Adjudication: confirmed.
- Root cause: the envelope builder did not route executor/model requirements through existing adapters, and resolver failure was non-terminal.
- Affected files: `src/noema/eg/plan.py`, `schemas/execution-envelope/v0.schema.json`.
- Fix: validate WorkOrder first, route only when required, consume resolver status, call RC0 executor selection, filter model candidates, and record binding/status.
- Tests added: `test_routed_pipeline_uses_model_router_and_tool_fallback`, `test_no_verified_executor_blocks_integrated_pipeline`, E2E 02/05/06.
- Before reproduction: a `BLOCKED` resolver could become `ROUTED`; router output remained unbound.
- After result: resolver failure is terminal and executor absence is `BLOCKED_NO_VERIFIED_EXECUTOR`; model selection is persisted when supplied.
- Remaining limitation: model candidates remain host-provided, not a Noema catalogue.

## R1-04 — WorkOrder validation at entry

- Audit severity: P1. Adjudication: confirmed.
- Root cause: the CLI delegated straight to planning without canonical schema validation.
- Affected files: `src/noema/eg/cli.py`, `src/noema/eg/plan.py`, `src/noema/cli.py`.
- Fix: both CLI and public builder validate `work-order/v1` before planning.
- Tests added: invalid-field integration parametrization and E2E 03.
- Before reproduction: missing primary WorkOrder fields entered routing.
- After result: each required primary field is rejected with deterministic configuration error and no envelope.
- Remaining limitation: shorthand tasks are deliberately unsupported by this contract.

## R1-05 — eligibility before dominance

- Audit severity: P1. Adjudication: confirmed.
- Root cause: source ranking was computed over denied candidates.
- Affected files: `src/noema/eg/tooling.py`.
- Fix: establish hard eligibility first, then rank/suppress only eligible candidates.
- Tests added: `test_denied_candidate_cannot_suppress_fallback`; E2E 07.
- Before reproduction: denied authoritative candidate suppressed an allowed broad fallback.
- After result: denied candidate is `HARD_DENY`, allowed fallback is `CALL`.
- Remaining limitation: selection is over caller-supplied candidates only.

## R1-06 — parallel-isolated proof

- Audit severity: P1. Adjudication: confirmed.
- Root cause: empty and overlapping write scopes were accepted.
- Affected files: `src/noema/eg/topology.py`, `schemas/execution-envelope/v0.schema.json`.
- Fix: normalize concrete paths; require at least two; reject equal/parent-child intersections and globs; require serialized publication.
- Tests added: topology negative/positive matrix and E2E 08.
- Before reproduction: `src` and `src/noema` could be parallel workers.
- After result: overlapping, equivalent, empty, and unprovable scopes fail; disjoint scopes pass.
- Remaining limitation: v0 rejects globs instead of heuristic intersection.

## R1-07 — resume contract

- Audit severity: P1. Adjudication: confirmed.
- Root cause: resume verification checked only a small subset of continuation state.
- Affected files: `src/noema/eg/recovery.py`, `src/noema/eg/cli.py`, `src/noema/cli.py`, `schemas/execution-envelope/v0.schema.json`.
- Fix: verify identity, WorkOrder, role/executor, branch/workspace/SHA/frontier, claims/evidence, blockers/gates/prohibited scope, and next-action consistency; return PASS/FAIL/INCOMPLETE.
- Tests added: stale regression, integrated contract test, E2E 10/11.
- Before reproduction: wrong branch/role/gate could resume with thin state.
- After result: stale or inconsistent state fails; absent state is incomplete; complete matching state passes.
- Remaining limitation: evidence refs establish structural provenance, not substantive truth.

## R1-08 — progressive context loop

- Audit severity: P1. Adjudication: confirmed.
- Root cause: only partial HOT/WARM planning existed and ReadSet was detached from trace.
- Affected files: `src/noema/eg/context_plan.py`, `src/noema/eg/trace.py`, both EG schemas.
- Fix: HOT/WARM/COLD/NEVER_PRELOAD, auditable promotion to HOT, and freshness-keyed duplicate-read outcomes as context events.
- Tests added: context/resume integration case and E2E 09.
- Before reproduction: COLD/NEVER/promotion and trace read suppression were absent.
- After result: transitions and `DUPLICATE_READ_SUPPRESSED` appear in envelope/trace.
- Remaining limitation: tiers are execution-local hints and do not alter authority.

## R1-09 — explicit metric availability

- Audit severity: P2. Adjudication: confirmed.
- Root cause: an empty metrics object could be structurally accepted.
- Affected files: `src/noema/eg/enums.py`, `src/noema/eg/trace.py`, `schemas/execution-trace/v0.schema.json`.
- Fix: require all nine metrics, explicit status/value pairs, null only for `UNAVAILABLE`, and a methodology reference for estimates.
- Tests added: trace metric test, estimated-metric regression, E2E 13.
- Before reproduction: omission was indistinguishable from zero or unavailable.
- After result: every produced trace declares each status explicitly.
- Remaining limitation: unavailable host telemetry remains honestly `UNAVAILABLE`.

## R1-10 — dogfood evidence accuracy

- Audit severity: P1. Adjudication: confirmed.
- Root cause: the previous report described a mixed helper suite as full end-to-end coverage.
- Affected files: `DOGFOOD_REPORT.md`, R1 test modules.
- Fix: report every canary with actual level, test, entrypoint, observed result, evidence, tested SHA, and status; create fourteen explicit E2E flows.
- Tests added: `tests/eg/test_rework_r1_e2e.py`.
- Before reproduction: helper-only cases were claimed as E2E.
- After result: dogfood table identifies only E2E flows as E2E.
- Remaining limitation: all canaries are deterministic local dogfood; host-backed provider effects are not claimed.
