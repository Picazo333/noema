# Execution Governance R2 dogfood evidence

Status: `READY_FOR_REAUDIT`. This matrix supersedes the R1 canary labels.
`R2_SOURCE_SHA` is `7507cd03ab4cf4747fb6571bb8a8908635ae6916`, the exact
source commit tested below.

| ID | Scenario | Level | Public entrypoint | Test path | Behavior asserted | Expected / observed | Evidence | SHA | Status |
|---|---|---|---|---|---|---|---|---|---|
| R2-C01 | WorkOrder → DIRECT → Trace | END_TO_END | `noema eg plan` → `record` | `tests/eg/test_rework_r1_e2e.py::test_e2e_01_cli_valid_work_order_direct_to_trace` | validates both generated artifacts | direct + valid trace / PASS | CLI YAML + schema | R2_SOURCE_SHA | PASS |
| R2-C02 | WorkOrder → ROUTED → tool/model → Trace | END_TO_END | `noema eg plan` → `record` | `tests/eg/test_rework_r2_contract_seams.py::test_r2_07_public_routed_tool_fallback_and_trace` | routed model and fallback tool are bound then traced | ROUTED + valid trace / PASS | CLI YAML + schema | R2_SOURCE_SHA | PASS |
| R2-C03 | Invalid WorkOrder | END_TO_END | `noema eg plan` | `tests/eg/test_rework_r1_e2e.py::test_e2e_03_cli_rejects_each_invalid_work_order_before_planning` | every primary required field rejects before planning | CLI code 2 / PASS | parametrized CLI assertions | R2_SOURCE_SHA | PASS |
| R2-C04 | Required blocked runtime resource/interface/global block | END_TO_END | `noema eg plan --runtime-pressure` | `tests/eg/test_rework_r2_contract_seams.py::test_r2_02_runtime_pressure_public_contract_to_envelope` | runtime schema reaches final disposition | DEFER/BLOCKED as applicable / PASS | public runtime files + envelope | R2_SOURCE_SHA | PASS |
| R2-C05 | Resolver BLOCKED | END_TO_END | `noema eg plan --resolver-receipt` | `tests/eg/test_rework_r2_contract_seams.py::test_r2_01_resolver_participation_is_explicit_and_terminal` | required blocked receipt is terminal | BLOCKED / PASS | CLI envelope | R2_SOURCE_SHA | PASS |
| R2-C06 | No verified executor | END_TO_END | `noema eg plan --task-metadata` | `tests/eg/test_rework_r2_contract_seams.py::test_r2_07_public_no_verified_executor_and_topology_rejection` | RC0 router status survives public planning | `BLOCKED_NO_VERIFIED_EXECUTOR` / PASS | CLI envelope | R2_SOURCE_SHA | PASS |
| R2-C07 | Denied authority tool → allowed fallback | END_TO_END | `noema eg plan --candidate-snapshot` | `tests/eg/test_rework_r2_contract_seams.py::test_r2_07_public_routed_tool_fallback_and_trace` | denial cannot suppress eligible fallback | HARD_DENY + CALL / PASS | CLI envelope | R2_SOURCE_SHA | PASS |
| R2-C08 | Parallel isolation rejection | END_TO_END | `noema eg plan --task-metadata` | `tests/eg/test_rework_r2_contract_seams.py::test_r2_07_public_no_verified_executor_and_topology_rejection` | overlapping scopes reject before envelope | CLI code 2 / PASS | CLI failure assertion | R2_SOURCE_SHA | PASS |
| R2-C09 | Context promotion + ReadSet | END_TO_END | `noema eg plan` → `record` | `tests/eg/test_rework_r2_contract_seams.py::test_r2_07_public_context_trace_resume_secret_and_harvest` | promotion and same-integrity suppression persist | transition + suppression / PASS | CLI envelope + trace | R2_SOURCE_SHA | PASS |
| R2-C10 | Resume success | END_TO_END | `noema eg resume-check` | `tests/eg/test_rework_r2_contract_seams.py::test_r2_07_public_context_trace_resume_secret_and_harvest` | matching continuation state resumes | CLI code 0 / PASS | CLI report | R2_SOURCE_SHA | PASS |
| R2-C11 | Resume failure | END_TO_END | `noema eg resume-check` | `tests/eg/test_rework_r2_contract_seams.py::test_r2_07_public_context_trace_resume_secret_and_harvest` | removed inherited prohibition fails | CLI code 1 / PASS | CLI report | R2_SOURCE_SHA | PASS |
| R2-C12 | Secret-bearing trace | END_TO_END | `noema eg record` | `tests/eg/test_rework_r2_contract_seams.py::test_r2_07_public_context_trace_resume_secret_and_harvest` | secret input never produces trace | CLI code 2 / PASS | CLI failure assertion | R2_SOURCE_SHA | PASS |
| R2-C13 | Unavailable metrics | END_TO_END | `noema eg record` | `tests/eg/test_rework_r2_contract_seams.py::test_r2_08_missing_metrics_stay_unavailable_through_public_record_cli` | absent telemetry remains explicit unavailable | null + UNAVAILABLE / PASS | CLI trace + schema | R2_SOURCE_SHA | PASS |
| R2-C14 | Harvest applicability | END_TO_END | `noema eg scan-harvest` | `tests/eg/test_rework_r2_contract_seams.py::test_r2_07_public_context_trace_resume_secret_and_harvest` | public scan remains read-only | read_only true / PASS | CLI report | R2_SOURCE_SHA | PASS |

Supporting integration coverage for strict trace structures, ReadSet identity,
resume effective binding, topology schema/runtime parity, and resolver receipt
semantics is in `tests/eg/test_rework_r2_contract_seams.py`. No helper-only
test is labelled END_TO_END in this table.
