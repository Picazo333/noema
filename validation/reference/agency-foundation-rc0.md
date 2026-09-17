# Noema RC0 Reference Audit — Agency Foundation

**Mode:** read-only audit  
**Target repository:** `Picazo333/agency-foundation`  
**Observed recent main evidence:** through `bb4ec892ee02b2c8c22dafcca036d996d83634de` on 2026-09-17  
**Noema protocol:** `0.1.0-rc.0`  
**Migration performed:** no

## Executive verdict

Agency Foundation can be represented by Noema RC0 without forcing a software-centric model and without replacing its Brand, business, research, validation, capability-governance, or Project Harvest methods.

The repository is an especially strong reference implementation because it mixes creative judgment, deterministic repository governance, research, agent collaboration, business delivery, media/assets, and human gates.

**Noema architecture defect:** none observed.  
**Profile gap:** none observed.  
**Selective migration recommended:** yes, after both reference audits.

## Proposed Noema composition

```yaml
project:
  type: delivery-system

traits:
  - creative
  - agentic
  - research-heavy
  - customer-facing
  - human-gated
  - reusable

quality_claims:
  - contract-conformance
  - delivery-integrity
  - research-groundedness
  - visual-coherence
  - provenance
  - context-efficiency
  - security-boundaries
```

The exact claims can be reduced during migration. This audit demonstrates that the composition model expresses the project without inventing an Agency-specific project species.

## Authority mapping

### Agency Foundation owns
- Agency business/strategy canon and evidence boundaries;
- Brand process, workbench/canon separation, visual gates, and approved identity artifacts;
- Agency delivery/workstream definitions;
- field-validation instruments and resulting project evidence;
- Agency-specific capability intake decisions;
- Asset Factory architecture and Agency-local asset lifecycle until later ecosystem migration;
- Agency Project Harvest records and downstream project-specific uses.

### Agency Foundation does not need to own
- Noema protocol/conformance;
- Skill Foundry taxonomy/ontology and canonical reusable Skill packages;
- global executor availability/quotas;
- secrets;
- future Drive blob-storage policy outside its local project contract.

## Strong alignment with Noema

1. **Repo-first authority.** `main` is reviewed project truth while status metadata differentiates FROZEN/APPROVED/REVIEW/DRAFT/RESEARCH artifacts.
2. **Research != decision.** Research cannot silently become strategic truth.
3. **Capability before executor.** The operating model explicitly says workstreams are capability-first and executors may change without changing the contract.
4. **External instructions are subordinate.** Capability governance prevents Skills/tools from expanding authority or task scope.
5. **Evidence before claims.** The validation system distinguishes instruments/plans from actual buyer evidence.
6. **Human creative authority.** Brand phases use explicit human gates and generated assets do not approve themselves.
7. **Harvest is already a low-friction sidecar.** Project Harvest captures meaningful reusable learning without blocking routine development or auto-promoting canon.
8. **Repository health already exists.** The project has a GitHub `repo-health.yml` workflow and local validation discipline.

These should be preserved during migration.

## Findings

### AF-01 — `PROJECT_STATE.md` has drifted behind main

**Classification:** `PROJECT_DEBT`  
**Severity:** P1 for context reliability.

`PROJECT_STATE.md` (updated 2026-09-16) declares Phase 3 Reference Atlas as the current Brand gate. Subsequent `main` history records Phase 3 closure, Phase 4 Tension Grammar/red-team work, and a Phase 5 iteration contract dated 2026-09-17.

The Phase 5 contract itself correctly remains subordinate to its Phase 4 human gate, so this finding does **not** claim that Phase 5 has been approved. It demonstrates only that the root current-state projection no longer describes the latest program position.

**Implication:** a new agent following `AGENTS.md` literally can begin from stale state before it sees stronger repository evidence.

**Recommended migration:** reduce `PROJECT_STATE.md` to a compact, explicitly freshness-sensitive projection or ensure meaningful gate transitions update it. Do not make a stale state projection more authoritative than frozen plans/ADRs/Git evidence.

---

### AF-02 — Default agent bootstrap is substantially heavier than task needs

**Classification:** `PROJECT_DEBT / CONTEXT_OPTIMIZATION`  
**Severity:** P1.

Current `AGENTS.md` requires, before work:

1. `PROJECT_STATE.md` (~5.7 KB)
2. `docs/00-meta/source-of-truth.md` (~0.8 KB)
3. `docs/00-meta/operating-model.md` (~1.6 KB)
4. `docs/00-meta/capability-governance.md` (~9.3 KB)
5. active workstream spec
6. relevant ADRs
7. Skill Registry when applicable

The fixed first four already exceed ~17 KB, before the active workstream, task, ADRs, Brand contracts, or capability material. The current DIVINIVID master plan is itself a deep execution contract rather than lightweight startup context.

**Recommended migration:** default startup should become `AGENTS.md + noema.project.yaml + current task/workstream pointer`. Then resolve deeper material by context mode:

- ordinary patch/build: scoped files + local invariant refs;
- Brand/creative execution: relevant Brand contract + current phase + only required capability adapters;
- architecture/governance: source-of-truth + operating model + relevant ADRs;
- capability intake: capability-governance + registry;
- recovery/audit: state/evidence/history slices.

This preserves every document while removing repeated mandatory reads.

---

### AF-03 — Universal governance and Agency-specific governance are currently co-located

**Classification:** `MIGRATION_OPPORTUNITY`  
**Severity:** P2.

`source-of-truth.md`, `agent-contracts.md`, `handoff-protocol.md`, `definitions-of-done.md`, `capability-governance.md`, and related meta documents contain both:

- genuinely universal repo/agent principles; and
- Agency-specific execution rules.

**Recommended migration:** do not delete or flatten these files. Map universal properties to pinned Noema contracts and keep only the Agency-specific deltas/constraints locally where that reduces duplication. Migration must prove that the Noema reference replaces a function before retiring local text.

---

### AF-04 — Executor assignment is more specific than the operating architecture

**Classification:** `PORTABILITY_OPTIMIZATION`  
**Severity:** P2.

The operating model correctly defines workstreams capability-first, but `AGENTS.md` still contains a concrete ownership summary assigning areas to ChatGPT, Claude/CoWork, Gemini, Codex, Antigravity, and Jules.

**Recommended migration:** keep stable workstream/capability ownership in the project. Move volatile executor assignments toward Noema stack/routing or an Agency extension/current execution configuration. Executor replacement should not require rewriting governance prose.

---

### AF-05 — Project relationships are understandable to humans but not yet expressed through the ecosystem contract

**Classification:** `EXPECTED_MIGRATION_GAP`  
**Severity:** P2.

The repo contains dependency maps and rich cross-system documentation, but no Noema Project Manifest currently declares relations to Noema, Skill Foundry, future Eidema/Media flows, or other ecosystem systems.

**Recommended migration:** add one small `noema.project.yaml`; do not replace the richer project dependency documentation. The manifest should expose only machine-relevant relationships and authority boundaries.

---

### AF-06 — Conformance must never replace Brand or market validation

**Classification:** `GUARDRAIL / NON-FINDING`  
**Severity:** constitutional.

Agency already demonstrates why Noema's `Conformance != Quality` rule matters:

- Brand artifacts require human `PASS / MUTATE / KILL` gates and system proof;
- field-validation instruments are not buyer evidence;
- research is not a decision;
- generated output is not canon.

A future `NOEMA PASS` must not be interpreted as Brand approval, validated product-market demand, or commercial proof.

No migration should weaken these gates.

---

### AF-07 — Asset/media architecture should not be migrated prematurely

**Classification:** `EXPECTED_DOMAIN_DIFFERENCE`  
**Severity:** none for RC0.

Agency already has `assets/` and an Asset Factory architecture. Future ecosystem plans include Drive/Eidema/Media Factory separation, but that phase intentionally follows Noema + Skill Foundry + Agency foundations.

**Recommendation:** leave current asset authority untouched during initial Noema migration. Later storage migration should be manifest/provenance-driven and transactional rather than a bulk folder move.

## Candidate relations

```yaml
relations:
  - type: conforms-to
    target: project:noema
  - type: consumes-capabilities-from
    target: project:skill-foundry
  - type: may-publish-harvest-to
    target: project:skill-foundry
  - type: may-publish-harvest-to
    target: system:obsidian
```

Future Eidema/Drive/Aurema relations should be added only when those integrations are actually activated.

## Dogfood impact on Noema

| Category | Result |
|---|---|
| `NOEMA_DEFECT` | none |
| `PROFILE_GAP` | none |
| `PROJECT_DEBT` | state drift; heavy bootstrap context |
| `MIGRATION_OPPORTUNITY` | common governance can become Noema refs; executor assignments can become volatile config |
| `EXPECTED_DOMAIN_DIFFERENCE` | Brand/market gates, Asset Factory, Agency strategy remain Agency-owned |
| Repeated exception required | no |
| Architecture reopen required | no |

## Cross-reference insight with Skill Foundry

Both reference repositories exhibit the same two operational pressures:

1. current-state/checkpoint documents can drift behind Git/project evidence;
2. correct governance has accumulated into a costly mandatory startup read.

This is evidence **for**, not against, Noema's progressive-context architecture. It does not yet justify a new runtime/state service. Initial migration should first reduce mandatory context and make state projections explicitly subordinate to stronger evidence.

## RC0 hypothesis check

- `type + traits + claims` describes Agency without hacks: **PASS**.
- Creative/human evals coexist with deterministic repo checks: **PASS**.
- Noema can preserve Agency-specific governance rather than flatten it: **PASS**.
- Capability ownership remains in Skill Foundry while Agency consumes it: **PASS**.
- Executor-specific implementation can be separated from durable workstream contracts: **PASS**.
- Noema audit can identify stale projections/context load without taking project authority: **PASS**.

## Recommended next action

Close the two-reference dogfood gate. Reconcile findings at the Noema level before modifying either target repository. If no RC0 protocol defect emerges, perform a small selective migration starting with Skill Foundry: add the manifest, reduce startup context, reconcile stale checkpoint state, and wire conformance without altering its G0-G10 lifecycle, taxonomy, ontology, or Skill Registry.
