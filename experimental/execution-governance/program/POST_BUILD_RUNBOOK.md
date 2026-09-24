# Post-build runbook

1. Give Jules the exact implementation SHA, the diff, the validation evidence,
   this Plan Lock, and `DOWNSTREAM_ADOPTION_HANDOFF.md`.
2. Jules returns `PASS` or `REWORK` without editing the target. Repair only
   accepted implementation defects and re-audit the new exact SHA.
3. Merge only after independent PASS and green conformance; then run the smoke
   self-dogfood canaries.
4. Freeze the v0 downstream interface. Skill Foundry reviews it against its
   then-current canon; any Foundry work is owned there. Afterwards review other
   repos one at a time. `NO_CHANGE` is valid.
