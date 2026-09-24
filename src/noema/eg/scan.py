"""Read-only applicability analysis over supplied Noema manifests."""

from __future__ import annotations

from ..schemas import validation_errors


def scan_harvest(harvest: dict, manifests: list[dict], protocol_root=None) -> dict:
    if validation_errors("harvest-candidate", harvest, protocol_root):
        raise ValueError("Harvest input is not a valid Noema HarvestCandidate")
    results = []
    for manifest in manifests:
        errors = validation_errors("project-manifest", manifest, protocol_root)
        project_id = manifest.get("project", {}).get("id", "unknown") if isinstance(manifest, dict) else "unknown"
        if errors:
            results.append({"project_id": project_id, "status": "INCOMPATIBLE", "reasons": ["INVALID_NOEMA_MANIFEST"], "evidence_refs": []})
            continue
        traits = set(manifest.get("traits", []))
        finding = harvest.get("finding", "").lower()
        matched = any(trait.lower() in finding for trait in traits)
        results.append({
            "project_id": project_id,
            "status": "NEEDS_REVIEW" if matched else "NOT_APPLICABLE",
            "reasons": ["TRAIT_MATCH"] if matched else ["NO_DECLARED_APPLICABILITY"],
            "evidence_refs": list(harvest.get("evidence_refs", [])),
        })
    return {"harvest_id": harvest["harvest_id"], "results": results, "read_only": True}
