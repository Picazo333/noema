# Execution Governance v0 Plan Lock

This implementation is bound to Noema `origin/main` baseline
`0e49538c24e51af98a3f3c12706afdbe2e8d812d` after a D0 drift check.

The public surface is limited to `ExecutionEnvelope v0` and
`ExecutionTrace v0`. EG is experimental, opt-in, Git-native, provider-neutral,
and derived from existing WorkOrder/Handoff/EvalResult authority. It must not
own Skill semantics, external tool/model catalogs, executor qualification,
domain quality semantics, runtime scheduling, or domain state.

Security is based on independent deliberation, effect, sensitivity, and
authority axes. DIRECT avoids unnecessary routing but does not bypass control.
