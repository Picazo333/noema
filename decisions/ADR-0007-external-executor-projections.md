# ADR-0007 — External executor projections require explicit promotion

**Status:** ACCEPTED

## Context

StackIA is an independent Noema-governed domain project that tracks AI tools, integrations, verification evidence, capacity state, and candidate executor qualification.

StackIA needs to publish stable executor candidates to Noema without becoming the authority that changes RC0 routing.

## Decision

External executor projections are **candidate inputs**, not live routing registries.

For StackIA:

- source projection: `github://Picazo333/stack-ia/exports/noema/executors.yaml`;
- Noema effective registry: `registry/executors.yaml`;
- promotion: explicit human/reviewed copy after verification and contract validation;
- runtime routing continues to read only the Noema-local registry plus runtime availability.

No automatic cross-repository import is added to RC0.

## Consequences

- StackIA keeps complete authority over its domain state and qualification evidence.
- Noema keeps complete authority over routing descriptors and policy.
- An empty StackIA projection is valid.
- Unverified StackIA candidates cannot enter routing by side effect.
- RC0 code and frozen deterministic routing remain unchanged.
- Automatic ingestion, if ever justified, requires a separate reopen/activation decision.
