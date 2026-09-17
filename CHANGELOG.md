# Changelog

## 0.1.0-rc.0
- Reframed Noema as a Git-native governance and conformance protocol.
- Added project composition, authority, relations, context, quality-claim, artifact, routing, and harvest foundations.
- Added deterministic CLI surface: init, lint, audit, harvest.
- Explicitly separated conformance from project quality.
- Added ecosystem discovery index and future capability registry.
- Hardened the validator after the first greenfield consumer exposed unsafe context-entrypoint and malformed-registry edge cases.
- Made Ruff CI policy explicit to prevent silent rule-family drift.
- Added provider-neutral context measurement that includes the manifest, validates optional refs, and reports every declared context mode.
- Consolidated project scaffolding around canonical templates consumed by `noema init`.
- Added CI constraints, bounded permissions/timeouts, and pip caching for more reproducible conformance.
- Hardened Harvest IDs against parallel collisions and added evidence capture at candidate creation.
- Registered the plastic-surgeon demo as the first external greenfield reference consumer and recorded its exhaustive harvest.
