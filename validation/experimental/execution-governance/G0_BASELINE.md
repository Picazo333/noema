# G0 baseline seal

- Pack reference SHA: `0e49538c24e51af98a3f3c12706afdbe2e8d812d`
- Actual fetched `origin/main`: `0e49538c24e51af98a3f3c12706afdbe2e8d812d`
- Drift classification: `D0` (none)
- Baseline evidence: `python -m ruff check .`, `pytest`, `python -m noema lint .`,
  and `python -m noema audit . --section context` passed after the separately
  reviewable portability repair commit.
