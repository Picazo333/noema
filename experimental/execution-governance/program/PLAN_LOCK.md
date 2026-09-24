# Execution Governance v0 Plan Lock

This implementation is bound to Noema `origin/main` baseline
`0e49538c24e51af98a3f3c12706afdbe2e8d812d` after a D0 drift check.

The public surface is limited to `ExecutionEnvelope v0` and
`ExecutionTrace v0`. EG is experimental, opt-in, Git-native, provider-neutral,
and derived from existing WorkOrder/Handoff/EvalResult authority. It must not
own Skill semantics, external tool/model catalogs, executor qualification,
domain quality semantics, runtime scheduling, or domain state.

Security is based on independent deliberation, effect, sensitivity, and
authority axes. DIRECT avoids unnecessary routing but does not bypass control.

R4 narrowly reopens the two artifact versions to `execution-envelope/v1` and
`execution-trace/v1` under ADR-0008. v0 remains read-only legacy. This does not
reopen the prohibition on a daemon, workflow engine, catalog, agent runtime,
or domain-state ownership.

R5 is a controlled internal reopening of these two v1 contracts, identified
by `contract_revision: 2`. The original v1 schemas remain frozen for historical
reading and cannot yield R5 readiness. G0 must first demonstrate independent
trust bootstrap and positive direct, human-approval, and external-authority
evidence paths as defined in `../EG_EVIDENCE_MODEL.md`. If it cannot, stop with
`TRUST_BOOTSTRAP_UNRESOLVED`. G1-G5 then implement and verify the evidence
boundary. G6 is an independent audit of a frozen SHA and is not performed by
the implementer.

T1 narrowly permits `execution-trace/v1` revision 3 while keeping envelope
revision 2 and both artifact types unchanged. Obligations bind the envelope,
attempt, action, material binding, and occurrence. Partial traces remain valid;
comparison derives coverage and demands independently accepted observation
evidence for material PASS. Mandatory resolver satisfaction requires matching
bytes and authority for the same receipt.

One local commit freezes the candidate SHA. A second clean local checkout and
GitHub Actions Ubuntu must verify that same SHA, with evidence outside Git.
Only the frozen experimental branch may be pushed after the clean local gate;
no merge, release, or consumer-pin update is authorized. CI success never
replaces independent adversarial review or domain authority.

## vNext final-closure scope (Sol 6, 2026-09-23)

The later frozen implementation package
`NOEMA_VNEXT_FINAL_PLAN_LOCK_SOL6_2026-09-23.md` governs this bounded closure;
the earlier R4/R5 history above is not the current audit verdict. The
implementation branch incorporates main `530751b471e07a3b2a6acc31a864d408442b56c5`
without mutating the historical EG branch. It adds strict YAML loading,
CandidateSnapshot identity rejection, the `state.execution` current cursor,
an operational recovery checkpoint and read-only `noema eg recover`. It does
not add a public contract type or transfer authority to Noema.

The tracked checkpoint is a snapshot, not a self-certifying claim for its own
commit. A later exact-SHA checkout must classify an older checkpoint as stale;
an authorized external writer must refresh current operational state. The
advisory Process Auditor WorkOrder is explicitly addressed to Skill Foundry,
which owns its semantics. Exact-SHA tests and Actions evidence belong outside
the audited commit; independent audit remains a separate gate.

## Post-merge release closure (2026-09-24)

The vNext candidate `36ceacd8d37ab45964ca512b83b67d68941a0549`
received `INDEPENDENT_REAUDIT_PASS` and a fresh
`GLOBAL_REVIEW_PASS`, then merged through PR #10. The integrated main baseline
`ecf4f0ae0878dbbe4c8e4f09b65846698f6c8e3b` passed post-merge CI run
`36047015874`.

The vNext architecture is frozen. Further changes require material evidence
from dogfood, a bounded defect, or an explicit ArchitectureException. The
operational next phase is transversal adoption across governed repositories,
performed from each target repository's own authoritative state and write
authority. Noema itself does not perform cross-repository writes.

The versioned `state.execution` checkpoint remains a snapshot rather than a
self-certifying reference to the commit that contains it. Any later commit
advances Git and can therefore make that snapshot stale; `eg recover` must
continue to fail closed until an authorized host refreshes operational state.
