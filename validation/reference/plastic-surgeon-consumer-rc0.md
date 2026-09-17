# Reference Consumer Harvest — Plastic Surgeon Demo

**Consumer:** `Picazo333/noema-plastic-surgeon-demo`  
**Protocol:** Noema `0.1.0-rc.0`  
**Purpose:** first greenfield, customer-facing, sensitive-domain consumer after RC0 convergence.  
**Method:** 100 adversarial review passes grouped across architecture/authority, progressive context, validator robustness, quality/evidence, Harvest, CI/performance, delivery/platform boundaries, agent ergonomics, documentation drift, and future scalability.

## What the consumer validated

1. **Federated authority held.** Medical advice, credentials, patient data, legal compliance, secrets, and large media remained explicitly outside project authority while Noema governed coordination contracts.
2. **Progressive context worked as a repository design.** The project could route build, patch, audit, research, architect, and recover tasks without requiring full-repository loading.
3. **Conformance stayed distinct from quality and delivery.** Noema could pass while GitHub Pages still had an external configuration problem; this was correctly classified as a platform/delivery issue rather than a protocol-quality claim.
4. **External consumer pressure found real validator defects.** Six edge cases plus one CI policy-drift issue were fixed and regression-tested without reopening architecture.
5. **Immutable consumer pins worked.** The demo invoked a reusable Noema workflow at an immutable commit rather than silently following `main`.
6. **Sensitive-domain project rules stayed local.** No medical-domain ontology leaked into Noema core.

## First hardening findings — closed

- context entrypoint path escape;
- directory-valued entrypoint;
- undeclared default context mode;
- malformed executor item crash;
- malformed route item crash;
- null/non-list route preference crash;
- Ruff rule-family drift.

All seven are covered by validator or CI hardening and regression tests.

## Second-pass findings accepted for hardening

### Context measurement
The original context audit omitted `noema.project.yaml` from cold-start accounting even though agents must read it. Optional refs existed in schema but were not integrity-checked by the cold-start resolver. Audit also exposed only the default mode. These issues would have contaminated the planned before/after Skill Foundry measurement.

**Response:** include the manifest, validate optional refs without loading them, report every context mode, and standardize on Noema Context Units v1.

### Scaffold drift
`noema init` and `templates/project/noema.project.yaml.tpl` represented the same scaffold independently. After default-mode hardening, the template could create an invalid manifest while the CLI-created version passed.

**Response:** templates become the canonical scaffold consumed by `noema init`.

### CI reproducibility and latency
Observed Noema consumer conformance completed in about 16 seconds; roughly 10 seconds were dependency installation while `noema lint` itself completed within the one-second timestamp resolution of GitHub Actions. Noema's own hardened CI completed in about 11 seconds, again with installation dominating execution.

**Response:** optimize bootstrap only—constraints, pip cache, explicit runner, timeout, least privilege. Do not add a daemon or service to save seconds.

### Harvest ergonomics
Candidate IDs used second-resolution timestamps plus the finding slug, allowing collisions under parallel agents. Candidate creation also defaulted to empty evidence even though the protocol says evidence precedes canon.

**Response:** collision-resistant IDs and repeatable `--evidence` arguments with fail-fast validation for local repo evidence.

### Delivery/platform boundaries
GitHub Pages exposed three distinct facts: private-repo Pages depended on account capabilities; Actions could not grant itself administrative Pages enablement; and branch/dynamic deployment could compete with the intended custom Pages artifact. These are external platform constraints, not Noema core defects.

**Response:** one canonical project deployment workflow, human-gated platform configuration, explicit visibility preflight, and no GitHub-specific runtime logic in Noema.

### Documentation drift
The local pre-publication report became stale after remote deployment, and Noema's own README/changelog/ecosystem index no longer reflected the external consumer evidence.

**Response:** milestone closure refreshes or supersedes derived evidence; derived views remain non-authoritative.

## Deferred on purpose

The demo did not provide strong evidence to design or expand:

- WorkOrder execution lifecycle;
- multi-agent handoff execution;
- eval-result discovery/aggregation;
- global relation resolution;
- cross-project single-writer enforcement;
- trait-driven automatic policies;
- external Drive/media storage behavior;
- full Harvest review/routing manager;
- central state, RAG, graph, event bus, agent runtime, or synchronization service.

These are better exercised by Skill Foundry, which already owns specialized taxonomy/ontology/workflow/eval concerns.

## Remote evidence

Final consumer commit observed during closure: `96e634c586c57acc70eeeed757667b41d93c2471`.

- Noema Conformance run `35272563625`: PASS. The job ran from 20:43:52Z to 20:44:08Z; dependency install consumed roughly ten seconds while `noema lint` completed within one second.
- Custom Deploy GitHub Pages run `35272562522`: PASS. Static validation passed; artifact upload and Pages deployment completed successfully.
- A dynamic GitHub `pages build and deployment` run was also observed on the same commit, providing evidence that delivery-source configuration is an external authority boundary and should be preflighted rather than inferred.

## Migration gate produced by this harvest

Before Skill Foundry migration, record a baseline for:

- cold-start files and Noema Context Units by mode;
- mandatory docs;
- duplicated authority/instructions;
- agent entrypoints;
- recovery material;
- handoff formats;
- eval gates;
- executor-specific instructions;
- time/steps required to reconstruct project state.

After selective migration, repeat the same measurement. Noema should be retained only where it reduces ambiguity, repeated context, recovery cost, or operational risk.

## Final decision

The first implementation supports the RC0 architecture. The defects found are implementation, measurement, reproducibility, and platform-boundary lessons. Architecture remains frozen; Skill Foundry is the next appropriate complex consumer. Agency Foundation is intentionally deferred until its active development reaches a stable checkpoint.
