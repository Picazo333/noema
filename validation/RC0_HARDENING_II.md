# Noema RC0 — Hardening II

**Trigger:** exhaustive harvest of the first external greenfield consumer.  
**Scope:** measurement, reproducibility, scaffolding, Harvest ergonomics, and documentation closure.  
**Architecture:** unchanged.

## Accepted changes

### A — Context correctness
- Cold-start accounting now includes `AGENTS.md`, `noema.project.yaml`, and required context for the selected mode.
- Optional context refs are validated for integrity but excluded from default cold-start loading.
- `audit --section context` reports every declared mode, not just the default.
- Context comparisons use **Noema Context Units v1** (`characters / 4`) as a provider-neutral heuristic.

### B — Scaffold single source
- `noema init` now consumes the canonical project templates instead of maintaining a second hardcoded scaffold.
- The manifest template explicitly declares its default `build` mode, keeping it conformant with the hardened validator.

### C — Reproducible conformance
- CI receives read-only contents permission, a five-minute timeout, an explicit Ubuntu runner, pip cache, and a pinned constraints set.
- The reusable consumer workflow receives the same bounded execution posture; its immutable validator pin is advanced separately after merge.

### D — Minimal Harvest hardening
- Harvest IDs include microseconds plus a short UUID suffix to avoid collisions under parallel agent creation.
- `harvest new` accepts repeatable `--evidence` refs.
- Missing `repo://` evidence fails at candidate creation rather than producing a weak candidate.

### E — Reference consumer closure
- The plastic-surgeon demo remains a reference consumer, not a design project.
- Its canonical delivery path is the custom GitHub Pages workflow; the root redirect is retained only as a defensive fallback for prior branch-based Pages behavior.
- Remote conformance, static validation, and live deployment are recorded as evidence.

### F — Documentation closure
- README, changelog, ecosystem index, and reference-consumer evidence are refreshed.
- Skill Foundry becomes the next complex migration target; Agency Foundation remains deferred until its active work reaches a stable checkpoint.

## Explicitly deferred

No database, daemon, event bus, RAG layer, knowledge graph, central runtime, automatic cross-repo synchronization, trait policy engine, full Harvest workflow manager, or quality-evidence aggregator was added.

The following remain evidence-seeking work for Skill Foundry: WorkOrder lifecycle, handoff execution, eval evidence aggregation, multi-agent recovery, executor routing in real work, cross-project writer collisions, and external storage behavior.

## Decision

RC0 architecture remains closed. This hardening makes the next before/after Skill Foundry migration measurable without expanding Noema into an execution platform.
