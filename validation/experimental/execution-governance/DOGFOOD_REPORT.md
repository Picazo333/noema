# Execution Governance R3 dogfood evidence

Generated from `CANARY_RESULTS.json`; do not edit this report manually.
Audited starting SHA: `5d54a1dcc8a6a9550bea138d0ce1899a75e0b437`.

| ID | Scenario | Level | Public entrypoint | Test/evidence | Expected / observed | SHA | Status |
|---|---|---|---|---|---|---|---|
| R3-C01 | WorkOrder to direct trace | END_TO_END | noema eg plan -> record | test_rework_r1_e2e.py::test_e2e_01_cli_valid_work_order_direct_to_trace | valid direct envelope and trace / PASS | 5d54a1d | PASS |
| R3-C02 | Routed tool and model binding | END_TO_END | noema eg plan -> record | test_rework_r2_contract_seams.py::test_r2_07_public_routed_tool_fallback_and_trace | model selected and traced; fallback called / PASS | 5d54a1d | PASS |
| R3-C03 | Runtime dependency matrix | INTEGRATION | planner + semantic kernel | test_r3_structural_closure.py::test_r3_runtime_dependency_matrix | blocked mandatory external dependency is terminal / PASS | 5d54a1d | PASS |
| R3-C04 | Resolver state matrix | INTEGRATION | planner + semantic kernel | test_r3_structural_closure.py::test_r3_resolver_state_matrix | successful states require usable resolution / PASS | 5d54a1d | PASS |
| R3-C05 | Parallel semantic public rejection | END_TO_END | noema eg validate | test_r3_structural_closure.py::test_r3_public_validation_rejects_unprovable_parallel_topology | schema-valid unsafe topology fails / PASS | 5d54a1d | PASS |
| R3-C06 | Metric state matrix | INTEGRATION | trace + semantic kernel | test_r3_structural_closure.py::test_r3_metric_state_matrix | only finite measured/estimated values persist / PASS | 5d54a1d | PASS |
| R3-C07 | Derived provenance and ReadSet evidence | INTEGRATION | planner -> trace | test_r3_structural_closure.py::test_r3_provenance_is_derived_and_trace_preserves_read_evidence | caller ref is ignored; fingerprint persists / PASS | 5d54a1d | PASS |
| R3-C08 | Resume prohibition non-escalation | END_TO_END | noema eg resume-check | test_rework_r2_contract_seams.py::test_r2_07_public_context_trace_resume_secret_and_harvest | preserved passes and removed prohibition fails / PASS | 5d54a1d | PASS |
| R3-C09 | Secret trace protection | END_TO_END | noema eg record | test_rework_r2_contract_seams.py::test_r2_07_public_context_trace_resume_secret_and_harvest | secret input rejected / PASS | 5d54a1d | PASS |
| R3-C10 | Harvest read-only applicability | END_TO_END | noema eg scan-harvest | test_rework_r2_contract_seams.py::test_r2_07_public_context_trace_resume_secret_and_harvest | read_only report / PASS | 5d54a1d | PASS |
