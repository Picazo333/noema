# R3 structural closure

Status: `READY_FOR_STRUCTURAL_REAUDIT` (pending independent adversarial audit).

## Freeze and scope

Starting audited SHA: `5d54a1dcc8a6a9550bea138d0ce1899a75e0b437`.
This change stays inside experimental Execution Governance. It adds no service,
registry, external integration, executor, or domain-state authority.

## Systemic closure

R3 replaces fragmented checks with `src/noema/eg/semantics.py`. Its structured
`SemanticIssue` contract (`code`, `severity`, `path`, `message`, `related_refs`)
is reused by the planner, CLI validation, trace creation, and resume checking.
`ExecutionNeeds` derives required dependencies before runtime disposition.

`LoadedWorkOrder` gives file input a source digest and gives programmatic input
a deterministic content-bound identity. Caller-provided work-order references no
longer establish envelope provenance.

`ReadIdentity` stores a normalized locator plus a stable fingerprint; traces
persist the fingerprint without retaining freshness payloads. Parallel topology
now validates an ownership map rather than a flattened set. Metrics use the
frozen `MEASURED | ESTIMATED | UNAVAILABLE` vocabulary and reject non-finite
or non-numeric values.

## Public parity

`noema eg plan`, `validate`, and `record` perform structural plus semantic
validation. `resume-check` invokes the same non-escalation semantics. The
runtime-pressure public loader invokes its semantic validator after schema
validation. No public EG command treats schema validity alone as protocol
validity.

## Coverage

`tests/eg/test_r3_structural_closure.py` supplies parameterized matrices for
resolver state, runtime dependencies, metrics, ReadSet identity, topology, and
provenance. It includes a public CLI seam where JSON Schema accepts a topology
that semantic validation rejects. R2's public routed canary now asserts and
persists selected model identity.

`CANARY_RESULTS.json` is the source of truth for dogfood evidence;
`DOGFOOD_REPORT.md` is checked against the deterministic renderer.

## Sol finding disposition

| Finding | R3 closure |
|---|---|
| Global external block bypass | `ExecutionNeeds.external_required` drives runtime terminality. |
| Parallel ownership / CLI bypass | Pairwise ownership-map semantics run in planner and public validation. |
| Non-numeric measured metric | Schema plus semantic finite-number rule. |
| Empty successful resolver result | Frozen receipt vocabulary and usable-reference invariant. |
| Lost freshness evidence | Persisted stable `identity_fingerprint`. |
| Caller-controlled WorkOrder ref | `LoadedWorkOrder` derived provenance. |
| Dogfood overclaim | Generated report and an assertion of model selection/tracing. |

## Remaining limitations

The profile remains experimental and does not execute tools or independently
verify external candidate claims. Runtime inputs remain caller-supplied
ephemeral evidence, now constrained by one contract and derived needs.
