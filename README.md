# Noema vNext

Noema is a Git-native protocol for making heterogeneous projects easier to understand, govern, validate, hand off, and evolve across humans and AI executors.

It is **not** a megapp, universal database, agent runtime, knowledge graph, or replacement for domain systems. Domain systems keep their own authority; Noema standardizes coordination contracts around them.

## RC0 goals

- describe a project through a small manifest;
- guide agents through progressive context rather than full-history loading;
- express project type, traits, quality claims, relations, and authorities;
- validate structural conformance without pretending conformance equals project quality;
- describe executors and deterministic routing without provider lock-in;
- preserve artifacts, storage references, provenance, handoffs, decisions, and harvest candidates;
- keep future capabilities explicit but out of runtime until activation criteria are met.

## Install

```bash
python -m pip install -e ".[dev]"
```

## Commands

```bash
noema init --id my-project --name "My Project" --profile minimal
noema lint .
noema audit .
noema audit . --section context
noema audit . --section routing
noema harvest new . --finding "Reusable lesson" --evidence repo://evidence.md
noema harvest validate path/to/harvest.yaml
```

## Context measurement

`noema audit . --section context` reports every declared mode and its cold-start footprint. The metric is **Noema Context Units v1** (`characters / 4`): a provider-neutral comparison heuristic, not billing-token accounting.

## Read order

1. `PROTOCOL.md` — runtime invariants.
2. `noema.project.yaml` — what this project is and owns.
3. `spec/` — deeper architecture only when the task requires it.
4. `decisions/` — frozen architecture decisions.

## Status

`v0.1.0-rc.0` remains architecturally frozen. RC0 has completed self-dogfood, audits of Skill Foundry and Agency Foundation, validator hardening from a greenfield external consumer, and a second hardening pass focused on context measurement, reproducibility, scaffolding, and Harvest ergonomics.

The next complex consumer is **Skill Foundry**, where Noema will test WorkOrders, handoffs, eval evidence, recovery, and multi-agent coordination. Agency Foundation remains intentionally unmigrated until its active work reaches a stable checkpoint.
