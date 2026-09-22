# Execution Governance Profile v0

This is Noema's opt-in, experimental execution-governance substrate. It derives
an `ExecutionEnvelope` from an existing WorkOrder and records observed work in
an `ExecutionTrace`; it does not run agents, own domain state, or copy external
catalogs.

The public protocol additions are only `execution-envelope/v0` and
`execution-trace/v0`. Host capabilities, candidate snapshots, runtime pressure,
and Harvest scan reports are experimental inputs or derived reports.

Use `python -m noema eg doctor .` to inspect available host evidence and
`python -m noema eg --help` for the read-only/planning commands.
