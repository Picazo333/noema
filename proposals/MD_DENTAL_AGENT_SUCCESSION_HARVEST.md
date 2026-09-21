# Noema proposal — Agent Succession, Execution Frontier, and Resume Verification

Status: **consumer-derived proposal; not RC0 canon**  
Source consumer: `Picazo333/MD_APP-AFTER-GROK`  
Observed transition: Cursor/Grok 4.6 -> Cursor/GPT-5.6 Sol Medium; Claude -> Jules.

## Why this belongs in Noema

MD Dental exercised four existing Noema invariants under real executor depletion:

- capability before executor;
- progressive context;
- durable coordination in artifacts rather than conversations;
- replaceable executors.

Those invariants held conceptually, but the consumer had to invent project-local machinery to make replacement safe in practice.

The missing operational layer is not a new agent runtime. It is a small set of **coordination contracts** describing how role authority, executor identity, model identity, live execution state, and historical evidence survive replacement.

## Observed failure modes

1. **Role/executor/model collapse.** Project contracts named Cursor/Claude/Grok directly, making a provider change look like an architectural change.
2. **Conversation-dependent resume.** A replacement could require reading large chat/history instead of a bounded cold-start context.
3. **Stale state files.** `PROJECT_STATE.md`, `NEXT_ACTION.md`, branch state, and exact-SHA evidence could disagree.
4. **Historical verdict rewrite risk.** Replacing an auditor creates pressure to restamp or relabel earlier PASS/RED evidence.
5. **Model swap conflated with executor replacement.** Same Cursor lane changing models is materially different from replacing the independent auditor.
6. **No explicit execution frontier.** A single next-action file did not capture canonical branch, isolated branches, peer evidence, blocked contracts, and unconsumed reviews.
7. **No resume proof.** A new executor could say “understood” without demonstrating that it recovered the right active node, gates, ownership, and closed claims.
8. **Context waste.** Safe resume context was not explicitly split into hot/warm/cold/not-preloaded sets.

## Consumer solution validated in MD Dental

MD Dental added a compact `agent/` layer:

- `ROLE_REGISTRY.yaml`
- `CURRENT_FRONTIER.md`
- `CONTEXT_MANIFEST.yaml`
- `HANDOFF_CONTRACT.md`
- `AGENT_TRANSITION_PROTOCOL.md`
- `RESUME_EVAL.md`
- `EVIDENCE_INDEX.md`
- explicit transition records

The core invariant is:

> **Role != executor != model.**

Example:

- role: Builder / Integrator
- executor: Cursor
- model: GPT-5.6 Sol / Medium

Changing the model does not change the role, branch, WorkOrder ownership, or review semantics.

Replacing the auditor does change the executor binding and requires predecessor freeze + successor branch + resume validation, while preserving historical verdict authorship.

## Candidate Noema concepts

### 1. RoleBinding
Maps stable project authority to a replaceable executor binding.

Minimum fields:
- role id;
- authority/scope;
- active executor;
- branch/workspace ref when material;
- historical bindings.

### 2. ExecutorBinding
Describes the active execution surface separately from capability/role.

Must not become provider-specific core architecture.

### 3. ModelBinding
Optional provenance attached to an executor run/binding.
A model swap is not itself a project architecture change.

### 4. ExecutionFrontier
A compact projection of the currently actionable distributed state:

- canonical role branches;
- exact material SHAs;
- active isolated branches;
- reviewed/unreviewed peer evidence;
- active node;
- blocked contract;
- human gates;
- exact next action.

It is a **derived coordination projection**, never a replacement for domain authority or immutable evidence.

### 5. ContextTemperature
A portable convention over existing Noema progressive context:

- hot: required on every resume;
- warm: load for active node/contract;
- cold: historical, only on demand;
- never-preload: high-volume history not needed for safe start.

This does not replace existing L0-L4; it is an operational loading policy layered on them.

### 6. AgentTransition
Two distinct transition kinds:

**MODEL_SWAP**
- same role/executor;
- preserve authority/branch;
- record provenance;
- refresh frontier;
- resume eval.

**EXECUTOR_SUCCESSION**
- freeze predecessor;
- preserve historical provenance;
- instantiate successor binding/lane;
- succession handoff;
- resume eval;
- new material keys only after takeover.

### 7. ResumeEval
A bounded verification that the incoming executor recovered:
- role;
- branch;
- integration authority;
- active node;
- closed claims;
- blocker;
- human gates;
- prohibited scope;
- exact next action;
- peer-review requirement.

A narrative “understood” is insufficient.

### 8. HistoricalVerdictImmutability
Executor/model replacement never rewrites the author or validity domain of historical evidence.
A verdict remains bound to its exact SHA and original producer.

### 9. PeerIndependence
Independent review should be defined by:
- separate role execution;
- no self-review;
- exact-SHA targeting;
- appropriate independent reproduction;
- provenance.

Provider/model diversity may strengthen review but is not its definition.

## Relationship to existing Noema RC0

These findings mostly **operationalize**, rather than contradict, RC0:

- Protocol 3: capability before executor.
- Protocol 6: progressive context.
- Protocol 7: durable coordination in artifacts.
- Protocol 9: proportional provenance.
- Protocol 10: derived views never silently become authority.
- Protocol 16: repeated exceptions improve Noema.
- Protocol 18: material relations are declared.

No new runtime, database, event bus, agent host, or persistent service is proposed.

## Recommended treatment

For the current frozen RC0:
- keep this as consumer harvest/proposal;
- do not mutate RC0 semantics silently.

For the next protocol planning cycle:
1. decide whether RoleBinding + AgentTransition belong in core or an optional coordination profile;
2. test ExecutionFrontier as a derived projection in a second real consumer;
3. test ResumeEval across at least two executor replacements;
4. measure cold-start context before/after;
5. only then promote schemas/validator support.

## Acceptance evidence for promotion

Suggested activation evidence:
- >=2 real projects replace an executor/model using the contracts;
- no historical verdict rewrite;
- no authority collision;
- replacement resumes without chat reconstruction;
- measurable context reduction;
- no false shared-gate PASS;
- deterministic validation of references/bindings;
- weekly maintenance remains within Noema's bounded-admin principle.

## Non-goals
- adaptive model routing;
- quota ingestion;
- persistent agent runtime;
- centralized project state;
- executor-specific core logic;
- replacing domain WorkOrders/evidence semantics.
