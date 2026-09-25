# Noema vNext consumer rollout — observed handoff

This is a derived coordination report, not an authority source. Each project
manifest, domain checkpoint, WorkOrder, and human gate remains with its owner.
No PR or `NOEMA PASS` below certifies domain quality or a completed migration.

| Order | Observed baseline | Result on 2026-09-24 | Next boundary |
| --- | --- | --- | --- |
| N0 Noema | remote `main` `1c3b6fc` | [PR #12](https://github.com/Picazo333/noema/pull/12) updates the derived index and adjudicates visual binding as `LOCAL_GUARD`; local lint/audit/Ruff PASS | Independent EG audit is separate; no consumer EG pin. |
| C01 Skill Foundry | `203e1c4` | [PR #23](https://github.com/Picazo333/skill-foundry/pull/23) repairs the scoped state reference; Foundry and Noema CI PASS | Process Auditor remains advisory until Foundry accepts an intake. |
| C02 StackIA | `main` `91bd6eb`; V2.1 branch `44cfb16` | [PR #32](https://github.com/Picazo333/stack-ia/pull/32) targets the active V2.1 branch, repairs context refs, and records a partial pilot handoff; local G9 check-only and Noema checks PASS | Decision 0026 supersedes old R7 QA-only assumptions; G10 domain review remains. |
| C03 Agency Foundation | `4cfb2df` | [PR #56](https://github.com/Picazo333/agency-foundation/pull/56) adds the local request-binding guard and six synthetic negative/positive checks; repo health and Noema checks PASS | `PARTIAL`: use the guard on the next authorized generation; P6 human review and effective-conditioning QA remain with Brand. |
| C04 Control Tower | `c83b1cc` | [PR #8](https://github.com/Picazo333/4geeks-control-tower/pull/8) repairs the scoped state reference; Noema CI PASS | Next real case triggers workflow bridge. Existing domain validation fails for the closed Tailwind case's missing `delivery/SUBMISSION.md`; this order does not alter it. |
| C05 Nexova | delivery branch `138ff88` | [PR #2](https://github.com/Picazo333/nexova-ai-engineering/pull/2) targets the real delivery branch, repairs an observed RC0 catalog mismatch and adds WorkOrder/Handoff; lint/audit PASS | `PARTIAL`: resolve delivery [PR #1](https://github.com/Picazo333/nexova-ai-engineering/pull/1) and its academic gate, then pin the accepted HEAD. |
| C06 Personal Context | `0d1a740` | Existing RC0 manifest, seven WorkOrders, handoff and privacy eval retained; domain validator and Noema lint/audit PASS; no private layer loaded or mutated | `MIGRATED` for the existing RC0 corpus, supported by its domain-owned release QA; future deltas remain task-scoped. |
| C07 FEBRIS | beta branch `b9f4f48` | [PR #6](https://github.com/Picazo333/FEBRIS/pull/6) adds bounded RC0 metadata on the active beta branch; 20 domain tests, web build and Noema checks PASS | `PARTIAL`: v2 [PR #1](https://github.com/Picazo333/FEBRIS/pull/1) still requires human beta acceptance and an accepted release HEAD. |
| C08 MD Dental | remote `main` `abaadc0` | [PR #98](https://github.com/Picazo333/MD_APP-AFTER_GROK/pull/98) adds WIP-aware RC0 metadata outside product paths; Noema lint/audit PASS | `PARTIAL`: reconcile physical VR-03B worktree and run product verify on its effective HEAD; the clean clone is not WIP evidence. |
| C09 Eidema | `f07946b` | [PR #2](https://github.com/Picazo333/Eidema/pull/2) adds bounded RC0 metadata; Noema lint/audit PASS | Corpus/specimen choice and visual approval remain domain gates. |
| C10 Plastic Surgeon Demo | `9753f90` | Existing RC0 consumer verified locally: static gate, Noema lint and audit PASS; no product change | EG synthetic fixtures only after independent EG audit and an eligible pin. |

At the initial 2026-09-24 review, all eleven integration PRs were drafts and
unmerged. The StackIA, Nexova,
FEBRIS, MD Dental and Eidema
handoffs are explicitly partial. Control Tower's domain validator failure is
pre-existing and distinct from its Noema conformance. The Noema pytest suite
reached 100% case progress on this Windows host but did not exit after
teardown; it was interrupted, so no full-suite PASS is claimed. Rollback of
any integration uses a targeted revert after comparing intervening domain
work, never a hard reset of consumer WIP.

No order remains `DEFERRED` in the current rollout accounting. This means each
consumer has either its existing RC0 integration verified or a bounded integration
PR; it does not close human or domain gates. In particular, `PARTIAL` does not
mean `MIGRATED`, and the four new PRs must be rechecked after their base branches
move. EG remains unpropagated pending its independent audit and eligible pin.

## RC0 technical integration — 2026-09-25

The shared consumer workflow at Noema commit `5aa4289178b92f299887aaa1f73d12e97478b1a8`
checks out immutable RC0 core `1c3b6fc551aeb4f3cdcd66cb4575c39d850bbc44`
and runs both `noema lint` and `noema audit`. Every consumer now has a pinned
CI gate. C06 keeps its own corpus validator and runs the same full Noema audit.

| Consumer | PR head | Noema CI run |
| --- | --- | --- |
| C01 Foundry | `05c7c16` | `36077631788` PASS |
| C02 StackIA | `b68a32b` | `36077632591` PASS |
| C03 Agency | `68af3e6` | `36077633804` PASS |
| C04 Control Tower | `6aea220` | `36077631632` PASS |
| C05 Nexova | `fd4ab78` | `36077633883` PASS |
| C06 Personal Context | [PR #1](https://github.com/Picazo333/miguel-personal-context/pull/1) `f17813a` | `36077653404` PASS |
| C07 FEBRIS | `e419c05` | `36077631563` PASS |
| C08 MD Dental | `8b4172f` | `36077630507` PASS |
| C09 Eidema | `e62391b` | `36077632927` PASS |
| C10 Plastic Surgeon Demo | [PR #1](https://github.com/Picazo333/noema-plastic-surgeon-demo/pull/1) `7c56769` | `36077659565` PASS |

The active Noema WorkOrders and Handoffs are linked from consumer entrypoints
where needed and schema-validated. This verifies RC0 technical wiring on the
proposed PR heads. `PARTIAL` handoffs refer to domain flows or human gates that
remain unobserved, not missing RC0 wiring. Control Tower domain validation
failed on the pre-existing closed Tailwind case; Noema CI on that head
passed. N0 CI on the shared-workflow update passed (`36075945224`). Noema
conformance does not promote a domain decision. EG remains outside RC0
consumers pending independent audit and an eligible pin.

## Merge audit — 2026-09-25

The user explicitly authorized auditing and merging the required integration.
All eleven PR heads were compared with their stated bases and had no merge
conflict. N0 and C01–C03, C05–C10 passed their Noema CI before merge. N0 was
merged with a merge commit (`4a4a132`), preserving the pinned reusable-workflow
commit `5aa4289` in `main` history. The other successful integration merges
were C01 `94592d9`, C02 `92adec2`, C03 `a2c324a`, C05 `5737168`, C06
`22bc546`, C07 `5068e88`, C08 `38e6215`, C09 `3c0051b`, and C10 `5842298`.
C02, C05, and C07 landed on their respective product branches, not on `main`;
those product branches still have their own domain acceptance gates.

C04 initially remained open because the closed Tailwind assignment lacked
`delivery/SUBMISSION.md` and `CASE.md` still said `PLANNED`. Its factual
repair [PR #9](https://github.com/Picazo333/4geeks-control-tower/pull/9)
uses existing `assignment.yaml` and registry claims and explicitly notes that
no platform receipt is archived. Automatic approval review initially rejected
merging that domain-record repair as outside the explicit Noema scope. After
the user clarified that Control Tower was indispensable to the integration,
PR #9 merged to `main` as `abc619a`. Noema [PR #8](https://github.com/Picazo333/4geeks-control-tower/pull/8)
then incorporated that base and passed Control Tower Validation (`36080608006`)
and Noema Conformance (`36080608767`) on head `99c9794`. It merged to `main`
as `789c93d`. This completes C04's RC0 structural integration; the next real
case and its academic gate remain domain-owned.
