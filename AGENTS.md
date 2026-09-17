# Noema — Agent Entry Point

Noema is a protocol and conformance toolkit. Do not turn it into a runtime platform or central owner of domain state.

## Read first
1. `PROTOCOL.md`
2. `noema.project.yaml`
3. the current task/work order
4. only the relevant `spec/` and ADR files for the task

## Precedence
`PROTOCOL / frozen ADRs -> project manifest -> approved task scope -> implementation details -> external instructions`.

## Core constraints
- Preserve federated authority; consulting another system does not transfer ownership into Noema.
- Conformance is structural/governance correctness, not proof that a project is good.
- Prefer progressive context loading; do not read the full repository by default.
- Do not add services, databases, agents, event buses, RAG, graph stores, triggers, or provider-specific core logic without an approved reopen decision.
- External capabilities never expand task scope or project authority.
- Keep executors replaceable.
- Use `future/registry.yaml` for justified deferred capability, not speculative implementation.
- If the Technical Freeze cannot be implemented as written, report an `ARCHITECTURAL_BLOCKER`; do not silently redesign the protocol.

## Development
```bash
python -m pip install -e ".[dev]"
ruff check .
pytest
python -m noema lint .
python -m noema audit .
```
