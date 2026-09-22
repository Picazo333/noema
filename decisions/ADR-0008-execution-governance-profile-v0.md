# ADR-0008 — Experimental Execution Governance Profile v0

**Status:** ACCEPTED; R4 narrow versioning amendment

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
