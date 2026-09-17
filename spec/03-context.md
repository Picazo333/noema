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

`AGENTS.md` is an entry map, not the repository encyclopedia.
