# KICKSTART — W07 Protocol Portability, CI & Artifact Promotion

- **Role:** Portability & CI protocol engineer (W07) in noema
- **Repo:** `noema` (local `Desktop/Repos/noema`, remote github://Picazo333/noema)
- **WorkOrder:** `state/workorders/W07-protocol-portability/WORK_ORDER.yaml` @ `claude/noema/genesis-w07` (commit in `CHECKPOINT.yaml#genesis_ref`; use `main` once the Genesis PR is merged)
- **Read in order:** `AGENTS.md` → `noema.project.yaml` → `state/workorders/W07-protocol-portability/CHECKPOINT.yaml` → `WORK_ORDER.yaml` → `REQUIREMENTS.yaml` → `ACCEPTANCE_CONTRACT.md` → `CONTEXT_BUNDLE.md`
- **Current state:** `WAITING_DEPENDENCY` — Starts when central contract shapes are sufficiently stable: W02 DOWNSTREAM_REQUIREMENTS shape and W03 protocol schemas committed (start edges). Home = noema per DEC-W07-HOME (recommended; confirm at PR review).
- **Branch / write boundary:** `<prefix>/noema/w07-protocol-portability`; write only `WORK_ORDER.yaml#allowed_writes`; PR to `main` (protected).
- **First required action:** When W02 WP3 and W03 WP2 are committed, create <prefix>/noema/w07-protocol-portability from the Genesis ref and run WP1: inventory current entry paths (AGENTS.md, noema.project.yaml, CLAUDE.md adapters) across agency-foundation, skill-foundry, stack-ia, 4geeks-control-tower, noema.
- **Terminal / gate condition:** H-W07 PASS
