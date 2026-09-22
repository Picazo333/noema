#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def y(rel):
    with open(ROOT / rel, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def j(rel):
    with open(ROOT / rel, "r", encoding="utf-8") as f:
        return json.load(f)


def fail(msg):
    raise SystemExit(f"FAIL: {msg}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--month", required=True)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--capacity", required=True)
    a = p.parse_args()

    snapshot = json.loads(Path(a.snapshot).read_text(encoding="utf-8"))
    capacity = json.loads(Path(a.capacity).read_text(encoding="utf-8"))

    Draft202012Validator(j("schemas/ui-snapshot/v1.schema.json")).validate(snapshot)
    Draft202012Validator(j("schemas/capacity-router/v1.schema.json")).validate(capacity)

    month = y(f"state/months/{a.month}.yaml")
    month_index = y("state/months/index.yaml")
    subscriptions = y("state/subscriptions.yaml")
    evaluations = y("state/evaluations.yaml")
    deployments = y("state/deployments.yaml")
    needs = y(f"state/needs/{a.month}.yaml")
    scaling = y(f"state/scaling/{a.month}.yaml")
    noema = y("exports/noema/executors.yaml")
    scenario = j(f"ui/derived/scenarios/{a.month}.proposal.json")
    verification_workloads = y("validation/verification-workloads.yaml")
    media_workloads = y("validation/media-factory-workloads.yaml")
    qualification = y("state/executor-qualification.yaml")

    paid_ids = [x["subscription_id"] for x in month["budget"]["paid_plans"]]
    snap_paid = [x["subscription_id"] for x in snapshot["budget"]["paid_plans"]]
    if snap_paid != paid_ids:
        fail(f"paid membership drift: {snap_paid} != {paid_ids}")

    for name in ("ACTUAL", "LEAN", "SCALE"):
        if scenario["scenarios"][name]["paid_subscription_ids"] != paid_ids:
            fail(f"{name} paid membership differs from locked month")

    ref = month["budget"]["totals"]["reference_active_stack_mxn_excluding_capcut"]
    if snapshot["overview"]["spend"]["reference_mxn"] != ref:
        fail("reference MXN drift")
    if snapshot["overview"]["spend"]["known_exact_mxn"] != 794:
        fail("October known exact MXN must be 794")
    if snapshot["overview"]["spend"]["paid_confirmed_mxn"] != 0:
        fail("October paid_confirmed_mxn must be 0 for PLANNED rows")

    # Independent evaluation truth.
    evs = []
    for k, v in evaluations.items():
        if k.endswith("_evaluations") and isinstance(v, list):
            evs.extend(v)
    counts = {"VERIFIED": 0, "TESTED": 0, "UNVERIFIED": 0}
    for e in evs:
        counts[e["verification"]] = counts.get(e["verification"], 0) + 1
    if counts != {"VERIFIED": 4, "TESTED": 6, "UNVERIFIED": 86}:
        fail(f"evaluation baseline changed unexpectedly after Decision 0017: {counts}")

    if len(deployments.get("deployments", [])) != 20:
        fail("explicit deployment baseline must be 20")

    # Full registry must include every tool + integration.
    tool_count = len(y("catalog/tools.yaml").get("tools", []))
    ints_doc = y("catalog/integrations.yaml")
    integration_count = sum(len(ints_doc.get(k, []) or []) for k in ("skills", "mcps", "plugins_connectors"))
    expected_registry = tool_count + integration_count
    if tool_count != 91:
        fail(f"Decision 0017 tool baseline drift: {tool_count} != 91")
    if integration_count != 92:
        fail(f"integration baseline drift: {integration_count} != 92")
    if expected_registry != 183:
        fail(f"Decision 0017 registry baseline drift: {expected_registry} != 183")
    if snapshot["overview"]["counts"]["registry_items"] != expected_registry:
        fail(f"registry count {snapshot['overview']['counts']['registry_items']} != {expected_registry}")
    if snapshot["overview"]["counts"].get("unknown") != 87:
        fail("Decision 0017 must not convert pre-existing UNKNOWN identities")
    if len(snapshot["actions"]) != 90:
        fail(f"Decision 0017 action baseline drift: {len(snapshot['actions'])} != 90")
    if len(snapshot["budget"]["paid_plans"]) != 6:
        fail("Decision 0017 must not add a paid-plan row")

    # Historical monthly UI coverage required by the approved monolith IA.
    available_months = [x["month"] for x in month_index.get("months", []) or []]
    if snapshot["selection"].get("available_months") != available_months:
        fail(f"available month projection drift: {snapshot['selection'].get('available_months')} != {available_months}")
    if set(snapshot.get("monthly", {})) != set(available_months):
        fail("monthly comparison projection must contain every indexed locked month")

    subscription_by_id = {x["id"]: x for x in subscriptions.get("subscriptions", []) or []}
    def expected_month_spend(month_state):
        known = sum((r.get("confirmed_mxn") or 0) for r in month_state["budget"]["paid_plans"])
        paid = sum(
            (r.get("confirmed_mxn") or 0)
            for r in month_state["budget"]["paid_plans"]
            if r.get("payment_state") in ("PAID", "CHARGED", "SETTLED")
        )
        ref = (month_state["budget"].get("totals", {}) or {}).get("reference_active_stack_mxn_excluding_capcut")
        unresolved = list((month_state["budget"].get("totals", {}) or {}).get("unresolved_items", []) or [])
        return known, paid, ref, unresolved

    for meta in month_index.get("months", []) or []:
        mid = meta["month"]
        source = y(meta["path"])
        projected = snapshot["monthly"][mid]
        expected_paid_ids = [x["subscription_id"] for x in source["budget"]["paid_plans"]]
        if [x["subscription_id"] for x in projected["paid_plans"]] != expected_paid_ids:
            fail(f"{mid} paid-plan projection drift")
        for row in projected["paid_plans"]:
            if row["subscription_id"] not in subscription_by_id:
                fail(f"{mid} broken projected subscription {row['subscription_id']}")
            if not row.get("billing_period"):
                fail(f"{mid} missing billing period for {row['subscription_id']}")
        known, paid, ref_total, unresolved_ids = expected_month_spend(source)
        if projected["spend"]["known_exact_mxn"] != known:
            fail(f"{mid} known-exact projection drift")
        if projected["spend"]["paid_confirmed_mxn"] != paid:
            fail(f"{mid} paid-confirmed projection drift")
        if projected["spend"]["reference_mxn"] != ref_total:
            fail(f"{mid} reference projection drift")
        if projected["spend"]["unresolved_subscription_ids"] != unresolved_ids:
            fail(f"{mid} unresolved projection drift")

    if snapshot["monthly"]["2026-09"]["spend"]["paid_confirmed_mxn"] != 794:
        fail("September paid-confirmed baseline must remain MXN 794")
    if snapshot["monthly"]["2026-09"]["spend"]["reference_mxn"] != 1389:
        fail("September reference baseline must remain MXN 1389")
    if snapshot["monthly"]["2026-10"]["spend"]["paid_confirmed_mxn"] != 0:
        fail("October paid-confirmed baseline must remain MXN 0")
    if snapshot["monthly"]["2026-10"]["spend"]["reference_mxn"] != 1665:
        fail("October reference baseline must remain MXN 1665")

    # Evidence detail must reconcile with canonical workload files.
    workloads = list(verification_workloads.get("workloads", []) or []) + list(media_workloads.get("workloads", []) or [])
    canonical_workload_ids = sorted(x["id"] for x in workloads)
    projected_workload_ids = sorted(x["id"] for x in snapshot["evidence"].get("workloads", []))
    if projected_workload_ids != canonical_workload_ids:
        fail("detailed workload projection drift")
    if len(projected_workload_ids) != 26:
        fail(f"expected 26 canonical verification/media workloads, got {len(projected_workload_ids)}")

    candidate_ids = [x["subject_id"] for x in qualification.get("candidates", []) or []]
    projected_candidate_ids = [x["subject_id"] for x in snapshot["evidence"].get("executor_candidates", [])]
    if projected_candidate_ids != candidate_ids:
        fail("executor qualification projection drift")

    need_index = {x["capacity_resource_id"]: x for x in need_rows}
    for row in snapshot["capacity"]["resources"]:
        source = need_index[row["capacity_resource_id"]]
        if row.get("completed_cycles_observed") != int(source.get("completed_cycles_observed", 0) or 0):
            fail(f"completed-cycle projection drift for {row['capacity_resource_id']}")
        if row.get("blocked_workloads") != int(source.get("blocked_workloads", 0) or 0):
            fail(f"blocked-workload projection drift for {row['capacity_resource_id']}")
        if row.get("workaround_minutes") != int(source.get("workaround_minutes", 0) or 0):
            fail(f"workaround projection drift for {row['capacity_resource_id']}")

    # UNKNOWN must exist for catalog identities without evaluation rows.
    if snapshot["overview"]["counts"].get("unknown", 0) <= 0:
        fail("expected UNKNOWN registry states for identities without evaluation rows")

    # Runway durable trigger.
    resources = {x["capacity_resource_id"]: x for x in snapshot["capacity"]["resources"]}
    runway = resources.get("runway-free-video")
    if not runway:
        fail("missing runway-free-video capacity resource")
    if runway["events"].get("PLAN_FEATURE_BLOCKED") != 1:
        fail("Runway feature block lost")
    if runway["scaling_status"] != "WATCH":
        fail("Runway scaling status must be WATCH")
    if runway["reroute_result"] != "EXISTING_ENTITLEMENTS_AVAILABLE":
        fail("Runway reroute result drift")

    # Canonical need/scaling keys must remain aligned.
    need_rows = needs.get("capacity_watch", needs.get("capacity_resources", needs.get("resources", []))) or []
    scale_rows = scaling.get("decisions", scaling.get("resources", [])) or []
    need_ids = {x["capacity_resource_id"] for x in need_rows}
    scale_ids = {x["capacity_resource_id"] for x in scale_rows}
    if need_ids != scale_ids:
        fail("canonical capacity/scaling key mismatch")
    if len(snapshot["capacity"]["resources"]) != len(need_ids):
        fail("snapshot capacity resource count mismatch")
    if len(capacity["capacity_resources"]) != len(need_ids):
        fail("Capacity Router resource count mismatch")

    # Noema boundary.
    if noema.get("executors", []) != []:
        fail("current Noema projection expected empty")
    if snapshot["evidence"]["executor_projection"]["published_count"] != 0:
        fail("snapshot falsely reports published executor")

    # Stable Capacity Router boundary.
    forbidden = {"live_remaining_credits", "live_reset_countdown", "secrets", "runtime_availability"}
    def walk(v):
        if isinstance(v, dict):
            if forbidden.intersection(v):
                fail(f"forbidden volatile Capacity Router field: {sorted(forbidden.intersection(v))}")
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(capacity)

    # Bundle double-counting: exactly one paid row per month plan.
    if len(snap_paid) != len(set(snap_paid)):
        fail("duplicate paid-plan row")

    print(json.dumps({
        "status": "PASS",
        "month": a.month,
        "registry_items": snapshot["overview"]["counts"]["registry_items"],
        "tools": tool_count,
        "integrations": integration_count,
        "actions": len(snapshot["actions"]),
        "capacity_resources": len(snapshot["capacity"]["resources"]),
        "paid_rows": len(snapshot["budget"]["paid_plans"]),
        "unknown_registry_states": snapshot["overview"]["counts"]["unknown"],
    }, indent=2))


if __name__ == "__main__":
    main()
