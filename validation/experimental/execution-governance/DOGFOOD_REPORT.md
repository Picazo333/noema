# Deterministic dogfood report

The deterministic suite covers all 22 declared strata through local fixtures or
pure policy tests: direct/no-action decisions, scoped writes, deliberation,
secret/canonical/foreign controls, resolver receipts, RC0 executor/model
boundaries, topology, resume, read-only Harvest, context tiers/deduplication,
and all resource postures. Host token and monetary telemetry remain
`UNAVAILABLE` unless explicitly supplied; this run claims none. The complete
matrix is in `CANARY_MANIFEST.yaml`; host-backed effects remain subject to host
evidence.
