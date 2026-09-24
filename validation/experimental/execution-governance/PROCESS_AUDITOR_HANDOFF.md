# Explicit handoff to Skill Foundry — advisory Process Auditor dogfood

Recipient: Skill Foundry capability owner. This document is a handoff package,
not an automatic trigger or a claim that Skill Foundry has executed it.

Use the ordinary WorkOrder in `PROCESS_AUDITOR_WORK_ORDER.yaml` to assess the
Noema vNext execution process after the implementation SHA is frozen. Inputs
are the frozen Plan Lock, the exact-SHA candidate and the local/CI evidence
bundle supplied by the requester. Return an advisory report to the requester.
Do not write to Noema (`allowed_writes: []`), create a Noema Skill registry,
or recursively start another process audit.

The implementing agent cannot certify the Process Auditor's output or send a
cross-repository write on Skill Foundry's behalf. Acceptance/execution by
Skill Foundry is a separate external action, not inferred from this file.
