"""Deterministic rendering of experimental EG canary evidence."""

from __future__ import annotations


def render_dogfood_report(results: dict) -> str:
    rows = results.get("canaries", [])
    lines = [
        "# Execution Governance R3 dogfood evidence",
        "",
        "Generated from `CANARY_RESULTS.json`; do not edit this report manually.",
        f"Audited starting SHA: `{results['audited_start_sha']}`.",
        "",
        "| ID | Scenario | Level | Public entrypoint | Test/evidence | Expected / observed | SHA | Status |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| {id} | {scenario} | {level} | {public_entrypoint} | {evidence} | {expected} / {observed} | {sha} | {status} |".format(**row)
        )
    return "\n".join(lines) + "\n"
