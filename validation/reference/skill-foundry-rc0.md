# Noema RC0 Reference Audit — Skill Foundry

**Mode:** read-only audit  
**Target repository:** `Picazo333/skill-foundry`  
**Observed main evidence:** merge `42fe23e5645facb1e132bbc2f9addfde49393e2e` and current canonical files  
**Noema protocol:** `0.1.0-rc.0`  
**Migration performed:** no

## Executive verdict

Skill Foundry can be represented by Noema RC0 without architectural hacks, without transferring ownership of its taxonomy/ontology, and without introducing a runtime dependency on Noema.

**Noema architecture defect:** none observed.  
**Profile gap:** none observed.  
**Selective migration recommended:** yes, after the audit phase.

## Proposed Noema composition

```yaml
project:
  type: library

traits:
  - agentic
  - reusable
  - research-heavy
  - human-gated

quality_claims:
  - contract-conformance
  - capability-trigger-accuracy
  - portability
  - context-efficiency
  - provenance
```

This composition is descriptive only; Skill Foundry remains authoritative for its own lifecycle, taxonomy, ontology, registry, capability packages, and Skill-specific evals.

## Authority mapping

### Skill Foundry owns
- reusable Skill/capability implementations;
- Foundry lifecycle and operating model;
- Skill taxonomy and ontology;
- Skill Registry;
- Skill-specific contracts, evals, handoffs, and publishing process;
- the canonical `SKILL.md` + thin-adapter packaging model.

### Skill Foundry does not need to own
- Noema protocol/conformance rules;
- global executor/stack availability;
- Agency delivery canon;
- secrets;
- unrelated project operational state.

## Strong alignment with Noema

1. **Capability before Skill/executor.** Foundry explicitly distinguishes Capability from Skill and uses `REUSE -> EXTEND -> MODE -> DEPENDENT_SKILL -> NEW_SKILL -> NO_SKILL`.
2. **Human authority.** G6 is a mandatory human architecture gate.
3. **Portability.** `SKILL.md` is canonical core with thin platform adapters.
4. **Progressive context already exists conceptually.** The operating model tells agents not to load the whole suite by default.
5. **Artifact-first continuity.** Candidates, specs, handoffs, checkpoints, registry, taxonomy, ontology, and evals are persisted in the repository.
6. **Independent audit.** G9 separates build from audit.
7. **Conditional research.** Research is executed only when it can materially improve the architecture/methodology.

These are domain-level implementations of principles Noema should preserve, not replace.

## Findings

### SF-01 — Current checkpoint is stale

**Classification:** `PROJECT_DEBT`  
**Severity:** P1 for context reliability; not an architectural blocker.

`foundry/state/CHECKPOINT.md` still states that Antigravity must be merged and Cursor reconciliation remains pending. Git history shows Antigravity was merged and the reconciled Cursor V5 foundation was subsequently merged to `main` on 2026-09-13.

**Implication:** a human/agent that trusts the checkpoint over Git evidence receives stale operational state.

**Recommended migration:** either update the checkpoint as part of meaningful state transitions or make it explicitly reconstructible/validated against repository evidence. Do not treat it as universally required startup context unless freshness is established.

---

### SF-02 — Static cold-start context is heavier than necessary

**Classification:** `PROJECT_DEBT / CONTEXT_OPTIMIZATION`  
**Severity:** P1 for agent efficiency.

Current `AGENTS.md` instructs an agent to read before Foundry work:

1. `FOUNDRY_CANON.md` (~9.9 KB)
2. `FOUNDRY_OPERATING_MODEL.md` (~8.0 KB)
3. `COLLABORATION_PROTOCOL.md` (~2.2 KB)
4. task/handoff
5. candidate + registry/taxonomy/ontology
6. relevant baseline pieces

The first three documents alone are roughly 20 KB+ before task-specific context.

**Implication:** the architecture is correct, but the startup policy loads architectural depth before task classification.

**Recommended migration:** make `AGENTS.md + noema.project.yaml + current task` the default entry. Load:
- `FOUNDRY_CANON.md` for architecture/reopen/constitutional work;
- `FOUNDRY_OPERATING_MODEL.md` for lifecycle execution/audit;
- `COLLABORATION_PROTOCOL.md` only when multi-agent role/branch coordination is relevant;
- registry/taxonomy/ontology only when capability classification/overlap requires them.

This preserves all canon while reducing repeated token cost.

---

### SF-03 — Installation-era start documents now create runtime noise

**Classification:** `PROJECT_DEBT`  
**Severity:** P2.

The repository root still contains multiple installation/bootstrap documents such as:
- `00_START_HERE.md`;
- `EXECUTE_THIS.md`;
- `README_START_HERE.md`.

They were useful to bootstrap the original dual-clone Cursor/Antigravity installation but are no longer the normal operating path of an established repository.

**Recommended migration:** preserve them as historical/setup evidence, but remove them from normal agent runtime discovery or consolidate/archive them. Do not delete before preserving their historical purpose.

---

### SF-04 — Executor-specific collaboration rules should remain assignment-level

**Classification:** `EXPECTED_DOMAIN_DIFFERENCE / PORTABILITY_OPTIMIZATION`  
**Severity:** P2.

`COLLABORATION_PROTOCOL.md` correctly states that Cursor/Antigravity roles are assignments inside G0-G10, not the architecture itself. Some root instructions still encode current executor/branch names.

**Recommended migration:** preserve role semantics, but express executor-specific assignments as current project execution configuration/extension rather than universal Foundry architecture where practical.

No change to the G0-G10 process is required.

## Explicit non-findings

### Taxonomy and ontology are not a Noema problem

`foundry/taxonomy/TAXONOMY.yaml` and `foundry/ontology/ONTOLOGY.yaml` are coherent domain-owned structures and should remain authoritative in Skill Foundry.

**Do not migrate them into Noema.**

### Skill Registry is not duplicated

Noema should reference published capability identifiers/locations through `CapabilityRef`; the actual registry remains in Skill Foundry.

### No runtime dependency is needed

Skill Foundry can continue operating when Noema tooling is unavailable. Noema conformance can also operate without loading the entire Skill catalog.

## Candidate relations

```yaml
relations:
  - type: conforms-to
    target: project:noema
  - type: publishes-capabilities-to
    target: ecosystem
  - type: consumed-by
    target: project:agency-foundation
```

These relationships do not transfer authority.

## Dogfood impact on Noema

| Category | Result |
|---|---|
| `NOEMA_DEFECT` | none |
| `PROFILE_GAP` | none |
| `PROJECT_DEBT` | stale checkpoint; startup context; historical bootstrap docs |
| `EXPECTED_DOMAIN_DIFFERENCE` | taxonomy/ontology/lifecycle remain Foundry-owned |
| Repeated exception required | no |
| Architecture reopen required | no |

## RC0 hypothesis check

- `type + traits + claims` describes Skill Foundry without hacks: **PASS**.
- Domain ontology remains independent: **PASS**.
- No dual capability authority required: **PASS**.
- Progressive context can reduce cold-start without deleting canon: **PASS**.
- Noema can audit without modifying the target repo: **PASS**.

## Recommended next action

Proceed to the read-only Agency Foundation reference audit before modifying Skill Foundry. After both reference audits are complete, apply only the migrations that reduce duplicated governance/context or add machine-readable Noema declarations without weakening Foundry's existing lifecycle and eval discipline.
