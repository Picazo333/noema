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
