# Execution Governance R1 dogfood evidence

Status: `READY_FOR_REAUDIT` pending final freeze. This supersedes the former
claim that all 22 canaries were end-to-end. The level here states what each test
actually exercises. `R1_IMPLEMENTATION_SHA` is the exact tested implementation
commit `3d1c60d7584eadb29fdd82b0a92677b96ba721e8`.

| ID | Scope | Level | Exact test | Entrypoint | Expected / observed result | Evidence | SHA | Status |
|---|---|---|---|---|---|---|---|---|
| C01 | Valid WorkOrder direct trace | END_TO_END | `test_e2e_01_cli_valid_work_order_direct_to_trace` | `noema eg plan` → `record` | direct envelope and valid trace | CLI files + schema assertion | R1_IMPLEMENTATION_SHA | PASS |
| C02 | Scoped reversible control | UNIT | `test_remaining_direct_context_and_control_canaries` | `evaluate_control` | `ALLOW_SCOPED` | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C03 | Deliberation | UNIT | `test_remaining_direct_context_and_control_canaries` | `classify_deliberation` | `DEEP` | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C04 | Direct/broad suppression | UNIT | `test_tool_selector_suppresses_broader_duplicate_source` | `decide_tools` | broad candidate suppressed | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C05 | Completed work | UNIT | `test_remaining_direct_context_and_control_canaries` | `decide_disposition` | `NO_ACTION` | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C06 | Secret trace safety | END_TO_END | `test_e2e_12_secret_bearing_trace_is_rejected` | envelope → `create_trace` | secret trace rejected | `ValueError` cases | R1_IMPLEMENTATION_SHA | PASS |
| C07 | Canonical mutation | UNIT | `test_security_controls_are_orthogonal_and_conservative` | `evaluate_control` | `REQUIRE_HUMAN` | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C08 | Foreign mutation | UNIT | `test_security_controls_are_orthogonal_and_conservative` | `evaluate_control` | `ROUTE_ELSEWHERE` | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C09 | Resolver receipt | INTEGRATION | `test_receipt_topology_model_and_executor_boundaries` | `validate_resolver_receipt` | opaque validated reference | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C10 | Resolver not required | UNIT | `test_remaining_direct_context_and_control_canaries` | `build_execution_envelope` | no forced receipt | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C11 | No verified executor | END_TO_END | `test_e2e_06_missing_verified_executor_is_rc0_blocked` | envelope → RC0 router | `BLOCKED_NO_VERIFIED_EXECUTOR` | integrated assertion | R1_IMPLEMENTATION_SHA | PASS |
| C12 | Model candidate binding | END_TO_END | `test_e2e_02_routed_tool_and_model_to_trace` | envelope → model router → trace | selected runtime model | integrated trace assertion | R1_IMPLEMENTATION_SHA | PASS |
| C13 | Independent audit topology | UNIT | `test_receipt_topology_model_and_executor_boundaries` | `derive_topology` | `AUDITED_SINGLE` | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C14 | Parallel isolation | END_TO_END | `test_e2e_08_parallel_overlap_rejects_envelope` | envelope → topology | overlap rejected | `ValueError` | R1_IMPLEMENTATION_SHA | PASS |
| C15 | Resume stale state | END_TO_END | `test_e2e_11_resume_wrong_state_rejects` | envelope → `resume_check` | FAIL for stale/wrong/gate state | parametrized assertions | R1_IMPLEMENTATION_SHA | PASS |
| C16 | Harvest applicability | END_TO_END | `test_e2e_14_harvest_remains_read_only` | `scan_harvest` | read-only true | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C17 | Patch HOT context | UNIT | `test_remaining_direct_context_and_control_canaries` | `build_context_plan` | required refs HOT | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C18 | Recover HOT context | UNIT | `test_remaining_direct_context_and_control_canaries` | `build_context_plan` | recovery ref HOT | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C19 | Duplicate read | INTEGRATION | `test_trace_is_structured_and_explicit_about_unavailable_metrics` | `create_trace` + ReadSet | suppression recorded | trace assertion | R1_IMPLEMENTATION_SHA | PASS |
| C20 | Conserve posture | UNIT | `test_read_set_and_runtime_pressure_are_conservative` | `derive_resource_policy` | external calls conserved | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C21 | Throttle posture | UNIT | `test_throttled_and_blocked_runtime_do_not_expand_work` | runtime policy | external calls deferred | assertion | R1_IMPLEMENTATION_SHA | PASS |
| C22 | Blocked platform precedence | END_TO_END | `test_e2e_04_runtime_blocked_required_resource_is_terminal` | envelope → runtime constraint | required BLOCKED; optional continues direct | integrated assertion | R1_IMPLEMENTATION_SHA | PASS |

The fourteen mandatory R1 E2E flows are explicit in
`tests/eg/test_rework_r1_e2e.py`: C01 (direct), C12 (routed), invalid WorkOrder
rejection, C22 (runtime blocked), resolver blocked, C11, denied-tool fallback,
C14, progressive context/ReadSet, resume pass/rejection, C06, metrics
unavailable, and C16. These are local deterministic tests; no provider usage,
external mutation, or downstream adoption is claimed.
