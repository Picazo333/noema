# RC0 consumer incorporation audit — 2026-09-25

This is a derived snapshot of the ten consumer target refs, not domain approval.
Each ref was fetched after the integration merges and checked out cleanly. All
ten target trees declare Noema `0.1.0-rc.0`; `python -m noema lint .` and
`python -m noema audit .` passed on each exact target SHA. Each uses a pinned
Noema CI gate: nine call reusable workflow `5aa4289`, while Personal Context
checks out immutable RC0 core `1c3b6fc` in its corpus workflow. The recurring
unverified-executor warning is expected; no qualified executor or EG adoption
is claimed.

| Consumer | Verified target SHA | Additional check on target | Boundary still open |
| --- | --- | --- | --- |
| C01 Skill Foundry | `main` `94592d9` | Foundry validator; 10 unit tests PASS; WorkOrder/Handoff schema PASS | Process Auditor intake remains advisory. |
| C02 StackIA | V2.1 branch `92adec2` | Human UI V2.1 G9 check-only PASS; WorkOrder/Handoff schema PASS | Parent PR #31 and G10 operator review. No G10 approval inferred. |
| C03 Agency Foundation | `main` `a2c324a` | Repo health and six guard tests PASS | Guard is a standalone preflight candidate. No observed image-tool call, effective conditioning QA or P6 human approval. |
| C04 Control Tower | `main` `789c93d` | Domain validator PASS (two assignments); WorkOrder/Handoff schema PASS | Next material case must exercise the workflow bridge and its academic gate. |
| C05 Nexova | delivery branch `5737168` | WorkOrder/Handoff schema PASS | Parent PR #1 and academic review; product code was unchanged by this integration. |
| C06 Personal Context | `main` `22bc546` | Corpus validator: zero errors, zero warnings | Private data and health remain default deny; future tasks still require scoped orders. |
| C07 FEBRIS | beta branch `5068e88` | 20 domain tests and web build PASS; WorkOrder/Handoff schema PASS | Parent PR #1 and human beta acceptance; parent PR currently conflicts with `main`. |
| C08 MD Dental | `main` `38e6215` | WorkOrder/Handoff schema PASS | Physical VR-03B WIP and product verification were outside this clean metadata checkout. |
| C09 Eidema | `main` `3c0051b` | WorkOrder/Handoff schema PASS | Visual review and corpus/specimen decision remain with Eidema. |
| C10 Plastic Surgeon Demo | `main` `5842298` | Static quality gate PASS | EG fixtures await independent EG audit and eligible pin. |

The C01, C02, C04, C05, C07, C08 and C09 WorkOrders and Handoffs also passed
the RC0 JSON schemas, project-ID match and WorkOrder reference check. Noema
lint/audit do not issue any listed human gate. Product suites requiring absent
dependencies (Nexova, MD Dental, Eidema) were not rerun for these metadata-only
changes; this audit does not certify those product builds.

## Follow-up findings

1. C03's guard accepts a request record but is not wired to an observed
   generation adapter. It must capture actual call evidence and undergo Brand
   QA before it can prove available, attached and effectively conditioned.
2. C02, C05 and C07 exist on product branches, not `main`. Their parent PRs
   remain open, and C07 currently has a merge conflict against `main`.
3. Some coordination handoffs predate the merges. C04 still lists the Tailwind
   validator failure as remaining although PR #9 repaired it; C09 still says
   "proposed" and "if merged". Their domain owners should refresh those
   snapshots on a scoped follow-up. The underlying RC0 checks pass.
4. StackIA's declared `build` context resolves about 164,343 Noema Context
   Units. Its `patch` mode is bounded, but the `build` read set deserves a
   separate context-efficiency review before claiming that quality property.
5. The ecosystem index previously listed four of the ten consumers. This
   audit updates that derived projection to list all ten without changing
   domain authority or executor routing.

Therefore all ten consumers have RC0 structural wiring on their intended
target refs, while C02, C03, C05, C07, C08 and C09 retain the stated real-flow
or domain-evidence boundaries. No `MIGRATED` conclusion follows solely from a
green conformance result.
