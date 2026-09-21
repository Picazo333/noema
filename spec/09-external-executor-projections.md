# External Executor Projections

Noema RC0 may receive stable executor candidates from domain systems such as StackIA, but external projections do **not** become routing authority automatically.

## Authority boundary

- Domain systems own their specialized state and evidence.
- StackIA owns AI-tool/integration state, verification evidence, executor qualification state, and its derived executor projection.
- Noema owns executor descriptors used by RC0 and the routing policy that consumes them.
- Runtime quota, reset, outage, and session state remains outside Git by default.

## StackIA integration

StackIA publishes its stable candidate projection at:

`github://Picazo333/stack-ia/exports/noema/executors.yaml`

The source projection is **derived** from StackIA's canonical catalog/state/evidence. It is not a source of truth for Noema routing.

### Promotion flow

1. StackIA verifies a candidate executor against an explicit representative workload.
2. StackIA marks the candidate eligible in its executor-qualification state.
3. StackIA emits a stable descriptor in `exports/noema/executors.yaml`.
4. A human/review gate compares the candidate with Noema's executor contract.
5. Only an approved descriptor is copied/promoted into Noema's `registry/executors.yaml`.
6. Existing Noema lint/tests validate route references and executor status.
7. RC0 may route to the executor only when the local Noema descriptor status is `verified`.

Noema does not read the external StackIA projection during each routing decision.

## Why promotion is explicit

Automatic cross-repository ingestion would introduce an external mutable dependency into RC0 and could allow a domain system to alter routing authority without a Noema review.

That would violate:

- domain/coordination authority separation;
- evidence before canon;
- derived views never silently become authority;
- reversible governance;
- the RC0 technical freeze.

## Descriptor compatibility

A candidate promoted from StackIA must map to the existing Noema executor fields:

- `id`
- `provider`
- `status`
- `capabilities`
- `modalities`
- `interfaces`
- `constraints`
- `last_verified`

The external projection may be empty. An empty projection is valid and means no StackIA candidate currently meets the stable executor gate.

## Runtime availability

Stable verification and runtime availability remain separate.

A promoted executor can be structurally `verified` in `registry/executors.yaml` and still be ineligible at runtime when `~/.noema/runtime/availability.yaml` marks it disabled, blocked, or down.

Credits, resets, quota balances, and transient outages are not copied into the stable executor descriptor.

## RC0 invariant

This integration requires no change to:

- `src/noema/routing.py`
- `registry/routing.yaml`
- deterministic preference/fallback semantics.

If a future workflow requires automatic external projection ingestion, that is a separate architecture change and must be activated explicitly rather than introduced through this integration.
