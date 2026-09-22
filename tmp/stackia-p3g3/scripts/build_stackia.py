#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

KIND_RANK = {
    "TOOL": 0, "SERVICE": 0, "LIBRARY": 0,
    "SKILL": 1, "MCP": 2, "PLUGIN_CONNECTOR": 3,
}
PRIORITY_RANK = {"CORE": 0, "NOW": 1, "NEXT": 2, "LATER": 3, "TRIGGER": 4, "NONE": 5, "UNKNOWN": 6}


def load_yaml(rel: str):
    with open(ROOT / rel, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_json(rel: str):
    with open(ROOT / rel, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def git_value(*args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def normalize_timestamp(value: str | None) -> str:
    if not value:
        value = git_value("show", "-s", "--format=%cI", "HEAD")
    if not value:
        raise SystemExit("source timestamp required for deterministic output")
    value = str(value).strip()
    if value.isdigit():
        dt = datetime.fromtimestamp(int(value), tz=timezone.utc)
    else:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def flatten_evaluations(doc):
    out = []
    for key, value in doc.items():
        if key.endswith("_evaluations") and isinstance(value, list):
            out.extend(value)
    return out


def flatten_integrations(doc):
    out = []
    for key in ("skills", "mcps", "plugins_connectors"):
        out.extend(doc.get(key, []) or [])
    return out


def assert_unique(items, key_fn, label):
    seen = set()
    dup = set()
    for item in items:
        key = key_fn(item)
        if key in seen:
            dup.add(key)
        seen.add(key)
    if dup:
        raise SystemExit(f"duplicate {label}: {sorted(dup)}")


def compile_snapshot(month: str, source_commit: str, source_timestamp: str, source_ref: str):
    tools_doc = load_yaml("catalog/tools.yaml")
    ints_doc = load_yaml("catalog/integrations.yaml")
    alt_doc = load_yaml("catalog/alternatives.yaml")
    eval_doc = load_yaml("state/evaluations.yaml")
    dep_doc = load_yaml("state/deployments.yaml")
    subs_doc = load_yaml("state/subscriptions.yaml")
    month_doc = load_yaml(f"state/months/{month}.yaml")
    month_index_doc = load_yaml("state/months/index.yaml")
    needs_doc = load_yaml(f"state/needs/{month}.yaml")
    scaling_doc = load_yaml(f"state/scaling/{month}.yaml")
    media_doc = load_yaml("state/media-factory.yaml")
    qual_doc = load_yaml("state/executor-qualification.yaml")
    noema_doc = load_yaml("exports/noema/executors.yaml")
    scenario_doc = load_json(f"ui/derived/scenarios/{month}.proposal.json")
    verification_workloads = load_yaml("validation/verification-workloads.yaml")
    media_workloads = load_yaml("validation/media-factory-workloads.yaml")

    tools = tools_doc.get("tools", [])
    integrations = flatten_integrations(ints_doc)
    evaluations = flatten_evaluations(eval_doc)
    deployments = dep_doc.get("deployments", []) or []
    subscriptions = subs_doc.get("subscriptions", []) or []

    assert_unique(tools, lambda x: x["id"], "tool id")
    assert_unique(integrations, lambda x: x["id"], "integration id")
    assert_unique(evaluations, lambda x: x["subject_id"], "evaluation subject")
    assert_unique(deployments, lambda x: (x["subject_id"], x["host"]), "deployment subject+host")

    tool_by_id = {x["id"]: x for x in tools}
    int_by_id = {x["id"]: x for x in integrations}
    all_ids = set(tool_by_id) | set(int_by_id)
    eval_by_id = {x["subject_id"]: x for x in evaluations}
    dep_by_subject = defaultdict(list)
    for row in deployments:
        dep_by_subject[row["subject_id"]].append(row)
    sub_by_id = {x["id"]: x for x in subscriptions}

    # Reference integrity.
    for row in evaluations:
        if row["subject_id"] not in all_ids:
            raise SystemExit(f"broken evaluation ref: {row['subject_id']}")
    for row in deployments:
        if row["subject_id"] not in all_ids:
            raise SystemExit(f"broken deployment ref: {row['subject_id']}")

    # Alternative reverse index.
    alternatives = defaultdict(list)
    for group in alt_doc.get("groups", []) or []:
        for member in group.get("members", []) or []:
            if member not in tool_by_id:
                raise SystemExit(f"broken alternative member: {member}")
            alternatives[member].append(group["id"])

    # Subscription relations.
    plan_rel = defaultdict(list)
    for sub in subscriptions:
        for tid in sub.get("covers_tools", []) or []:
            if tid not in tool_by_id:
                raise SystemExit(f"broken subscription tool ref: {tid}")
            plan_rel[tid].append(sub["id"])

    # Budget + monthly comparison context.
    def compile_paid_rows(month_state):
        rows = []
        for row in month_state["budget"]["paid_plans"]:
            sid = row["subscription_id"]
            if sid not in sub_by_id:
                raise SystemExit(f"broken month subscription ref: {sid}")
            sub = sub_by_id[sid]
            billing = sub.get("billing", {})
            native_currency = billing.get("currency", "UNKNOWN")
            native_amount = billing.get("amount")
            native_certainty = billing.get("certainty", "UNKNOWN")

            ref_mxn = None
            ref_certainty = "UNKNOWN"
            if row.get("confirmed_mxn") is not None:
                ref_mxn = row["confirmed_mxn"]
                ref_certainty = "CONFIRMED"
            elif row.get("reference_mxn") is not None:
                ref_mxn = row["reference_mxn"]
                ref_certainty = "REFERENCE_ESTIMATE"
            elif native_currency == "MXN" and native_amount is not None:
                ref_mxn = native_amount
                ref_certainty = native_certainty
            elif billing.get("reference_mxn") is not None:
                ref_mxn = billing["reference_mxn"]
                ref_certainty = billing.get("reference_certainty", "REFERENCE_ESTIMATE")

            rows.append({
                "subscription_id": sid,
                "provider": sub["provider"],
                "plan_name": sub["plan_name"],
                "payment_state": row["payment_state"],
                "subscription_state": sub["subscription_state"],
                "billing_period": sub.get("billing_period", "UNKNOWN"),
                "amount": {
                    "currency": native_currency,
                    "native_amount": native_amount,
                    "native_certainty": native_certainty,
                    "reference_mxn": ref_mxn,
                    "reference_mxn_certainty": ref_certainty,
                },
                "covers_tools": list(sub.get("covers_tools", []) or []),
                "includes_capabilities": list(sub.get("includes_capabilities", []) or []),
            })
        return rows

    def compile_month_state(month_state):
        paid = compile_paid_rows(month_state)
        entitlements = list((month_state.get("entitlements", {}) or {}).get("zero_monthly_cash_out", []) or [])
        exiting = [
            x["subscription_id"] if isinstance(x, dict) else x
            for x in ((month_state.get("entitlements", {}) or {}).get("exiting", []) or [])
        ]
        known_exact = sum((r.get("confirmed_mxn") or 0) for r in month_state["budget"]["paid_plans"])
        paid_confirmed = sum(
            (r.get("confirmed_mxn") or 0)
            for r in month_state["budget"]["paid_plans"]
            if r.get("payment_state") in ("PAID", "CHARGED", "SETTLED")
        )
        reference_total = (month_state["budget"].get("totals", {}) or {}).get("reference_active_stack_mxn_excluding_capcut")
        unresolved = list((month_state.get("budget", {}).get("totals", {}) or {}).get("unresolved_items", []) or [])
        reference_excludes = ["capcut-pro"] if reference_total is not None and "capcut-pro" in unresolved else []
        active_tools = {str(k): list(v or []) for k, v in (month_state.get("active_tools", {}) or {}).items()}
        targets = month_state.get("integration_targets", {}) or {}
        return {
            "paid_plans": paid,
            "entitlements": entitlements,
            "exiting": exiting,
            "active_tools": active_tools,
            "included_capabilities_to_use": list(month_state.get("included_capabilities_to_use", []) or []),
            "integration_targets": {
                "skills": list(targets.get("skills", []) or []),
                "mcps": list(targets.get("mcps", []) or []),
            },
            "agent_lab": list(month_state.get("agent_lab", []) or []),
            "spend": {
                "known_exact_mxn": known_exact,
                "paid_confirmed_mxn": paid_confirmed,
                "reference_mxn": reference_total,
                "reference_excludes": reference_excludes,
                "unresolved_subscription_ids": unresolved,
            },
        }

    paid_rows = compile_paid_rows(month_doc)
    entitlement_rows = list((month_doc.get("entitlements", {}) or {}).get("zero_monthly_cash_out", []) or [])
    exiting_rows = [
        x["subscription_id"] if isinstance(x, dict) else x
        for x in ((month_doc.get("entitlements", {}) or {}).get("exiting", []) or [])
    ]

    available_months = []
    monthly_states = {}
    for month_meta in month_index_doc.get("months", []) or []:
        mid = month_meta["month"]
        mdoc = load_yaml(month_meta["path"])
        available_months.append(mid)
        monthly_states[mid] = compile_month_state(mdoc)

    # Unified registry.
    registry = []
    for item in tools + integrations:
        iid = item["id"]
        ev = eval_by_id.get(iid)
        if ev:
            state = {
                "usage": ev.get("usage", "UNKNOWN"),
                "verification": ev.get("verification", "UNKNOWN"),
                "decision": ev.get("decision", "UNKNOWN"),
                "priority": ev.get("priority", "NONE" if ev.get("decision") == "DROP" else "UNKNOWN"),
            }
        else:
            state = {"usage": "UNKNOWN", "verification": "UNKNOWN", "decision": "UNKNOWN", "priority": "UNKNOWN"}

        related_tool = item.get("related_tool")
        provider = item.get("provider")
        if not provider and related_tool in tool_by_id:
            provider = tool_by_id[related_tool].get("provider")

        inherited_plan_rel = list(plan_rel.get(iid, []))
        if not inherited_plan_rel and related_tool:
            inherited_plan_rel = list(plan_rel.get(related_tool, []))

        registry.append({
            "id": iid,
            "name": item["name"],
            "kind": item["kind"],
            "category": item["category"],
            "provider": provider,
            "description": item.get("description", ""),
            "related_tool": related_tool,
            "packaged_host": item.get("host"),
            "surfaces": list(item.get("surfaces", []) or []),
            "state": state,
            "deployments": [
                {"host": d["host"], "state": d["state"]}
                for d in sorted(dep_by_subject.get(iid, []), key=lambda x: (x["host"], x["state"]))
            ],
            "alternative_groups": sorted(alternatives.get(iid, [])),
            "plan_relations": sorted(inherited_plan_rel),
        })

    registry.sort(key=lambda x: (
        KIND_RANK.get(x["kind"], 9),
        x["category"],
        x["name"].casefold(),
        x["id"],
    ))

    # Host matrix: integrations only.
    hosts = list(dep_doc.get("hosts", []) or [])
    for integ in integrations:
        h = integ.get("host")
        if h and h != "MULTI_HOST" and h not in hosts:
            hosts.append(h)
    matrix = []
    for integ in integrations:
        ev = eval_by_id.get(integ["id"])
        cells = {}
        dep_index = {d["host"]: d["state"] for d in dep_by_subject.get(integ["id"], [])}
        for host in hosts:
            cells[host] = dep_index.get(host, "UNKNOWN")
        matrix.append({
            "subject_id": integ["id"],
            "kind": integ["kind"],
            "verification": ev.get("verification", "UNKNOWN") if ev else "UNKNOWN",
            "cells": cells,
        })
    matrix.sort(key=lambda x: (KIND_RANK.get(x["kind"], 9), x["subject_id"]))

    # Workloads.
    workloads = []
    for doc in (verification_workloads, media_workloads):
        workloads.extend(doc.get("workloads", []) or [])
    assert_unique(workloads, lambda x: x["id"], "workload id")
    workload_text = defaultdict(list)
    stage_workload_ids = defaultdict(list)
    workload_rows = []
    for w in workloads:
        ids = []
        if w.get("subject_id"):
            ids.append(w["subject_id"])
        ids.extend(w.get("subject_group", []) or [])
        ids.extend(w.get("subjects", []) or [])
        ids.extend(w.get("related_subjects", []) or [])
        ids.extend(w.get("integration_ids", []) or [])
        ids.extend(w.get("skill_ids", []) or [])
        ids = sorted(set(ids))
        for sid in ids:
            workload_text[sid].append(w["id"])
        if w.get("stage"):
            stage_workload_ids[w["stage"]].append(w["id"])
        workload_rows.append({
            "id": w["id"],
            "subjects": ids,
            "stage": w.get("stage"),
            "category": w.get("category"),
            "target_level": w.get("target_level"),
            "result": w.get("result", "UNKNOWN"),
            "objective": w.get("objective", ""),
            "blocker": w.get("blocker"),
        })
    workload_rows.sort(key=lambda x: x["id"])

    # Action ledger.
    actions = []
    def add_action(rank, subject_id, action_type, priority, reason_codes, human_required, refs):
        actions.append({
            "id": f"{subject_id}:{action_type}:{reason_codes[0]}",
            "rank": rank,
            "subject_id": subject_id,
            "action_type": action_type,
            "priority": priority,
            "reason_codes": reason_codes,
            "human_required": human_required,
            "source_refs": refs,
        })

    for ev in evaluations:
        sid = ev["subject_id"]
        priority = ev.get("priority", "NONE")
        verification = ev.get("verification", "UNKNOWN")
        if priority == "CORE" and verification not in ("TESTED", "VERIFIED"):
            refs = ["state/evaluations.yaml"]
            if sid in workload_text:
                refs.append(f"workloads:{','.join(sorted(workload_text[sid]))}")
            add_action(10, sid, "VERIFY", priority, ["CORE_VERIFICATION_GAP"], True, refs)

    skill_targets = set((month_doc.get("integration_targets", {}) or {}).get("skills", []) or [])
    mcp_targets = set((month_doc.get("integration_targets", {}) or {}).get("mcps", []) or [])
    integration_targets = skill_targets | mcp_targets
    for sid in sorted(integration_targets):
        if sid not in int_by_id:
            raise SystemExit(f"broken integration target: {sid}")
        ev = eval_by_id.get(sid)
        priority = ev.get("priority", "UNKNOWN") if ev else "UNKNOWN"
        explicit_not = [d for d in dep_by_subject.get(sid, []) if d["state"] == "NOT_DEPLOYED"]
        if priority == "NOW" and explicit_not:
            add_action(20, sid, "DEPLOY", priority, ["EXPLICIT_NOT_DEPLOYED", "MONTHLY_INTEGRATION_TARGET"], True, ["state/deployments.yaml", f"state/months/{month}.yaml"])

    for ev in evaluations:
        sid = ev["subject_id"]
        priority = ev.get("priority", "NONE")
        verification = ev.get("verification", "UNKNOWN")
        if priority == "NOW" and verification in ("UNKNOWN", "UNVERIFIED"):
            refs = ["state/evaluations.yaml"]
            if sid in workload_text:
                refs.append(f"workloads:{','.join(sorted(workload_text[sid]))}")
            add_action(30, sid, "TEST", priority, ["NOW_VERIFICATION_GAP"], True, refs)

    # Capacity + scaling.
    need_rows = needs_doc.get("capacity_watch", needs_doc.get("capacity_resources", needs_doc.get("resources", []))) or []
    scale_rows = scaling_doc.get("decisions", scaling_doc.get("resources", [])) or []
    need_by_id = {x["capacity_resource_id"]: x for x in need_rows}
    scale_by_id = {x["capacity_resource_id"]: x for x in scale_rows}
    if set(need_by_id) != set(scale_by_id):
        raise SystemExit(f"capacity/scaling mismatch: needs={sorted(need_by_id)} scaling={sorted(scale_by_id)}")

    capacity_rows = []
    for cid in sorted(need_by_id):
        n = need_by_id[cid]
        s = scale_by_id[cid]
        events = dict(n.get("events", {}) or {})
        status = s.get("status", "UNASSESSED")
        capacity_rows.append({
            "capacity_resource_id": cid,
            "plan_ref": n.get("plan_ref"),
            "subjects": list(n.get("subjects", []) or []),
            "events": events,
            "completed_cycles_observed": int(n.get("completed_cycles_observed", 0) or 0),
            "blocked_workloads": int(n.get("blocked_workloads", 0) or 0),
            "workaround_minutes": int(n.get("workaround_minutes", 0) or 0),
            "depletion_class": n.get("depletion_class", "UNKNOWN"),
            "scaling_status": status,
            "reroute_result": s.get("reroute_result", "NOT_RUN"),
            "economic_gate": s.get("economic_gate", "UNASSESSED"),
            "next_action": s.get("next_action", "OBSERVE"),
        })
        if any(int(v or 0) > 0 for v in events.values()) or status != "UNASSESSED":
            subject = (n.get("subjects") or [cid])[0]
            action_type = "BENCHMARK" if "BENCHMARK" in str(s.get("next_action", "")) else "CAPACITY_REVIEW"
            add_action(40, subject, action_type, eval_by_id.get(subject, {}).get("priority", "NONE"), ["ACTIVE_CAPACITY_OR_SCALING_SIGNAL"], False, [f"state/needs/{month}.yaml", f"state/scaling/{month}.yaml"])

    # Billing fact actions.
    unresolved = list((month_doc.get("budget", {}).get("totals", {}) or {}).get("unresolved_items", []) or [])
    for sid in unresolved:
        sub = sub_by_id[sid]
        subjects = sub.get("covers_tools", []) or [sid]
        for subject in subjects:
            add_action(50, subject, "RESOLVE_ACCOUNT_FACT", eval_by_id.get(subject, {}).get("priority", "NONE"), ["UNRESOLVED_SUBSCRIPTION_FACT"], True, ["state/subscriptions.yaml", f"state/months/{month}.yaml"])

    for ev in evaluations:
        if ev.get("priority") == "NEXT":
            add_action(60, ev["subject_id"], "TEST", "NEXT", ["NEXT_PRIORITY"], True, ["state/evaluations.yaml"])

    # Stable action dedupe/order.
    dedup = {}
    for a in actions:
        key = (a["subject_id"], a["action_type"], a["reason_codes"][0])
        dedup[key] = a
    actions = sorted(dedup.values(), key=lambda x: (x["rank"], PRIORITY_RANK.get(x["priority"], 9), x["subject_id"], x["action_type"]))

    # Media Factory.
    stage_result = defaultdict(list)
    for w in media_workloads.get("workloads", []) or []:
        stage = w.get("stage")
        if stage:
            stage_result[stage].append(w.get("result", "PENDING"))
    human_by_after = defaultdict(list)
    for gate in media_doc.get("human_gates", []) or []:
        target_stage = gate.get("after_stage") or gate.get("before_stage")
        if target_stage:
            human_by_after[target_stage].append(gate["id"])

    def stage_subjects(entries):
        out = []
        for e in entries or []:
            if isinstance(e, dict) and e.get("subject_id"):
                out.append(e["subject_id"])
        return out

    def stage_verification(stage_id):
        results = stage_result.get(stage_id, [])
        good = any(r in ("PASS", "SATISFIED_BY_EXISTING_EVIDENCE") for r in results)
        pending = any(r in ("PENDING", "PARTIAL") for r in results)
        if good and pending:
            return "MIXED"
        if good:
            return "VERIFIED"
        if results and not pending:
            return "TESTED"
        if pending:
            return "UNVERIFIED"
        return "UNVERIFIED"

    media_stages = []
    for stage in media_doc.get("stages", []) or []:
        sid = stage["id"]
        media_stages.append({
            "id": sid,
            "order": stage["order"],
            "primary_subjects": stage_subjects(stage.get("primary")),
            "fallback_subjects": stage_subjects(stage.get("fallbacks")),
            "verification_state": stage_verification(sid),
            "human_gate_ids": sorted(human_by_after.get(sid, [])),
            "workload_ids": sorted(stage_workload_ids.get(sid, [])),
        })

    # Scenarios.
    scenarios = scenario_doc["scenarios"]

    # Evidence summary.
    result_counts = Counter(w.get("result", "UNKNOWN") for w in workloads)
    eligible = list((qual_doc.get("stable_projection", {}) or {}).get("eligible_now", []) or [])
    executor_candidates = []
    for row in qual_doc.get("candidates", []) or []:
        executor_candidates.append({
            "subject_id": row["subject_id"],
            "intended_capabilities": list(row.get("intended_capabilities", []) or []),
            "intended_interfaces": list(row.get("intended_interfaces", []) or []),
            "qualification": row.get("qualification", "UNKNOWN"),
            "workload_ref": row.get("workload_ref"),
            "reason": row.get("reason"),
        })
    published = len(noema_doc.get("executors", []) or [])

    # Overview.
    verification_counts = Counter(x["state"]["verification"] for x in registry)
    known_exact = sum((r.get("confirmed_mxn") or 0) for r in month_doc["budget"]["paid_plans"])
    paid_confirmed = sum(
        (r.get("confirmed_mxn") or 0)
        for r in month_doc["budget"]["paid_plans"]
        if r.get("payment_state") in ("PAID", "CHARGED", "SETTLED")
    )
    reference_total = (month_doc["budget"].get("totals", {}) or {}).get("reference_active_stack_mxn_excluding_capcut")
    reference_excludes = ["capcut-pro"] if reference_total is not None and "capcut-pro" in unresolved else []

    event_totals = Counter()
    scale_counts = Counter()
    for row in capacity_rows:
        for k, v in row["events"].items():
            event_totals[k] += int(v or 0)
        scale_counts[row["scaling_status"]] += 1

    snapshot = {
        "schema": "stackia/ui-snapshot@1",
        "meta": {
            "generated_at": source_timestamp,
            "source_repo": "Picazo333/stack-ia",
            "source_ref": source_ref,
            "source_commit": source_commit,
            "derived_only": True,
        },
        "selection": {"month": month, "scenario": "ACTUAL", "available_months": available_months},
        "overview": {
            "counts": {
                "registry_items": len(registry),
                "verified": verification_counts["VERIFIED"],
                "tested": verification_counts["TESTED"],
                "unverified": verification_counts["UNVERIFIED"],
                "unknown": verification_counts["UNKNOWN"],
                "deployments": len(deployments),
                "pending_actions": len(actions),
            },
            "spend": {
                "known_exact_mxn": known_exact,
                "paid_confirmed_mxn": paid_confirmed,
                "reference_mxn": reference_total,
                "reference_excludes": reference_excludes,
                "unresolved_subscription_ids": unresolved,
            },
            "signals": {
                "capacity_events": dict(sorted(event_totals.items())),
                "scaling_status_counts": dict(sorted(scale_counts.items())),
            },
        },
        "budget": {
            "paid_plans": paid_rows,
            "entitlements": entitlement_rows,
            "exiting": exiting_rows,
        },
        "monthly": monthly_states,
        "registry": {"items": registry},
        "integrations": {"hosts": hosts, "matrix": matrix},
        "actions": actions,
        "capacity": {"resources": capacity_rows},
        "media_factory": {
            "stages": sorted(media_stages, key=lambda x: (x["order"], x["id"])),
            "human_gates": [x["id"] for x in media_doc.get("human_gates", []) or []],
        },
        "scenarios": scenarios,
        "evidence": {
            "workload_summary": dict(sorted(result_counts.items())),
            "executor_projection": {"eligible_now": eligible, "published_count": published},
            "executor_candidates": executor_candidates,
            "workloads": workload_rows,
        },
    }

    Draft202012Validator(load_json("schemas/ui-snapshot/v1.schema.json")).validate(snapshot)
    return snapshot


def compile_capacity_seed(month: str, source_commit: str):
    subs_doc = load_yaml("state/subscriptions.yaml")
    month_doc = load_yaml(f"state/months/{month}.yaml")
    needs_doc = load_yaml(f"state/needs/{month}.yaml")
    scaling_doc = load_yaml(f"state/scaling/{month}.yaml")

    sub_by_id = {x["id"]: x for x in subs_doc.get("subscriptions", []) or []}
    plan_ids = []
    for row in month_doc["budget"]["paid_plans"]:
        plan_ids.append(row["subscription_id"])
    for row in (month_doc.get("entitlements", {}) or {}).get("zero_monthly_cash_out", []) or []:
        plan_ids.append(row["subscription_id"])

    plans = []
    for sid in plan_ids:
        sub = sub_by_id[sid]
        billing = sub.get("billing", {})
        currency = billing.get("currency", "UNKNOWN")
        amount = billing.get("amount")
        native_certainty = billing.get("certainty", "UNKNOWN")
        ref_mxn = amount if currency == "MXN" else billing.get("reference_mxn")
        ref_certainty = native_certainty if currency == "MXN" else billing.get("reference_certainty", "REFERENCE_ESTIMATE" if ref_mxn is not None else "UNKNOWN")
        plans.append({
            "subscription_id": sid,
            "subscription_state": sub["subscription_state"],
            "billing": {
                "currency": currency,
                "native_amount": amount,
                "native_certainty": native_certainty,
                "reference_mxn": ref_mxn,
                "reference_mxn_certainty": ref_certainty,
            },
            "covered_subjects": list(sub.get("covers_tools", []) or []),
        })

    need_rows = needs_doc.get("capacity_watch", needs_doc.get("capacity_resources", needs_doc.get("resources", []))) or []
    scale_rows = scaling_doc.get("decisions", scaling_doc.get("resources", [])) or []
    scale_by_id = {x["capacity_resource_id"]: x for x in scale_rows}
    resources = []
    for n in sorted(need_rows, key=lambda x: x["capacity_resource_id"]):
        cid = n["capacity_resource_id"]
        s = scale_by_id[cid]
        resources.append({
            "capacity_resource_id": cid,
            "plan_ref": n.get("plan_ref"),
            "subjects": list(n.get("subjects", []) or []),
            "integrations": list(n.get("integrations", []) or []),
            "durable_events": dict(n.get("events", {}) or {}),
            "depletion_class": n.get("depletion_class", "UNKNOWN"),
            "scaling_status": s.get("status", "UNASSESSED"),
            "reroute_result": s.get("reroute_result", "NOT_RUN"),
            "economic_gate": s.get("economic_gate", "UNASSESSED"),
            "next_action": s.get("next_action", "OBSERVE"),
        })

    seed = {
        "schema": "stackia/capacity-router-seed@1",
        "meta": {"derived_only": True, "source_repo": "Picazo333/stack-ia", "source_commit": source_commit},
        "month": month,
        "plans": plans,
        "capacity_resources": resources,
    }
    Draft202012Validator(load_json("schemas/capacity-router/v1.schema.json")).validate(seed)
    return seed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", required=True)
    parser.add_argument("--source-commit")
    parser.add_argument("--source-timestamp")
    parser.add_argument("--source-ref")
    parser.add_argument("--snapshot-out", required=True)
    parser.add_argument("--capacity-out", required=True)
    args = parser.parse_args()

    source_commit = args.source_commit or git_value("rev-parse", "HEAD")
    if not source_commit:
        raise SystemExit("source commit required")
    source_timestamp = normalize_timestamp(args.source_timestamp)
    source_ref = args.source_ref or git_value("rev-parse", "--abbrev-ref", "HEAD") or "unknown"

    snapshot = compile_snapshot(args.month, source_commit, source_timestamp, source_ref)
    capacity = compile_capacity_seed(args.month, source_commit)

    write_json(Path(args.snapshot_out), snapshot)
    write_json(Path(args.capacity_out), capacity)


if __name__ == "__main__":
    main()
