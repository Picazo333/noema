# ADR-0009 — Direct implementation while no executor is verified

**Status:** ACCEPTED (2026-09-28) · Program: OLV1 (`github://Picazo333/skill-foundry/foundry/plans/operator-layer-v1/PLAN_LOCK.md`, decision D4)

## Context

`registry/executors.yaml` lists `codex` and `claude-code`, both `needs-verification`. Deterministic routing (ADR-0006, `spec/06-routing.md`) therefore returns `BLOCKED_NO_VERIFIED_EXECUTOR` for every route, and the StackIA projection consumed under ADR-0007 is still `executors: []`. Meanwhile the operator's real work proceeds: the FAV1 program in Skill Foundry was closed by direct implementation (`foundry/plans/functional-architecture-v1/PLAN_DEVIATION_DIRECT_IMPLEMENTATION.md`), and the operator keeps both Claude Code (principal, October 2026) and Codex (secondary) as executors under his own supervision (StackIA `state/operator-lanes.yaml`).

## Decision

While no entry in `registry/executors.yaml` is `verified`, work proceeds by **direct human + Claude Code implementation outside Noema routing**. `codex` remains `needs-verification` (no deprecation, no removal). The StackIA projection remains `executors: []` (ADR-0007). `src/noema/routing.py`, `spec/06-routing.md` and ADR-0006 are unchanged: the block is the correct protocol answer, and this ADR documents the operating lane that runs *beside* it, not a fallback inside it.

## Consequences

- Noema conformance (`lint`/`audit`) continues to govern repository structure; it does not gate direct implementation.
- Independence is established by session provenance recorded in program receipts (builder ≠ reviewer), not by executor verification.
- When StackIA promotes a verified descriptor (ADR-0007 flow), routing resumes without changes to this repository's routing code; this ADR then becomes historical.
- Operator preference facts (which tool for which work) live in StackIA (`state/operator-lanes.yaml`) and never in Noema's routing registry.
