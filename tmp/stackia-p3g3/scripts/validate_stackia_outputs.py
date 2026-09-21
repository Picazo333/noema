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
    evaluations = y("state/evaluations.yaml")
    deployments = y("state/deployments.yaml")
    needs = y(f"state/needs/{a.month}.yaml")
    scaling = y(f"state/scaling/{a.month}.yaml")
    noema = y("exports/noema/executors.yaml")
    scenario = j(f"ui/derived/scenarios/{a.month}.proposal.json")

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
    if counts != {"VERIFIED": 4, "TESTED": 6, "UNVERIFIED": 82}:
        fail(f"evaluation baseline changed unexpectedly: {counts}")

    if len(deployments.get("deployments", [])) != 20:
        fail("explicit deployment baseline must be 20")

    # Full registry must include every tool + integration.
    tool_count = len(y("catalog/tools.yaml").get("tools", []))
    ints_doc = y("catalog/integrations.yaml")
    integration_count = sum(len(ints_doc.get(k, []) or []) for k in ("skills", "mcps", "plugins_connectors"))
    expected_registry = tool_count + integration_count
    if snapshot["overview"]["counts"]["registry_items"] != expected_registry:
        fail(f"registry count {snapshot['overview']['counts']['registry_items']} != {expected_registry}")

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
