# ACCEPTANCE CONTRACT — W07 Protocol Portability, CI & Artifact Promotion

## Definition of Done
H-W07 PASS; checks green on Genesis packages; clean-session workload ready for a Sonnet 5.5 run.

**Terminal state:** `PASS`

## Requirement acceptance
| Req | Priority | Observable acceptance |
|---|---|---|
| W07-R01 | MUST | spec/11 lists ≤5 hops; each repo's current files mapped. |
| W07-R02 | MUST | spec/11 rule + check script flags adapters >N lines of authority content. |
| W07-R03 | MUST | Eval doc + workload file; dry-run instructions. |
| W07-R04 | MUST | Receipt schema validates example; spec states unobservable targets explicitly. |
| W07-R05 | MUST | check_workorder_package.py passes on all Genesis packages; fails on seeded broken fixture. |

All MUST rows require committed evidence (see `EXPECTED_EVIDENCE.yaml`). A narrative, an agent's PASS or a green build alone is never acceptance.

## Gates that may stop advancement
- H-W07: human accepts new spec sections (noema ADR if protocol semantics change)

## Independent audit
Not planned by default; open one only through the audit protocol if a material finding justifies it.
