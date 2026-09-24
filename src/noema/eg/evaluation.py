"""Generic evaluator constraints; criterion semantics remain domain-owned."""

from __future__ import annotations

def derive_evaluation_constraints(work_order: dict, metadata: dict | None = None) -> dict:
    metadata = metadata or {}
    independent = bool(metadata.get("independent_review_required") or "independent-review" in work_order.get("human_gates", []))
    return {
        "quality_claim_ids": list(work_order.get("quality_claims", [])),
        "required_grader_classes": metadata.get("required_grader_classes", []),
        "exact_target_required": bool(metadata.get("exact_target_required", False)),
        "independent_review_required": independent,
        "regression_sensitive": bool(metadata.get("regression_sensitive", False)),
    }
