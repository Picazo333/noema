---
status: PROPOSAL_ONLY
date: 2026-09-23
source: two_week_activity_audit
source_window: 2026-09-09..2026-09-23
implementation_authorized: false
---
# Noema Improvement Harvest — Two-Week Activity Audit

## Boundary
This document exports only reusable execution-governance findings.

It does not export:
- personal private/sensitive context;
- personal WIP state;
- project-specific aesthetics;
- client/project domain state;
- StackIA's external catalog;
- Skill Foundry Skill semantics.

## Executive finding

Across multiple projects, the dominant scarce resources were:
1. human attention;
2. coherent current state;
3. bounded context transfer.

The main Noema opportunity is therefore not broader orchestration. It is stronger conformance/diagnostic support around existing Execution Governance evidence.

---

## KEEP — current EG evidence model

Current EG already has useful primitives:
- ExecutionEnvelope;
- ExecutionTrace;
- tool qualification/decision;
- context/read evidence;
- retries/rework;
- human interventions;
- economics vector;
- topology/write scopes;
- validation/comparison.

Do not add a parallel audit evidence model.

---

## ADD CANDIDATE N1 — Execution Process Audit integration

Adopt `execution-process-auditor` as an opt-in capability reference/module candidate.

Integration must:
- consume existing WorkOrder/Envelope/Trace evidence;
- return a Skill-owned diagnostic report/handoff;
- add no new public artifact type;
- add no router/catalog/runtime.

See:
`experimental/execution-governance/proposals/EXECUTION_PROCESS_AUDITOR_MODULE_CANDIDATE.md`.

Priority: HIGH.

---

## ADD CANDIDATE N2 — Scoped State Authority conformance

Problem observed repeatedly:
- multiple legitimate state scopes exist;
- narrative documents sometimes retain stale ACTIVE/next-step flags;
- agents can confuse historical state with the current cursor.

Proposed consumer-manifest convention:

```yaml
state_scopes:
  project:
    current_ref: ...
  brand:
    current_ref: ...
  execution:
    current_ref: ...
```

Semantics:
- exactly one current cursor per declared scope;
- cross-scope dependencies explicit;
- historical documents cannot override the current cursor;
- Noema validates declared references/shape/conformance;
- Noema does not decide domain meaning.

Implementation note:
evaluate whether this can remain an extension/convention before changing the public protocol schema.

Priority: HIGH.

---

## MODIFY CANDIDATE N3 — Human-attention economics visibility

Current EG already tracks:
`human_interventions`.

The process audit shows this metric should be treated as a first-class diagnostic signal.

Do not invent a scalar score.

Diagnostic report may compare:
- human interventions;
- retries;
- rework cycles;
- tool calls;
- suppressed calls;
- outcome.

Classification of an intervention as avoidable/required belongs to the Skill/report, not the core trace.

Priority: MEDIUM-HIGH.

---

## ADD CANDIDATE N4 — Rework-triggered process audit

Do **not** automatically process-audit every run.

Candidate triggers:
- explicit WorkOrder/user request;
- second material rework cycle;
- PLAN_DEVIATION / architecture exception;
- repeated paid-tool failure;
- unresolved state/authority contradiction.

Exact thresholds must be project/configurable. Do not hard-code a universal token/tool threshold without evidence.

Priority: MEDIUM.

---

## RESEARCH CANDIDATE N5 — Ephemeral human-attention/runtime pressure

Observed:
parallel AI work can exceed the human's review/gating bandwidth even when executors themselves are available.

Potential host-supplied ephemeral inputs:
- pending human gates;
- number of material workstreams awaiting review;
- attention pressure class.

Allowed use:
- suppress optional context expansion;
- suppress optional tool/challenger calls;
- favor direct/low-complexity execution when semantics permit.

Forbidden:
- personal task scheduling;
- owning WIP/backlog;
- persisted personal quotas;
- becoming Regula.

This must remain runtime pressure, not durable project truth.

Priority: RESEARCH / MEDIUM.

---

## KEEP / INTEGRATE N6 — StackIA verified capability projection

Activity evidence strongly validates:

`CONFIGURED != VERIFIED != AUTHORIZED`.

Noema EG already requires:
- allowed = true;
- available = true;
- qualification = VERIFIED.

Therefore do not invent a new lifecycle schema in Noema.

Instead:
- StackIA owns external tool lifecycle/pricing/account truth;
- export only verified/purpose-scoped candidates;
- Noema consumes that projection.

Priority: HIGH integration, LOW protocol change.

---

## MODIFY CANDIDATE N7 — Process economics diagnostic view

Reuse the existing economics vector:
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

Add report-level interpretation only:
- likely avoidable calls;
- context duplication;
- rework concentration;
- high-cost calls with demonstrated reuse/value.

Do not store `decision_changed` or `value_score` as protocol truth unless later evidence proves a stable observable definition.

Priority: MEDIUM.

---

## REMOVE / DO NOT BUILD

Do not add:
- Noema WIP manager;
- personal priority engine;
- external tool/model catalog;
- Skill registry mirror;
- new public ProcessAudit protocol artifact;
- second execution router;
- automatic always-on process auditing;
- universal fixed iteration/repair limits.

These would violate current ownership boundaries or add governance rent.

---

## Proposed adoption sequence

```text
1. Complete two-week activity audit            DONE
2. Package Foundry Skill candidate             DONE / G9 pending
3. G9 independent Skill audit                  PENDING
4. Review this Noema harvest                    PENDING HUMAN
5. Validate scoped-state convention on 2–3 repos
6. Dogfood process-audit module with one WorkOrder
7. Re-audit against EG Plan Lock / ADR-0008
8. Only then authorize implementation
```

## Current recommendation

Highest-value next Noema changes:
1. scoped state authority/conformance;
2. Skill-backed process-audit diagnostic integration;
3. verified StackIA capability projection;
4. expose human-attention/rework economics in diagnostics.

Do not expand Noema beyond these until dogfood produces evidence.
