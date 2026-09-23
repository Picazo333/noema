---
status: PROPOSAL_ONLY
date: 2026-09-23
source_skill: execution-process-auditor
source_repo: Picazo333/skill-foundry
source_branch: candidate/execution-process-auditor-2026-09-23
target: experimental_execution_governance
implementation_authorized: false
---
# Noema Module Candidate — Execution Process Audit

## Decision sought

Evaluate whether the Skill Foundry capability `execution-process-auditor` should be exposed inside Noema as an **opt-in Execution Governance diagnostic module**.

This proposal intentionally does **not** implement the module. The user's requested two-week activity audit must run first and may refine the module boundary.

## Boundary

Noema must not copy or own Skill semantics.

Skill Foundry owns:
- trigger/non-trigger semantics;
- audit methodology;
- process-audit modes;
- KEEP / MODIFY / REMOVE / ADD analysis;
- audit red-team procedure;
- reusable-harvest semantics.

Noema may own only the protocol/runtime-facing integration needed to supply trustworthy execution evidence and record a handoff/result reference.

## Why this belongs near Execution Governance

The current EG branch already provides relevant evidence primitives:
- `ExecutionEnvelope`;
- `ExecutionTrace`;
- tool decisions;
- trace validation/comparison;
- runtime pressure;
- context/read evidence;
- economics vector;
- work-order provenance;
- topology/authority controls.

The proposed auditor consumes those facts to answer a higher-level question:

> Is the execution process buying enough quality/information/recoverability for its tool, context, human-attention and governance cost?

This is diagnostic interpretation over existing evidence, not a second runtime.

## Proposed module shape

Working internal name:

`eg.process_audit`

or CLI-facing:

`noema eg process-audit`

Naming is provisional and must not create a new public protocol artifact type.

### Inputs

Use existing authorities/references where available:
- WorkOrder;
- ExecutionEnvelope;
- ExecutionTrace;
- project manifest/state refs;
- optional Handoff/EvalResult refs;
- optional external cost evidence;
- explicit audit objective/scope.

### Skill binding

Noema should resolve/reference:

`capability: execution-process-auditor`

through the existing Skill Foundry capability boundary. Noema does not add a second capability catalog.

### Outputs

No new public schema.

Preferred output:
- a diagnostic report/ref produced by the Skill execution;
- optional existing Handoff/EvalResult reference;
- existing trace/evidence refs retained for provenance.

The report itself remains Skill-owned content, not Noema protocol authority.

## Candidate Noema responsibilities

### 1. Evidence projection
Prepare the minimum verified projection from existing EG evidence:
- actual tool calls;
- suppressed calls;
- retries/rework;
- human interventions;
- context units/tokens when available;
- monetary cost when measured/estimated with methodology;
- outcome;
- tool-decision reasons;
- topology/write scopes;
- material deviations;
- trace coverage status.

### 2. Scoped-state references
Expose declared current-state authorities from project manifests without inventing a global state owner.

Rule:
`one authoritative cursor per declared scope`.

Noema may detect unresolved/conflicting declared state refs, but project/domain authority resolves meaning.

### 3. Process-audit work order
Create/accept an ordinary WorkOrder asking for the `execution-process-auditor` capability.

Do not create a second orchestration path.

### 4. Result provenance
Bind the returned report/handoff to:
- source WorkOrder;
- envelope/trace refs;
- observed commit/SHA when applicable.

## Explicit non-goals

The module must not:
- create another executor router;
- create another context router;
- own a Skill registry;
- add a tool/model catalog;
- add a capability-resolution public schema;
- introduce a daemon/agent runtime;
- own domain-state truth;
- store personal activity history;
- persist user-specific personal instructions;
- automatically mutate project plans based on audit recommendations;
- bypass human approval for PLAN_DEVIATION.

These constraints preserve the current Execution Governance Plan Lock and ADR-0008 boundaries.

## Relationship to current `audit_project`

The existing project audit checks:
- manifest/lint conformance;
- context modes/cost;
- quality-claim declarations;
- routing availability.

The proposed process-audit module is not a replacement.

Difference:

`audit_project`
→ protocol/project conformance inspection.

`execution-process-auditor`
→ evidence-backed analysis of how a particular body of work was actually executed and how to improve that process.

The two may share evidence, but should not be merged into one giant audit command without demonstrated need.

## Economics integration

Reuse the current component-vector approach in `src/noema/eg/economics.py`.

Relevant fields:
- context_units;
- input_tokens;
- output_tokens;
- monetary_cost;
- wall_time_ms;
- human_interventions;
- tool_calls;
- suppressed_calls;
- retries;
- rework_cycles;
- outcome.

Do **not** generate a fabricated aggregate efficiency score.

The Skill may interpret the vector qualitatively and identify:
- avoidable calls;
- unnecessary context;
- human-attention rent;
- rework loops;
- high-value expensive calls worth preserving.

## Tool governance integration

Reuse existing EG semantics:

`allowed && available && qualification == VERIFIED`

and current decisions:
- CALL;
- SOFT_SUPPRESS;
- DEFER;
- HARD_DENY.

The Skill may audit whether the caller-supplied candidate set/question was well-formed, but Noema must not become the owner of external tool qualification truth.

## Proposed trigger

Opt-in only.

Valid triggers:
- explicit process/workflow audit WorkOrder;
- explicit postmortem WorkOrder;
- explicit cross-project execution review where evidence refs are supplied.

Not automatic after every run.

Automatic invocation would create governance rent and is not justified by current evidence.

## Activity-window boundary

The Skill's `ACTIVITY_WINDOW_AUDIT` mode should **not** become a Noema runtime module responsibility.

Reason:
- Noema explicitly does not own personal operational state;
- cross-conversation/personal activity sources may live outside project repos;
- the Skill can consume those sources via an external host/workflow when explicitly requested.

Only reusable findings approved by the human should later feed Noema proposals.

## Adoption gates

Before implementation:

1. complete the requested two-week activity audit using the packaged Skill methodology;
2. identify whether the same process-failure classes recur beyond DIVINIVID/Nexova;
3. confirm that EG already exposes enough evidence without new public schemas;
4. define one concrete dogfood WorkOrder and expected report;
5. run capability-dedup review against any newly discovered Noema audit concepts;
6. obtain explicit human approval for implementation.

## Provisional decision

**CANDIDATE: ADOPT AS OPT-IN EG DIAGNOSTIC MODULE VIA CAPABILITY REFERENCE**

Confidence: medium-high.

Why not implement now:
the upcoming two-week activity audit is intentionally part of the evidence-gathering gate and may reveal a smaller or better boundary.
