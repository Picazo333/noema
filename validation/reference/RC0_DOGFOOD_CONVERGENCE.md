# Noema RC0 — Reference Dogfood Convergence

**Reference A:** Skill Foundry  
**Reference B:** Agency Foundation  
**Mode:** read-only reference audits  
**Protocol:** `0.1.0-rc.0`

## Gate result

**PASS — RC0 architecture remains closed.**

| Gate | Result |
|---|---|
| P0 architecture defects | 0 |
| P1 Noema architecture defects | 0 |
| Project-profile gaps | 0 |
| Required domain-ontology duplication | 0 |
| Required runtime dependency on Noema | 0 |
| Repeated exception needed to describe projects | 0 |
| Authority collisions introduced by Noema | 0 |

## What both repositories proved

### 1. `type + traits + quality claims + extensions` generalizes

Skill Foundry is naturally described as a reusable agentic capability library. Agency Foundation is naturally described as a creative/research-heavy delivery system. Neither requires a custom project species or protocol fork.

### 2. Domain authority can remain federated

Skill Foundry keeps its taxonomy, ontology, lifecycle and Skill Registry. Agency keeps Brand/business/validation/Asset Factory authority. Noema only supplies the interoperability/conformance layer.

### 3. Progressive context addresses a real measured problem

Both projects have correct but accumulated governance. Their current agent startup instructions require multiple large canonical files before task classification. Noema does not need to remove that knowledge; it needs to make it selectively loadable.

### 4. State projections are useful but can drift

Both reference projects contain current-state/checkpoint documents that lag behind stronger Git/repository evidence. The correct initial response is not a central state service. During migration:

- startup state must be loaded only when relevant;
- state projections remain subordinate to frozen canon/ADRs and material repository evidence;
- meaningful gate transitions should update the project's state projection;
- stale state should be treated as a project-quality/context issue, not silently promoted by Noema.

A new Noema runtime/state subsystem is **not justified** by the current evidence.

### 5. `Conformance != Quality` is essential

Agency demonstrates human creative and market-validation gates. Skill Foundry demonstrates capability/eval gates. A Noema structural pass cannot replace either.

### 6. Executor assignments are volatile

Both projects encode some current executor names in operational instructions while their deeper architecture is capability-first. Selective migration should preserve roles/capabilities and move volatile executor selection toward stack/routing declarations where useful.

## Cross-project findings

| Finding | Skill Foundry | Agency | Noema response |
|---|---|---|---|
| stale state/checkpoint projection | yes | yes | migration/context discipline; no new runtime |
| heavy mandatory startup context | yes | yes | progressive context + context modes |
| domain-specific ontology/process | yes | yes | preserve domain authority |
| executor-specific prose | yes | yes | separate stable capability from volatile executor assignment |
| existing eval/human gates | strong | strong | claims reference them; do not replace |
| migration requires rewrite | no | no | overlay/selective migration only |

## Noema changes required before migration

**None.**

The dogfood produced clarifications and migration targets, not a Core defect. Adding new schemas, services, state synchronization, event machinery, or automation at this point would exceed the evidence.

## Migration sequence approved by dogfood

1. Skill Foundry:
   - reconcile stale checkpoint;
   - add `noema.project.yaml`;
   - shorten/reframe `AGENTS.md` as entry map;
   - preserve Foundry canon/lifecycle/taxonomy/ontology/registry;
   - add Noema conformance adapter/pinning;
   - archive or de-prioritize installation-era startup docs without deleting their historical evidence.

2. Agency Foundation:
   - update current-state projection;
   - add `noema.project.yaml`;
   - make startup context task/mode-driven;
   - map common governance to Noema only where function is demonstrably replaced;
   - preserve Brand/business/validation/Project Harvest and Asset Factory domain rules;
   - move volatile executor assignment out of durable governance where practical.

3. Re-run reference audits after migration and compare cold-start/context burden.

## RC1 implications

RC1 should be considered only after both selective migrations demonstrate:

- materially lower cold-start context;
- no authority loss;
- no taxonomy/ontology duplication;
- no increase in human maintenance;
- no repeated Noema exceptions;
- existing domain eval/human gates remain intact.

**Decision:** proceed to selective migration. Architecture reopen is not justified.
