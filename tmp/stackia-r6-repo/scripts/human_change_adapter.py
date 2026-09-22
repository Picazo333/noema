#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from ruamel.yaml import YAML


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MONTH = "2026-10"


class CommandBlocked(Exception):
    pass


class StackIAChangeAdapter:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root).resolve()
        self.yaml = YAML()
        self.yaml.preserve_quotes = True
        self.yaml.width = 1000
        self.schema = self._load_json("schemas/change-set/v1.schema.json")
        self.transitions = self._load_yaml("commands/transitions.yaml")
        self.identities = self._build_identity_index()
        self.subscriptions = self._subscription_index()
        self.workloads = self._build_workload_index()

    def _path(self, rel: str) -> Path:
        return self.root / rel

    def _load_json(self, rel: str) -> Any:
        return json.loads(self._path(rel).read_text(encoding="utf-8"))

    def _load_yaml(self, rel: str) -> Any:
        return self.yaml.load(self._path(rel).read_text(encoding="utf-8"))

    def _dump_yaml(self, doc: Any) -> str:
        buf = io.StringIO()
        self.yaml.dump(doc, buf)
        text = buf.getvalue()
        return text if text.endswith("\n") else text + "\n"

    def _build_identity_index(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        tools = self._load_yaml("catalog/tools.yaml").get("tools", []) or []
        for row in tools:
            out[row["id"]] = {
                "id": row["id"],
                "kind": row["kind"],
                "class": "TOOL",
                "evaluation_collection": "tool_evaluations",
            }
        ints = self._load_yaml("catalog/integrations.yaml")
        mapping = {
            "skills": ("SKILL", "skill_evaluations"),
            "mcps": ("MCP", "mcp_evaluations"),
            "plugins_connectors": ("PLUGIN", "plugin_connector_evaluations"),
        }
        for key, (cls, collection) in mapping.items():
            for row in ints.get(key, []) or []:
                out[row["id"]] = {
                    "id": row["id"],
                    "kind": row["kind"],
                    "class": cls,
                    "evaluation_collection": collection,
                }
        return out

    def _subscription_index(self) -> dict[str, dict[str, Any]]:
        doc = self._load_yaml("state/subscriptions.yaml")
        return {x["id"]: x for x in doc.get("subscriptions", []) or []}

    def _build_workload_index(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for rel in ("validation/verification-workloads.yaml", "validation/media-factory-workloads.yaml"):
            doc = self._load_yaml(rel)
            for row in doc.get("workloads", []) or []:
                ids: list[str] = []
                for key in ("subject_id",):
                    if row.get(key):
                        ids.append(row[key])
                for key in ("subject_group", "subjects", "related_subjects", "integration_ids", "skill_ids"):
                    ids.extend(row.get(key, []) or [])
                clone = copy.deepcopy(row)
                clone["_subjects"] = sorted(set(ids))
                clone["_source"] = rel
                out[row["id"]] = clone
        return out

    def _validate_envelope(self, change_set: dict[str, Any]) -> None:
        validator = Draft202012Validator(self.schema, format_checker=FormatChecker())
        errors = sorted(validator.iter_errors(change_set), key=lambda e: list(e.path))
        if errors:
            msg = "; ".join(f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors)
            raise CommandBlocked(f"change-set schema invalid: {msg}")
        if change_set["status"] not in ("DRAFT", "PREVIEW_VALID"):
            raise CommandBlocked("incoming change-set status must be DRAFT or PREVIEW_VALID")

    def _subject_identity(self, subject: dict[str, str]) -> dict[str, Any]:
        sid = subject["id"]
        cls = subject["class"]
        if cls == "PLAN":
            if sid not in self.subscriptions:
                raise CommandBlocked(f"unknown PLAN subject: {sid}")
            return {"id": sid, "class": "PLAN", "kind": "PLAN", "evaluation_collection": None}
        item = self.identities.get(sid)
        if not item:
            raise CommandBlocked(f"unknown inventory subject: {sid}")
        if item["class"] != cls:
            raise CommandBlocked(f"subject class mismatch for {sid}: {cls} != {item['class']}")
        return item

    def _load_docs(self, change_set: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        rels = {
            "state/evaluations.yaml",
            "state/deployments.yaml",
            "state/verification-evidence.yaml",
            "state/subscriptions.yaml",
            "state/months/index.yaml",
            "state/human-change-log.yaml",
        }
        for op in change_set["operations"]:
            if op["command"] == "RESOLVE_ACCOUNT_FACT":
                rels.add(f"state/months/{op['payload']['month']}.yaml")
                # Subscription billing facts can affect any indexed month that references the plan.
                if op["payload"]["field"].startswith("billing_") or op["payload"]["field"] == "subscription_state":
                    idx = self._load_yaml("state/months/index.yaml")
                    for meta in idx.get("months", []) or []:
                        rels.add(meta["path"])
        docs, originals = {}, {}
        for rel in sorted(rels):
            path = self._path(rel)
            if rel == "state/human-change-log.yaml" and not path.exists():
                docs[rel] = {"schema": "stackia/human-change-log@0.1", "status": "canonical", "entries": []}
                originals[rel] = ""
            else:
                originals[rel] = path.read_text(encoding="utf-8")
                docs[rel] = self.yaml.load(originals[rel])
        return docs, originals

    def _eval_row(self, docs: dict[str, Any], identity: dict[str, Any], create: bool = False) -> dict[str, Any] | None:
        doc = docs["state/evaluations.yaml"]
        collection = identity["evaluation_collection"]
        rows = doc.setdefault(collection, [])
        for row in rows:
            if row.get("subject_id") == identity["id"]:
                return row
        if not create:
            return None
        row = {"subject_id": identity["id"]}
        rows.append(row)
        return row

    def _audit_ref(self, change_set_id: str) -> str:
        return f"state/human-change-log.yaml#{change_set_id}"

    @staticmethod
    def _append_unique(row: dict[str, Any], key: str, value: Any) -> None:
        seq = row.setdefault(key, [])
        if value not in seq:
            seq.append(value)

    @staticmethod
    def _matches_expected(before: dict[str, Any], expected: dict[str, Any] | None) -> None:
        if not expected:
            return
        for key, value in expected.items():
            if before.get(key) != value:
                raise CommandBlocked(
                    f"expected_before conflict for {key}: expected {value!r}, current {before.get(key)!r}"
                )

    def _check_command_class(self, command: str, cls: str) -> None:
        spec = (self.transitions.get("commands", {}) or {}).get(command)
        if not spec:
            raise CommandBlocked(f"unknown command: {command}")
        allowed = list(spec.get("classes", []) or [])
        if cls not in allowed:
            raise CommandBlocked(f"{command} is not allowed for class {cls}")

    def _apply_eval_axis(
        self,
        docs: dict[str, Any],
        change_set: dict[str, Any],
        op: dict[str, Any],
        identity: dict[str, Any],
        axis: str,
        target: str,
    ) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        row = self._eval_row(docs, identity, create=False)
        before_value = row.get(axis, "UNKNOWN") if row else "UNKNOWN"
        before = {axis: before_value}
        self._matches_expected(before, op.get("expected_before"))

        if axis == "usage":
            if before_value == "USED" and target == "NOT_TRIED":
                if not op["payload"].get("correction_mode"):
                    raise CommandBlocked("USED -> NOT_TRIED requires correction_mode")
                if not (op.get("reason") or change_set.get("reason")):
                    raise CommandBlocked("usage correction requires a reason")

        row = self._eval_row(docs, identity, create=True)
        row[axis] = target
        self._append_unique(row, "evidence", self._audit_ref(change_set["change_set_id"]))
        return before, {axis: target}, ["state/evaluations.yaml"]

    def _apply_deployment(
        self,
        docs: dict[str, Any],
        change_set: dict[str, Any],
        op: dict[str, Any],
        identity: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        payload = op["payload"]
        host, target = payload["host"], payload["state"]
        dep_doc = docs["state/deployments.yaml"]
        known_hosts = set(dep_doc.get("hosts", []) or [])
        if host not in known_hosts:
            raise CommandBlocked(f"unknown deployment host: {host}")

        row = next(
            (x for x in dep_doc.get("deployments", []) or [] if x.get("subject_id") == identity["id"] and x.get("host") == host),
            None,
        )
        current = row.get("state") if row else "ABSENT"
        before = {"host": host, "state": current}
        self._matches_expected(before, op.get("expected_before"))

        if current != target:
            rules = ((self.transitions["commands"]["SET_DEPLOYMENT"] or {}).get("transitions", []) or [])
            rule = next((x for x in rules if x.get("from") == current and x.get("to") == target), None)
            if not rule:
                raise CommandBlocked(f"deployment transition blocked: {current} -> {target}")
            if rule.get("mode") == "reason_required" and not (op.get("reason") or change_set.get("reason")):
                raise CommandBlocked(f"deployment regression {current} -> {target} requires a reason")

        if row is None:
            row = {
                "subject_id": identity["id"],
                "subject_kind": identity["kind"],
                "host": host,
                "state": target,
                "evidence": [self._audit_ref(change_set["change_set_id"])],
            }
            dep_doc.setdefault("deployments", []).append(row)
        else:
            row["state"] = target
            self._append_unique(row, "evidence", self._audit_ref(change_set["change_set_id"]))
        return before, {"host": host, "state": target}, ["state/deployments.yaml"]

    def _workload(self, workload_id: str, subject_id: str) -> dict[str, Any]:
        workload = self.workloads.get(workload_id)
        if not workload:
            raise CommandBlocked(f"unknown workload: {workload_id}")
        if subject_id not in workload["_subjects"]:
            raise CommandBlocked(f"workload {workload_id} is not compatible with {subject_id}")
        return workload

    def _verification_record_id(self, change_set_id: str, operation_id: str) -> str:
        return f"{change_set_id}:{operation_id}"

    def _apply_record_test(
        self,
        docs: dict[str, Any],
        change_set: dict[str, Any],
        op: dict[str, Any],
        identity: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        payload = op["payload"]
        workload = self._workload(payload["workload_id"], identity["id"])
        refs = list(op.get("evidence_refs", []) or [])
        summary = (payload.get("summary") or "").strip()
        if not refs and not summary:
            raise CommandBlocked("RECORD_TEST requires evidence_refs or a durable summary")

        evidence_doc = docs["state/verification-evidence.yaml"]
        records = evidence_doc.setdefault("records", [])
        record_id = self._verification_record_id(change_set["change_set_id"], op["operation_id"])
        if any(x.get("id") == record_id for x in records):
            raise CommandBlocked(f"duplicate verification evidence record: {record_id}")

        row = self._eval_row(docs, identity, create=False)
        current = row.get("verification", "UNKNOWN") if row else "UNKNOWN"
        before = {"verification": current, "workload_id": payload["workload_id"]}
        self._matches_expected(before, op.get("expected_before"))

        records.append(
            {
                "id": record_id,
                "change_set_id": change_set["change_set_id"],
                "operation_id": op["operation_id"],
                "subject_id": identity["id"],
                "workload_id": payload["workload_id"],
                "record_type": "TEST",
                "result": payload["result"],
                "summary": summary or None,
                "evidence_refs": refs,
                "recorded_at": change_set["created_at"],
            }
        )

        after_level = current
        affected = ["state/verification-evidence.yaml"]
        if payload["result"] == "PASS" and current != "VERIFIED":
            after_level = "TESTED"
            row = self._eval_row(docs, identity, create=True)
            row["verification"] = "TESTED"
            self._append_unique(row, "evidence", f"state/verification-evidence.yaml#{record_id}")
            pair = {"subject_id": identity["id"], "workload_id": payload["workload_id"]}
            tested = evidence_doc.setdefault("tested_now", [])
            if not any(x.get("subject_id") == pair["subject_id"] and x.get("workload_id") == pair["workload_id"] for x in tested):
                tested.append(pair)
            affected.append("state/evaluations.yaml")

        return before, {"verification": after_level, "workload_id": payload["workload_id"], "result": payload["result"]}, affected

    def _accepted_pass_evidence(self, docs: dict[str, Any], subject_id: str, workload: dict[str, Any]) -> bool:
        if workload.get("result") == "PASS":
            ev = workload.get("evidence")
            if ev or workload.get("result_summary") or workload.get("verified_at") or workload.get("tested_at"):
                return True
        for record in docs["state/verification-evidence.yaml"].get("records", []) or []:
            if (
                record.get("subject_id") == subject_id
                and record.get("workload_id") == workload["id"]
                and record.get("result") == "PASS"
                and (record.get("evidence_refs") or record.get("summary"))
            ):
                return True
        return False

    def _apply_record_verification(
        self,
        docs: dict[str, Any],
        change_set: dict[str, Any],
        op: dict[str, Any],
        identity: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        payload = op["payload"]
        workload = self._workload(payload["workload_id"], identity["id"])
        if workload.get("target_level") != "VERIFIED":
            raise CommandBlocked(f"workload {workload['id']} does not target VERIFIED")
        if not self._accepted_pass_evidence(docs, identity["id"], workload):
            raise CommandBlocked("VERIFIED requires accepted PASS evidence for the selected workload")

        row = self._eval_row(docs, identity, create=False)
        current = row.get("verification", "UNKNOWN") if row else "UNKNOWN"
        before = {"verification": current, "workload_id": workload["id"]}
        self._matches_expected(before, op.get("expected_before"))

        row = self._eval_row(docs, identity, create=True)
        row["verification"] = "VERIFIED"
        record_id = self._verification_record_id(change_set["change_set_id"], op["operation_id"])
        self._append_unique(row, "evidence", f"state/verification-evidence.yaml#{record_id}")

        evidence_doc = docs["state/verification-evidence.yaml"]
        evidence_doc.setdefault("records", []).append(
            {
                "id": record_id,
                "change_set_id": change_set["change_set_id"],
                "operation_id": op["operation_id"],
                "subject_id": identity["id"],
                "workload_id": workload["id"],
                "record_type": "VERIFICATION",
                "result": "VERIFIED",
                "summary": op.get("reason") or change_set.get("reason"),
                "evidence_refs": list(op.get("evidence_refs", []) or []),
                "recorded_at": change_set["created_at"],
            }
        )
        pair = {"subject_id": identity["id"], "workload_id": workload["id"]}
        verified = evidence_doc.setdefault("verified_now", [])
        if not any(x.get("subject_id") == pair["subject_id"] and x.get("workload_id") == pair["workload_id"] for x in verified):
            verified.append(pair)

        return before, {"verification": "VERIFIED", "workload_id": workload["id"]}, [
            "state/evaluations.yaml",
            "state/verification-evidence.yaml",
        ]

    def _month_plan_row(self, month_doc: dict[str, Any], plan_id: str) -> dict[str, Any]:
        for row in month_doc["budget"]["paid_plans"]:
            if row.get("subscription_id") == plan_id:
                return row
        raise CommandBlocked(f"plan {plan_id} is not a paid-plan row in selected month")

    def _subscription_row(self, docs: dict[str, Any], plan_id: str) -> dict[str, Any]:
        for row in docs["state/subscriptions.yaml"].get("subscriptions", []) or []:
            if row.get("id") == plan_id:
                return row
        raise CommandBlocked(f"unknown subscription: {plan_id}")

    def _effective_reference(self, month_row: dict[str, Any], sub: dict[str, Any]) -> float | int | None:
        if month_row.get("confirmed_mxn") is not None:
            return month_row["confirmed_mxn"]
        if month_row.get("reference_mxn") is not None:
            return month_row["reference_mxn"]
        billing = sub.get("billing", {}) or {}
        if billing.get("currency") == "MXN" and billing.get("amount") is not None:
            return billing["amount"]
        if billing.get("reference_mxn") is not None:
            return billing["reference_mxn"]
        return None

    def _recalculate_month_total(self, docs: dict[str, Any], rel: str) -> None:
        month_doc = docs[rel]
        sub_by_id = {x["id"]: x for x in docs["state/subscriptions.yaml"].get("subscriptions", []) or []}
        total = 0
        for row in month_doc["budget"]["paid_plans"]:
            value = self._effective_reference(row, sub_by_id[row["subscription_id"]])
            if value is not None:
                total += value
        totals = month_doc["budget"].setdefault("totals", {})
        totals["reference_active_stack_mxn_known_components"] = total

    def _apply_account_fact(
        self,
        docs: dict[str, Any],
        change_set: dict[str, Any],
        op: dict[str, Any],
        identity: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
        payload = op["payload"]
        month = payload["month"]
        field, value = payload["field"], payload["value"]
        rel = f"state/months/{month}.yaml"
        if rel not in docs:
            raise CommandBlocked(f"month is not indexed: {month}")
        if not (op.get("reason") or change_set.get("reason") or op.get("evidence_refs")):
            raise CommandBlocked("RESOLVE_ACCOUNT_FACT requires a source, evidence reference, or reason")

        sub = self._subscription_row(docs, identity["id"])
        month_row = self._month_plan_row(docs[rel], identity["id"])
        affected = [rel]

        if field in ("payment_state", "confirmed_mxn", "reference_mxn"):
            current = month_row.get(field)
            before = {field: current}
            self._matches_expected(before, op.get("expected_before"))
            if field in ("confirmed_mxn", "reference_mxn"):
                if value is not None and (not isinstance(value, (int, float)) or value < 0):
                    raise CommandBlocked(f"{field} must be a non-negative number or null")
                if field == "confirmed_mxn" and value is not None and not op.get("evidence_refs"):
                    raise CommandBlocked("confirmed_mxn requires confirming evidence_refs")
            month_row[field] = value
            if field == "confirmed_mxn" and value is not None:
                unresolved = docs[rel]["budget"].setdefault("totals", {}).setdefault("unresolved_items", [])
                if identity["id"] in unresolved:
                    unresolved.remove(identity["id"])
            self._recalculate_month_total(docs, rel)
            return before, {field: value}, affected

        if field == "billing_amount":
            current = (sub.get("billing", {}) or {}).get("amount")
            before = {field: current}
            self._matches_expected(before, op.get("expected_before"))
            if value is not None and (not isinstance(value, (int, float)) or value < 0):
                raise CommandBlocked("billing_amount must be a non-negative number or null")
            sub.setdefault("billing", {})["amount"] = value
            if payload.get("certainty"):
                sub["billing"]["certainty"] = payload["certainty"]
        elif field == "billing_currency":
            current = (sub.get("billing", {}) or {}).get("currency")
            before = {field: current}
            self._matches_expected(before, op.get("expected_before"))
            if not isinstance(value, str) or not value.strip():
                raise CommandBlocked("billing_currency must be a non-empty string")
            sub.setdefault("billing", {})["currency"] = value.strip().upper()
        elif field == "billing_period":
            current = sub.get("billing_period")
            before = {field: current}
            self._matches_expected(before, op.get("expected_before"))
            if value not in ("MONTHLY", "ANNUAL", "PREPAID", "FREE", "UNKNOWN"):
                raise CommandBlocked("invalid billing_period")
            sub["billing_period"] = value
        elif field == "subscription_state":
            current = sub.get("subscription_state")
            before = {field: current}
            self._matches_expected(before, op.get("expected_before"))
            if not isinstance(value, str) or not value.strip():
                raise CommandBlocked("subscription_state must be a non-empty string")
            sub["subscription_state"] = value.strip().upper()
        else:
            raise CommandBlocked(f"unsupported account field: {field}")

        affected.append("state/subscriptions.yaml")
        idx = docs["state/months/index.yaml"]
        for meta in idx.get("months", []) or []:
            mrel = meta["path"]
            if mrel in docs:
                try:
                    self._month_plan_row(docs[mrel], identity["id"])
                except CommandBlocked:
                    continue
                self._recalculate_month_total(docs, mrel)
                if mrel not in affected:
                    affected.append(mrel)
        return before, {field: value}, affected

    def _apply_operation(
        self,
        docs: dict[str, Any],
        change_set: dict[str, Any],
        op: dict[str, Any],
    ) -> dict[str, Any]:
        command = op["command"]
        identity = self._subject_identity(op["subject"])
        self._check_command_class(command, identity["class"])

        if command == "SET_USAGE":
            before, after, affected = self._apply_eval_axis(
                docs, change_set, op, identity, "usage", op["payload"]["usage"]
            )
        elif command == "SET_DECISION":
            before, after, affected = self._apply_eval_axis(
                docs, change_set, op, identity, "decision", op["payload"]["decision"]
            )
        elif command == "SET_PRIORITY":
            before, after, affected = self._apply_eval_axis(
                docs, change_set, op, identity, "priority", op["payload"]["priority"]
            )
        elif command == "SET_DEPLOYMENT":
            before, after, affected = self._apply_deployment(docs, change_set, op, identity)
        elif command == "RECORD_TEST":
            before, after, affected = self._apply_record_test(docs, change_set, op, identity)
        elif command == "RECORD_VERIFICATION":
            before, after, affected = self._apply_record_verification(docs, change_set, op, identity)
        elif command == "RESOLVE_ACCOUNT_FACT":
            before, after, affected = self._apply_account_fact(docs, change_set, op, identity)
        else:
            raise CommandBlocked(f"unsupported command: {command}")

        return {
            "operation_id": op["operation_id"],
            "command": command,
            "subject": copy.deepcopy(op["subject"]),
            "before": before,
            "after": after,
            "affected_files": sorted(set(affected)),
            "guards": ["PASS"],
        }

    def _canonical_digest(self, originals: dict[str, str]) -> str:
        h = hashlib.sha256()
        for rel in sorted(originals):
            h.update(rel.encode())
            h.update(b"\0")
            h.update(originals[rel].encode())
            h.update(b"\0")
        return h.hexdigest()

    def _prepare(self, change_set: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
        self._validate_envelope(change_set)
        docs, originals = self._load_docs(change_set)
        staged = copy.deepcopy(docs)
        results = []
        affected: set[str] = set()
        for op in change_set["operations"]:
            result = self._apply_operation(staged, change_set, op)
            results.append(result)
            affected.update(result["affected_files"])

        # Audit log is part of the transaction and is itself canonical.
        affected.add("state/human-change-log.yaml")
        digest = self._canonical_digest(originals)
        normalized = json.dumps(change_set, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        preview_token = hashlib.sha256((digest + "\n" + normalized).encode()).hexdigest()
        response = {
            "status": "PREVIEW_VALID",
            "change_set_id": change_set["change_set_id"],
            "preview_token": preview_token,
            "operations": results,
            "affected_files": sorted(affected),
            "canonical_digest": digest,
        }
        return response, staged, originals

    def preview(self, change_set: dict[str, Any]) -> dict[str, Any]:
        try:
            response, _, _ = self._prepare(change_set)
            return response
        except CommandBlocked as exc:
            return {
                "status": "PREVIEW_BLOCKED",
                "change_set_id": change_set.get("change_set_id"),
                "errors": [str(exc)],
            }

    def _append_change_log(
        self,
        staged: dict[str, Any],
        change_set: dict[str, Any],
        preview: dict[str, Any],
        affected_files: list[str],
    ) -> None:
        log = staged["state/human-change-log.yaml"]
        entry = {
            "change_set_id": change_set["change_set_id"],
            "applied_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "reason": change_set.get("reason"),
            "supersedes_change_set_id": change_set.get("supersedes_change_set_id"),
            "operations": preview["operations"],
            "affected_files": affected_files,
            "result": "APPLIED",
        }
        log.setdefault("entries", []).append(entry)

    def _write_atomic(self, rel: str, text: str) -> None:
        path = self._path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            os.replace(tmp_name, path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
            raise

    def _git(self, *args: str) -> str:
        try:
            return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()
        except Exception:
            return "unknown"

    def _rebuild_and_validate(self, month: str) -> tuple[str, str]:
        with tempfile.TemporaryDirectory(prefix="stackia-r6-") as td:
            tdir = Path(td)
            snapshot_tmp = tdir / "snapshot.json"
            capacity_tmp = tdir / "capacity.json"
            source_commit = self._git("rev-parse", "HEAD")
            source_ref = self._git("rev-parse", "--abbrev-ref", "HEAD")
            source_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            subprocess.run(
                [
                    sys.executable, str(self._path("scripts/build_stackia.py")),
                    "--month", month,
                    "--source-commit", source_commit,
                    "--source-timestamp", source_timestamp,
                    "--source-ref", source_ref,
                    "--snapshot-out", str(snapshot_tmp),
                    "--capacity-out", str(capacity_tmp),
                ],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable, str(self._path("scripts/validate_stackia_outputs.py")),
                    "--month", month,
                    "--snapshot", str(snapshot_tmp),
                    "--capacity", str(capacity_tmp),
                ],
                cwd=self.root,
                check=True,
                capture_output=True,
                text=True,
            )

            snapshot_text = snapshot_tmp.read_text(encoding="utf-8")
            template = self._path("ui/human-v2-r6-template.html").read_text(encoding="utf-8")
            marker = "__STACKIA_DATA__"
            if template.count(marker) != 1:
                raise RuntimeError("R6 template must contain exactly one data marker")
            rendered = template.replace(marker, snapshot_text.replace("</script", "<\\/script"))
            return snapshot_text, rendered

    def apply(self, change_set: dict[str, Any], preview_token: str, month: str = DEFAULT_MONTH, rebuild: bool = True) -> dict[str, Any]:
        preview, staged, originals = self._prepare(change_set)
        if preview["preview_token"] != preview_token:
            return {
                "status": "FAILED_VALIDATION",
                "change_set_id": change_set.get("change_set_id"),
                "errors": ["preview token mismatch; preview the current canonical state again"],
            }

        self._append_change_log(staged, change_set, preview, preview["affected_files"])
        serialized: dict[str, str] = {}
        for rel in preview["affected_files"]:
            serialized[rel] = self._dump_yaml(staged[rel])

        backups: dict[str, str | None] = {}
        generated_backups: dict[str, str | None] = {}
        try:
            for rel, text in serialized.items():
                path = self._path(rel)
                backups[rel] = path.read_text(encoding="utf-8") if path.exists() else None
                self._write_atomic(rel, text)

            snapshot_text = None
            rendered = None
            if rebuild and self.root == ROOT:
                snapshot_text, rendered = self._rebuild_and_validate(month)
                generated = {
                    f"ui/derived/snapshots/{month}.actual.json": snapshot_text,
                    "ui/prototypes/human-v2-r6-writeback.html": rendered,
                }
                for rel, text in generated.items():
                    path = self._path(rel)
                    generated_backups[rel] = path.read_text(encoding="utf-8") if path.exists() else None
                    self._write_atomic(rel, text)

            return {
                "status": "APPLIED",
                "change_set_id": change_set["change_set_id"],
                "operations": preview["operations"],
                "affected_files": preview["affected_files"],
                "rebuild": "PASS" if rebuild and self.root == ROOT else "SKIPPED",
            }
        except Exception as exc:
            for rel, text in backups.items():
                path = self._path(rel)
                if text is None:
                    if path.exists():
                        path.unlink()
                else:
                    self._write_atomic(rel, text)
            for rel, text in generated_backups.items():
                path = self._path(rel)
                if text is None:
                    if path.exists():
                        path.unlink()
                else:
                    self._write_atomic(rel, text)
            return {
                "status": "FAILED_VALIDATION",
                "change_set_id": change_set.get("change_set_id"),
                "errors": [str(exc)],
            }


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview/apply validated StackIA Human UI change-sets.")
    parser.add_argument("mode", choices=("preview", "apply"))
    parser.add_argument("change_set", help="Path to stackia/change-set@1 JSON")
    parser.add_argument("--preview-token")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--month", default=DEFAULT_MONTH)
    parser.add_argument("--no-rebuild", action="store_true")
    args = parser.parse_args()

    change_set = json.loads(Path(args.change_set).read_text(encoding="utf-8"))
    adapter = StackIAChangeAdapter(Path(args.root))
    if args.mode == "preview":
        result = adapter.preview(change_set)
    else:
        if not args.preview_token:
            raise SystemExit("--preview-token is required for apply")
        result = adapter.apply(
            change_set,
            args.preview_token,
            month=args.month,
            rebuild=not args.no_rebuild,
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] in ("PREVIEW_BLOCKED", "FAILED_VALIDATION"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
