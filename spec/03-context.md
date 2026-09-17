# Context Model

Context is progressively loaded. The total repository may be large while the safe startup context remains small.

## Levels
- L0 — project identity, purpose, boundaries.
- L1 — current operating state when relevant.
- L2 — task/domain slice.
- L3 — architecture/evidence depth.
- L4 — historical reconstruction.

## Modes
RC0 recognizes `patch`, `build`, `audit`, `research`, `architect`, and `recover` as context modes. A project may declare mode-specific structural sources in the manifest; the task adds task-specific files.

`AGENTS.md` is an entry map, not the repository encyclopedia. Exact mode-to-file routing belongs in `noema.project.yaml` so it has one machine-readable authority.

## Required vs optional context
- `required` references are validated and loaded for that mode.
- `optional` references are validated for integrity but are not part of cold-start context unless the task explicitly needs them.

A declared reference must not silently rot merely because it is optional.

## Cold-start measurement
Noema's measured project cold start consists of:

1. the declared `context.entrypoint`;
2. `noema.project.yaml`;
3. the selected mode's required project-local context.

The current task itself is intentionally excluded from repository context accounting because task size is external to the project structure.

For cross-project comparisons Noema reports **Noema Context Units v1**, a provider-neutral heuristic equal to `characters / 4`, rounded to the nearest integer. It is a normalized engineering metric, not a claim about billing tokens for GPT, Claude, Gemini, or any other executor.
