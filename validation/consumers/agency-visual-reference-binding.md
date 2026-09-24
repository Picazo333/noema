# Visual reference binding — consumer adjudication

**Decision (2026-09-24): LOCAL_GUARD.** This is a bounded adjudication of
`harvest/harvest-20260922-active-multimodal-reference-binding.yaml`, which
remains a candidate. It does not change RC0, ADR-0008, WorkOrder, or the two
experimental Execution Governance artifact types.

## Evidence and boundary

The [DIVINIVID incident](https://github.com/Picazo333/agency-foundation/blob/main/docs/03-brand/workbench/divinivid/generation/POSTMORTEM_2026-09-22_ACTIVE_VISUAL_CONDITIONING_FAILURE.md)
recovered approved references but could not establish that their pixels were
attached to each image-generation request. A separate executor substitution
produced quarantined output. The [domain harvest](https://github.com/Picazo333/agency-foundation/blob/main/docs/10-knowledge-harvest/records/HARVEST-20260922-divinivid-active-reference-binding.md)
distinguishes reference availability, request binding, and effective visual
fidelity. Those are three different predicates.

Noema's existing WorkOrder can identify inputs, allowed writes, forbidden
effects, and human gates. The experimental trace r3 can report a tool
occurrence and reference evidence. Neither proves that a particular image was
attached to the request, nor that the generated result passed Brand QA. A
trace reference alone must not be promoted into either claim.

## Consumer guard

For each authorized visual-generation occurrence, DIVINIVID's adapter should
record the approved positive reference identity and authority role, the
executor's image-conditioning capability, the references actually attached to
the request, and exclusion of quarantined descendants. The Brand QA record
then separately decides whether the output is effective and eligible for human
review. Missing or incompatible binding stops the generation occurrence;
failed visual QA leaves its output as evidence, not canon. Tool permissions
for each phase stay in the domain work order and adapter preflight.

Noema may reference these records after the domain owner creates them. It
does not inspect private media to infer attachment or fidelity, change the
visual canon, or issue human approval. A reusable Noema contract change would
require evidence that this local guard fails across independent consumers,
plus an explicit architecture reopen under `spec/09-versioning-and-change.md`.

## Negative evaluations for the consumer order

- A retrievable reference with no request attachment cannot be reported as bound.
- An attached reference with failed Brand QA cannot be reported as effective.
- An incompatible executor cannot silently replace the approved conditioning path.
- A quarantined generated descendant cannot become a positive root reference.
