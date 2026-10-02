# RECOVERY AND HANDOFF — W07

Resume with `github://Picazo333/Divinivid/docs/08-plans/program/protocols/@957098dc0ed80bbba3432be1d0a5e202f1ef0d0dRESUME_PROTOCOL.md` using this package's `CHECKPOINT.yaml` (schema `CHECKPOINT_SCHEMA.yaml`).

## WorkOrder-specific checkpoint boundaries
- after each WP
- H-W07
- plus every program boundary in CHECKPOINT_SCHEMA.yaml#checkpoint_boundaries

## Forbidden replay
- —

**Side effects:** none permitted by this WorkOrder.

## Execution branch
`<prefix>/noema/w07-protocol-portability` created from the Genesis ref (or `main` once the Genesis PR is merged). Prefix per `Repos/CLAUDE.md` (claude-code→claude, cursor→cursor, codex→codex). Executors without git write access (e.g. ChatGPT Work) do not commit: a git-capable executor commits their outputs and records the producing executor in `CHECKPOINT.yaml#updated_by`.

## Downstream handoff
| Artifact | Consumer |
|---|---|
| reusable CI + entry-path spec + promotion protocol | every repo (adoption via own PR), W00 (freshness checks) |

Consumers read handoff artifacts from this repo at the SHA recorded in `CHECKPOINT.yaml#current_sha`, never from chat.

## Unexpected needs
Classify with `github://Picazo333/Divinivid/docs/08-plans/program/protocols/@957098dc0ed80bbba3432be1d0a5e202f1ef0d0dEXPANSION_POLICY.md`; record in `CHECKPOINT.yaml#child_inquiries` or `#blockers`. Unaffected work continues.
