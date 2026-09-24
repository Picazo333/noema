# Execution Governance Profile — vNext final-closure candidate

This is Noema's opt-in, experimental execution-governance substrate. It derives
an `ExecutionEnvelope` from an existing WorkOrder and records observed work in
an `ExecutionTrace`; it does not run agents, own domain state, or copy external
catalogs.

The public artifact types remain ExecutionEnvelope and ExecutionTrace. New
plans and traces use `execution-envelope/v1` and `execution-trace/v1`; v0 is
readable legacy evidence but cannot receive v1 structural certification.
The v1 envelope binds input snapshots to canonical digests and replays the
decision at public validation. File-backed sources must still match; missing
sources are UNVERIFIED. Memory-backed programmatic inputs are content-bound,
not externally authenticated. Host capabilities, candidate snapshots, runtime
pressure, and Harvest scan reports remain experimental inputs or derived reports.

Only explicitly allowed, available, and verified tool candidates can be
called. Human gates remain outstanding until evidence-backed clearance.
Read suppression requires an integrity-bound reference; arbitrary freshness
tokens and version labels do not establish stable identity.

`validation/experimental/execution-governance/R5_CANARY_DEFINITIONS.json` contains
test definitions, not results. After committing, generate evidence for the
clean HEAD outside the repo with:

```bash
python -m noema.eg.dogfood . validation/experimental/execution-governance/R5_CANARY_DEFINITIONS.json /path/outside/repo --expected-sha <frozen-sha>
```

Use `python -m noema eg doctor .` to inspect available host evidence and
`python -m noema eg --help` for the read-only/planning commands.

T1 keeps envelope v1-r2 and emits trace v1-r3. `eg explain --json` lists
occurrence-bound material obligations. `record` may preserve partial reports;
`compare` and `validate trace --envelope` compute coverage and require a
host-pinned observation snapshot before certifying material conformance.
Historical r2 traces remain readable without invented actor attributes.
For material tool or actor obligations, r3 observations need the exact
`obligation_ref` shown by `explain`; unbound events remain in the trace but
cannot complete coverage. An r2 name association is diagnostic, not a
material conformance PASS.

After the T1 commit is frozen, run `.github/scripts/verify_t1.py` from a
separate clean checkout with `--root`, `--expected-sha`, and an empty external
`--output-dir`. It repeats all five required checks and 35 canaries. Only a
successful clean local run permits publishing the frozen experimental branch
for exact-SHA GitHub Actions. Keep results outside Git; Actions green is not
a substitute for independent audit.

Final-closure inputs are strict: duplicate YAML mapping keys and duplicate or
missing candidate IDs within each category fail before selection. `noema eg
recover . --json` reads the manifest's `state.execution` cursor, operational
checkpoint, Handoff and WorkOrder without reading an old conversation. It does
not mutate them or turn an unverified claim into authority. A stale checkpoint,
human gate or missing evidence prevents material continuation. A committed
checkpoint cannot contain its own future commit SHA; refresh it through an
authorized external writer after a new commit. A clean checkout will correctly
report the previously committed checkpoint as stale until that refresh is
available. Cross-device continuity requires the latest checkpoint to be
accessible on the destination host; Git alone cannot atomically self-pin it.

Host-reported context pressure is advisory: LOW/MODERATE continue, HIGH asks
preparation, CRITICAL recommends migration, and absent telemetry remains
UNKNOWN. Noema does not create a new chat, change executors or clear gates.
No material tool need yields no material CALL even if execution is routed for
another reason. Stable read identity still governs repeat-read suppression.

The advisory Process Auditor WorkOrder is
`validation/experimental/execution-governance/PROCESS_AUDITOR_WORK_ORDER.yaml`.
It is an explicit handoff package for Skill Foundry, the capability owner;
Noema does not execute, register, trigger or certify that auditor.

Role, executor and model remain separate identities. A model/provider swap
does not change the role, ownership or historical evidence authorship.
Independent review still requires an independent actor, exact target and
appropriate reproduction; provider diversity alone is not a review verdict.
