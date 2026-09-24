# ADR-0008 — Experimental Execution Governance Profile v0

**Status:** ACCEPTED; R4 versioning and R5 internal evidence-binding amendments

Noema adds an opt-in execution-governance profile with exactly two protocol
schemas: `execution-envelope/v0` and `execution-trace/v0`. The envelope is
derived coordination state, while WorkOrder, Handoff, and EvalResult retain
their existing authorities. The trace records observable execution evidence,
not private reasoning or secrets.

The profile reuses the existing context and deterministic executor routers.
Capability semantics stay with Skill Foundry; tool/model/executor qualification
truth stays external and is supplied only as runtime/projection input. Runtime
pressure is ephemeral input and never Git quota truth. Harvest applicability is
read-only. No daemon, workflow engine, catalog, or agent runtime is introduced.

## R4 amendment

The two artifact types may have explicit v1 contracts: `execution-envelope/v1`
and `execution-trace/v1`. This is a version of the same two types, not an
authorization for further public artifact types or runtime infrastructure.
v0 remains readable as experimental legacy evidence, but v0 validation does
not certify v1 structural closure. v1 binds the input projection and requires
public replay before a PASS. Missing external source evidence is UNVERIFIED,
not PASS. WorkOrder, Handoff, EvalResult, and external qualification authorities
remain unchanged.

## R5 internal evidence-binding amendment

The same two experimental artifact types may carry an explicit
`contract_revision: 2` while revision-1 schemas remain available for historical
reading. An artifact can be structurally and semantically valid without being
ready for execution. Readiness is calculated for the current invocation from
observed bytes and independently accepted sources; persisted claims, receipts,
and past readiness results cannot authenticate themselves.

The verifier consumes a transient, operator/host-controlled trust context. It
does not issue human approvals or own external qualification truth. If that
context cannot be established, material execution remains unverified. R5 does
not authorize another public artifact type, service, registry, provider-specific
core, or a change to WorkOrder, Handoff, EvalResult, or RC0 routing semantics.

## R5 targeted closure T1

The v1 envelope remains at revision 2. The v1 trace may use revision 3 to
report occurrence-bound tool and actor observations, including explicit
nonparticipation and material workspace, branch, and write scope. Trace r2
remains readable without invented observations. Coverage is computed during
comparison, not trusted from a trace field. Material PASS additionally needs
an independently pinned host observation snapshot. GitHub Actions checks the
frozen commit operationally and does not supply domain authority.
