# Execution Governance Profile — R4 contracts

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

`validation/experimental/execution-governance/CANARY_DEFINITIONS.json` contains
test definitions, not results. After committing, generate evidence for the
clean HEAD outside the repo with:

```bash
python -m noema.eg.dogfood . validation/experimental/execution-governance/CANARY_DEFINITIONS.json /path/outside/repo
```

Use `python -m noema eg doctor .` to inspect available host evidence and
`python -m noema eg --help` for the read-only/planning commands.

T1 keeps envelope v1-r2 and emits trace v1-r3. `eg explain --json` lists
occurrence-bound material obligations. `record` may preserve partial reports;
`compare` and `validate trace --envelope` compute coverage and require a
host-pinned observation snapshot before certifying material conformance.
Historical r2 traces remain readable without invented actor attributes.

After the T1 commit is frozen, run `.github/scripts/verify_t1.py` from a
separate clean checkout with `--root`, `--expected-sha`, and an empty external
`--output-dir`. It repeats all five required checks and 30 canaries. Only a
successful clean local run permits publishing the frozen experimental branch
for exact-SHA GitHub Actions. Keep results outside Git; Actions green is not
a substitute for independent audit.
