"""Selection policy over caller-supplied candidates, never a catalog."""

from __future__ import annotations

from .enums import ToolDecision


_RANK = {"AUTHORITATIVE": 0, "DIRECT": 1, "INDIRECT": 2, "BROAD": 3}


def _qualified(candidate: dict) -> bool:
    return (candidate.get("allowed") is True
            and candidate.get("available") is True
            and candidate.get("qualification") == "VERIFIED"
            and candidate.get("availability") in {"AVAILABLE", "available"})


def decide_tools(candidates: list[dict], requirements: dict | None = None, *, control: str = "ALLOW") -> list[dict]:
    requirements = requirements or {}
    required = set(requirements.get("capabilities", []))
    eligible = []
    for candidate in candidates:
        supplied = set(candidate.get("capabilities", []))
        if (
            control not in {"DENY", "ROUTE_ELSEWHERE"}
            and _qualified(candidate)
            and required.issubset(supplied)
        ):
            eligible.append(candidate)
    best = min(
        (_RANK.get(candidate.get("source_relation", "BROAD"), 3) for candidate in eligible),
        default=None,
    )
    decisions = []
    for candidate in candidates:
        ident = candidate.get("id") or candidate.get("candidate") or "unknown"
        supplied = set(candidate.get("capabilities", []))
        if control in {"DENY", "ROUTE_ELSEWHERE"} or candidate.get("allowed") is False:
            decision, reason = ToolDecision.HARD_DENY, "CONTROL_INELIGIBLE"
        elif not required.issubset(supplied):
            decision, reason = ToolDecision.HARD_DENY, "CAPABILITY_INSUFFICIENT"
        elif candidate.get("allowed") is not True:
            decision, reason = ToolDecision.HARD_DENY, "CANDIDATE_NOT_ALLOWED"
        elif not _qualified(candidate):
            decision, reason = ToolDecision.DEFER, "CANDIDATE_UNVERIFIED"
        elif best is not None and _RANK.get(candidate.get("source_relation", "BROAD"), 3) > best and not candidate.get("adds_material_evidence"):
            decision, reason = ToolDecision.SOFT_SUPPRESS, "AUTHORITATIVE_SOURCE_DIRECT"
        else:
            decision, reason = ToolDecision.CALL, "FUNCTIONALLY_SUFFICIENT"
        decisions.append({
            "candidate": ident,
            "decision": decision.value,
            "reason_codes": [reason],
            "source_relation": candidate.get("source_relation", "BROAD"),
            "availability": candidate.get("availability", "UNKNOWN"),
            "qualification": candidate.get("qualification", "UNAVAILABLE"),
        })
    return decisions
