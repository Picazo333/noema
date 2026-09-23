# EG R5 evidence model and G0 trust boundary

Status: G0 architecture specification. R5 remains experimental and opt-in.
The only public EG artifact types are ExecutionEnvelope and ExecutionTrace.

## Threat model and bootstrap

An evaluated actor may alter WorkOrders, metadata, envelopes, traces, refs,
candidate snapshots, resolver receipts, handoff/state files, and nominal
authority strings. It may not alter the verifier implementation used by the
relying host, the host/operator invocation, protected trust inputs, or immutable
observations used by that invocation. If it can alter these, Noema cannot issue
an independent readiness result.

The invocation creates a transient VerificationContext with separate real
project and protected package roots, policy/verifier revisions, an observed
baseline and material state, an evaluation instant, and a finite map of trusted
sources. Each source is accepted only for named predicates, subjects, scopes,
and validity intervals. The context is selected by the operator/host outside
the evaluated artifact and actor write scope. A standalone CLI invocation
without such a context may plan or validate shape but returns UNVERIFIED for
authority predicates and NOT_EXECUTION_READY for material effects. Consumers
must pin the expected trust-root identity; an arbitrary process can print a
result relative to its own chosen root but cannot make that root trusted by a
different consumer.

Repository-local policy or evidence is trusted only when the protected
invocation pins its exact committed object/digest and the verifier checks the
actual bytes. HEAD alone does not prove a clean tree. Dirty material inputs
require their own observed digests. Protected policy, schemas, and verifier
code must be outside the evaluated actor's write authority. An envelope,
trace, resolver result, candidate snapshot, or --state file cannot promote
itself by naming an authority or referring to another attacker-controlled file.

G0 has three positive paths, each using real verification logic: (A) Noema
reads bytes and computes CONTENT_INTEGRITY; (B) a separately accepted approval
is checked for the exact gate fingerprint and HUMAN_APPROVAL; (C) a separately
accepted external qualification projection is checked for exact subject,
predicate, scope, digest, and freshness. Test fixtures may represent an
external authority; production qualification remains UNVERIFIED until a real
source is accepted by the host. G0 stops with TRUST_BOOTSTRAP_UNRESOLVED if
any path cannot be demonstrated without circular authority.

G0 architecture spike on the R4 checkout observed 2,488 bytes from
`PROTOCOL.md` and recomputed their SHA-256. A separately pinned approval
fixture yielded HUMAN_APPROVAL=VERIFIED for its exact gate subject; a separately
pinned qualification fixture yielded TOOL_QUALIFICATION=VERIFIED for its exact
tool/capability subject. Wrong subjects and an invented authority source
yielded UNVERIFIED. The spike used real JSON parsing, SHA-256, scope, subject,
and expiry checks without replacing the verifier result with a mock. It proves
the mechanics of a non-circular root, not that the current R4 CLI provides a
protected invocation. G2/G3 must establish that transport and repeat all three
positive paths through the public CLI before readiness can be claimed.

## Frozen vocabulary

CLAIM is a supplied assertion. PREDICATE is the exact property tested.
EVIDENCE is a source offered for that predicate. OBSERVATION is what the
verifier or trusted host actually examined. VERIFICATION is the predicate,
subject, and context-specific result. AUTHORITY may assert a predicate only
within an accepted scope. REQUIREMENT is a condition derived from intent and
policy; DEPENDENCY is a requirement relying on another source or candidate.
MATERIAL_INTENT identifies the exact operation that may be authorized.
ENVELOPE_IDENTITY identifies the complete envelope document. APPROVAL is
external evidence for a gate fingerprint. READINESS is current permission to
proceed, never a persisted credential. DEVIATION is a reported difference
between planned and actual execution.

Evidence states are VERIFIED, UNVERIFIED, INVALID, and NOT_REQUIRED.
NOT_REQUIRED is policy-derived, never candidate-declared. Every result names
requirement_id, subject_fingerprint, predicate, method, source_ref/digest,
authority where applicable, observed_at, valid_until, and safe reason_codes.
CONTENT_INTEGRITY=VERIFIED does not imply HUMAN_APPROVAL=VERIFIED.

Structural validity, semantic validity, predicate-specific verification,
and current execution readiness are separate results. An honest document with
a pending approval is semantically valid and NOT_EXECUTION_READY. Readiness
must be recalculated against current context, material state, policy,
evidence, authority, and gates at every public gate.

## Binding and field policy

EG-C14N-1 uses strict JSON-compatible types, sorted keys, fixed separators,
UTF-8, finite numbers, and duplicate-key rejection. Domain-separated hashes
identify material intent, full envelope, and gate approval. Material intent
includes execution/attempt, WorkOrder, action/effect/target, authority,
permissions, requirements, candidate plan, topology, policy, and material
state. It excludes its own digest, approving evidence, and derived readiness.
The envelope digest covers the complete immutable envelope but is stored only
in the trace. Gate fingerprint covers material digest, gate, action, and
attempt. Changing any material field invalidates prior approval.

Every revision-2 schema field is classified MATERIAL, EVIDENCE, DERIVED, or
NON_MATERIAL. This applies recursively, including allowed map-key patterns.
Unclassified or open-ended new fields fail schema-classification tests and
validation. Typed projections replace arbitrary raw input snapshots.

The existing v0 and v1 schemas stay frozen. New revision-2 schemas have
distinct identifiers and require contract_revision=2. v0 remains
LEGACY_VALID, v1 revision 1 remains LEGACY_V1_UNVERIFIED, and neither receives
R5 readiness. Unknown revisions are rejected. No migration invents evidence.

## Domain and operational limits

Noema verifies that a particular external claim is supported; qualification
truth remains with its owning system. Direct byte integrity does not establish
who authored content. A well-formed caller-supplied hash does not establish
observed read identity, and reading bytes now does not prove a historical read
event. Parallel isolation requires authority containment, exclusive writers,
and observed host isolation. A stateless verifier cannot prove one-time
consumption of the same approval within the same attempt.

EG persistence uses typed projections, rejects defined credential families
in durable values and diagnostics, and writes atomically. It does not claim to
recognize every possible arbitrary secret encoded as innocuous text.

Post-commit canary evidence is generated outside Git for the exact frozen SHA.
A report inside its own commit cannot contain that commit's final SHA without
a hash self-reference; the in-repo implementation report must point to the
external post-commit evidence rather than claim its own final SHA.
