# 4Geeks Control Tower — Noema Consumer Record

Status: **BOUNDARY ACCEPTED / CONSUMER DECLARED**

Date: 2026-09-20

## Consumer
`project:4geeks-control-tower`

## Source
Control Tower adopted `noema.project.yaml` against Noema `0.1.0-rc.0` after its Artist Showcase postmortem.

## Authority boundary
Control Tower retains authority over:
- 4Geeks assignment governance;
- rubric/evidence contracts;
- academic and learning lifecycle;
- NotebookLM handoffs;
- study/defense presentation protocol;
- assignment-local harvest state.

Noema retains authority over:
- protocol/conformance;
- context routing model;
- inter-project relations;
- coordination/provenance/recovery semantics.

Noema does **not** own assignment runtime, 4Geeks rubric semantics, Skill Foundry taxonomy/ontology, or study-presentation content.

## Cross-project findings accepted as Noema-relevant
1. **Canonical truth drift:** a project's control-plane documents can lag behind a downstream source of truth; this is a recoverability/governance concern, not a reason for Noema to own the domain state.
2. **Context/authority isolation:** cross-project agents must have explicit project/authority boundaries before writes or reuse.
3. **Evidence before canon:** a downstream case may produce candidates, but domain/protocol authority decides whether they become canon.

## Not promoted into Noema
- Mac Miller/Artist Showcase-specific facts;
- 4Geeks-specific rubric fields;
- Liturgia Onírica presentation semantics;
- Skill definitions or skill-registry state.

## Relation
Noema records `audits -> project:4geeks-control-tower`.

## Conformance note
The consumer manifest intentionally follows the existing RC0 project-manifest pattern already used by Skill Foundry: explicit authority, sources of truth, progressive context modes, quality claims and declared relations. Full domain quality remains Control Tower's responsibility; `NOEMA PASS` must never be interpreted as academic/rubric PASS.
