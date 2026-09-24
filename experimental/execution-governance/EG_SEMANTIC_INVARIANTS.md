# Execution Governance semantic invariants

This is the normative semantic contract for experimental EG. JSON Schema proves
shape; `src/noema/eg/semantics.py` proves these cross-field rules.

| ID | Statement | Responsible validator | Public entrypoints | Test family |
|---|---|---|---|---|
| INV-EG-001 | WorkOrder id, project id, and content-bound source provenance are preserved. | `programmatic_work_order`, `load_work_order` | `plan` | R3 provenance |
| INV-EG-002 | A blocked required dependency cannot yield a path that calls it. | `ExecutionNeeds`, `resource_disposition_constraint` | `plan` | R3 runtime matrix |
| INV-EG-003 | Resolver success has a usable result; partial has an explicit unresolved set. | `validate_resolver_receipt_semantics` | `plan`, `validate` | R3 resolver matrix |
| INV-EG-004 | Metric status and value have finite, truthful semantics. | `validate_metric_semantics` | `record`, `validate` | R3 metric matrix |
| INV-EG-005 | Parallel isolation has mutually exclusive writing ownership. | `validate_topology_semantics` | `plan`, `validate` | R3 topology matrix |
| INV-EG-006 | Reads suppress only on a stable identity fingerprint. | `ReadIdentity`, `validate_trace_semantics` | `record`, `validate` | R3 ReadSet matrix |
| INV-EG-007 | Resume preserves or reduces authority. | `validate_resume_semantics` | `resume-check` | R2/R3 resume seam |
| INV-EG-008 | A public valid result has passed schema and semantic validation. | `contract_issues` | `plan`, `validate`, `record` | R3 public topology seam |
| INV-EG-009 | Observable provenance is derived from loaded/programmatic input. | `LoadedWorkOrder` | `plan` | R3 provenance |
| INV-EG-010 | Canary claims are rendered from machine-readable results. | `render_dogfood_report` | dogfood evidence | R3 canary evidence |
| INV-EG-011 | Trace r3 material tool and actor coverage requires each observation's exact occurrence `obligation_ref`; a unique name cannot supply it. Trace r2 name association remains historical and cannot certify material PASS. | `evaluate_material_coverage`, `compare_execution` | `record`, `compare`, `validate` | Final conformance repair |
| INV-EG-012 | A complete material report needs an independently pinned host snapshot for PASS. | `verify_host_snapshot` | `compare`, `validate` | T1 observation evidence |
| INV-EG-013 | Mandatory resolver satisfaction binds current bytes and external authority to one receipt. | `required_dependency_results` | `plan`, `validate`, `resume-check` | T1 resolver drift |
| INV-EG-014 | Known deviations remain FAIL despite missing readiness or other evidence. | `compare_execution` | `compare`, `validate` | T1 precedence |
| INV-EG-015 | Explicit actor nonparticipation does not suppress validation of the reported material binding; contradictory attributes retain `ACTOR_BINDING_MISMATCH` alongside `EXPECTED_ACTOR_NOT_EXECUTED`. | `evaluate_material_coverage` | `record`, `compare`, `validate` | Final diagnostic repair |
| INV-EG-016 | Candidate IDs are exact, nonempty and unique within each category at planning, standalone validation and envelope replay. | `validate_candidate_snapshot_semantics` | `plan`, `validate` | vNext candidate identity |
| INV-EG-017 | Duplicate YAML mapping keys cannot silently replace authoritative input. | strict `load_yaml` | all YAML entrypoints | vNext YAML integrity |
| INV-EG-018 | The manifest's `state.<scope>` cursor outranks historical status prose; incomplete or stale execution checkpoints cannot authorize continuation. | `resolve_state_scope`, `recover_current_execution` | `eg recover` | vNext continuity |
| INV-EG-019 | Context pressure only recommends; no material tool need creates no material CALL. | `context_pressure_advisory`, `decide_tools` | `eg recover`, `eg plan` | vNext lifecycle and tool efficiency |
