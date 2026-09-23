# NOEMA vNext — R5 Evidence-Binding Closure implementation

Status: implementation candidate for independent R5 adversarial reauditing. Execution Governance remains experimental, opt-in, and limited to two artifact types. RC0 remains `0.1.0-rc.0`.

## Gate record

| Gate | Evidence in this commit |
|---|---|
| G0 — trust lock | `EG_EVIDENCE_MODEL.md`, bounded ADR/Plan Lock reopening, production-verifier tests for observed bytes, host-pinned human approval, and independent external qualification projection. |
| G1 — public regressions | `test_r5_public_regressions.py` drives `python -m noema eg` through the seven R4 P1 families; revision-2 schemas are distinct from historical v1. |
| G2 — evidence foundation | `evidence.py`, `bindings.py`, and `persistence.py` provide predicate-specific verification, domain-separated digests, input projection, and atomic persistence. |
| G3 — readiness | Public direct, routed, human-approved, parallel, and resume positives; negative current-context checks for nominal, missing, stale, and mismatched evidence. |
| G4 — trace/CLI | Exact envelope/material trace binding, observation coverage, event-bound historical read identity, sanitized diagnostics, explicit `--require-ready`, and compatible legacy readers. |
| G5 — freeze | Run the five validation commands before the single local commit. Post-commit canaries must run from a clean isolated checkout at the exact final SHA and write outside Git. The observed G5 result is not asserted by this tracked file. |

## Trust bootstrap and positive paths

The relying host/operator selects `VerificationContext` outside the evaluated project and must pin its identity. The evaluated artifact cannot nominate accepted evidence. `CONTENT_INTEGRITY` hashes observed bytes; human approvals bind the material digest, gate, action, and attempt; candidate qualification and availability bind a specific candidate projection and required use. A trusted host assertion can bind a historical read event, but a caller-supplied hash cannot. `resume-check` additionally requires host-pinned current state and Handoff bytes. These are tests of the defined trust boundary, not claims that Noema owns external authority.

Public positive tests include `test_direct_ready_requires_host_context`, `test_routed_ready_requires_candidate_specific_external_proof`, `test_resume_ready_rechecks_current_envelope_and_handoff`, `test_human_approval_is_bound_to_exact_material_intent`, `test_resume_after_exact_human_approval`, `test_resolver_requires_usable_result_satisfied_set_and_external_proof`, `test_parallel_isolation_requires_host_bound_proof`, and `test_historical_read_suppression_needs_event_bound_host_observation`.

## Seven R4 P1 closure families

| Family | Public-path regression |
|---|---|
| Gates/resume | Explicit gates, terminal disposition, wrong attempt, stale approval, pinned continuation. |
| Trace/envelope | Exact digest/reference, outcome coverage, unexpected executor/model/tool. |
| Credentials | Recursive field/text/URL rejection, sanitized diagnostics, atomic output. |
| Replay | Source, context, baseline, material digest, and derived-control tamper. |
| Dependencies/qualification | Nominal resolver/model, verified and partial resolver, wrong/stale candidate. |
| Parallel isolation | Actor/scope ownership, host proof, shared workspace/branch, out-of-scope and overlapping writes. |
| ReadSet | Claimed hash does not suppress; event-bound trusted identity may suppress; comparison without trust remains incomplete. |

## Version and compatibility

`execution-envelope/v0` and `execution-trace/v0` remain legacy structural readers. Historical v1 revision 1 schemas were not edited and return `LEGACY_V1_UNVERIFIED`, never R5 readiness. New `execution-envelope/v1` and `execution-trace/v1` with `contract_revision: 2` use new schemas. Unknown revisions are rejected. No WorkOrder, Handoff, EvalResult, RC0, registry, or external-domain contract was reopened.

## Changed areas and verification

The bounded ADR and Plan Lock, evidence model, two revision-2 schemas, EG planner/evaluator/trace/recovery/CLI, three evidence modules, public regression tests, and `R5_CANARY_DEFINITIONS.json` comprise the implementation. Before committing, run:

```text
ruff check .
pytest
python -m noema lint .
python -m noema audit .
git diff --check
```

`R5_CANARY_DEFINITIONS.json` is scenario-only; it contains no observed PASS or final SHA. The post-commit runner rejects a wrong SHA, wrong import checkout, failed/empty/skipped required case, or tree mutation, and preserves external results on failure.

## Known limits and reauditing

The CLI result is relative to a host-selected trust context. A separate consumer must pin the expected trust-root identity; arbitrary standalone invocation is not an external authority. Fixture projections demonstrate the mechanics without asserting live StackIA or other provider integration. Credential detection covers the defined families, not every possible encoded secret. Stateless Noema cannot prove single-use consumption of an approval. Current byte integrity alone does not prove a past agent read; historical suppression requires a separately accepted event-bound assertion. No verified executor currently exists in the project registry; routed positives therefore use evidence-bound tools and resolver output, not a fabricated executor.

The final SHA cannot be written into a file inside its own commit. The exact final/parent SHA, clean canary checkout, results, and imported module path belong in external post-commit evidence. The pre-existing `Noema-vNext-R4-2cf6e84.zip` in the repository root is user-owned and must not be included in the R5 commit; use an isolated clean checkout for canaries. For independent reauditing, inspect the frozen commit, run the five validation commands on that SHA, execute all R5 canaries from the same clean checkout, and adversarially challenge the host trust boundary and all seven P1 families. Do not merge or push based on this tracked report alone.

## T1 implementation and post-commit procedure

T1 keeps envelope v1-r2 and adds trace v1-r3 for occurrence-level tool and
actor observations. Comparison recalculates reported coverage and requires
independently host-pinned `EXECUTION_OBSERVATIONS` for material PASS. Mandatory
resolver readiness binds current bytes and an authority assertion to the same
receipt. The 30-scenario definitions file contains no observed results.

After local regression, freeze a single commit. Use an isolated clean checkout
and `.github/scripts/verify_t1.py` with the full SHA and an empty external
output directory. Only after that local gate passes, publish exactly the
experimental branch at that SHA. `.github/workflows/ci.yml` runs the same gate
on Ubuntu and uploads four allowlisted evidence files to the matching run.
Cross-check run ID, attempt, head SHA, artifact ID and remote ref before asking
for independent Sol reaudit. A correction requires a new SHA and fresh local
and CI evidence. CI success does not certify external authority or architecture.
