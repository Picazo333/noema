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
noema harvest new . --finding "Reusable lesson"
noema harvest validate path/to/harvest.yaml
```

## Read order

1. `PROTOCOL.md` — runtime invariants.
2. `noema.project.yaml` — what this project is and owns.
3. `spec/` — deeper architecture only when the task requires it.
4. `decisions/` — frozen architecture decisions.

## Status

`v0.1.0-rc.0` candidate implementation. RC0 is intended to be dogfooded against Skill Foundry and Agency Foundation before an RC1 freeze.
