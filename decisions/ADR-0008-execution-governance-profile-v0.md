# ADR-0008 — Experimental Execution Governance Profile v0

**Status:** ACCEPTED

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
