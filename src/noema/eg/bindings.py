"""Domain-separated, fail-closed identities for the two EG v1-r2 artifacts."""

from __future__ import annotations

from hashlib import sha256
import json
import math


FIELD_CLASS = {
    "contract_version": "MATERIAL", "contract_revision": "MATERIAL",
    "execution_id": "MATERIAL", "work_order_ref": "MATERIAL",
    "work_order_id": "MATERIAL", "project_id": "MATERIAL",
    "profile": "MATERIAL", "policy_version": "MATERIAL",
    "created_at": "NON_MATERIAL", "baseline_ref": "MATERIAL",
    "disposition": "DERIVED", "reason_codes": "DERIVED",
    "decision": "MATERIAL", "context": "MATERIAL",
    "runtime_resource_policy": "DERIVED",
    "capability_requirements": "MATERIAL", "resolver_receipts": "EVIDENCE",
    "tool_decisions": "DERIVED", "executor": "MATERIAL",
    "model": "MATERIAL", "topology": "MATERIAL",
    "evaluation_constraints": "MATERIAL", "recovery": "MATERIAL",
    "evidence_refs": "EVIDENCE", "effective_needs": "DERIVED",
    "input_bindings": "MATERIAL", "intent": "MATERIAL",
    "material_binding": "DERIVED", "verification_requirements": "DERIVED",
    "evidence_bindings": "EVIDENCE",
}


def _check_json(value: object) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if math.isfinite(value):
            return
        raise ValueError("non-finite value cannot be canonically bound")
    if isinstance(value, list):
        for child in value:
            _check_json(child)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for child in value.values():
            _check_json(child)
        return
    raise ValueError("value cannot be canonically bound")


def canonical_bytes(value: object) -> bytes:
    _check_json(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(domain: str, value: object) -> str:
    return "sha256:" + sha256(domain.encode("ascii") + b"\0" + canonical_bytes(value)).hexdigest()


def material_projection(envelope: dict) -> dict:
    if envelope.get("contract_revision") != 2:
        raise ValueError("material binding requires envelope revision 2")
    if set(envelope) != set(FIELD_CLASS):
        raise ValueError("unclassified or missing envelope field")
    projection = {name: envelope[name] for name, category in FIELD_CLASS.items()
                  if category == "MATERIAL"}
    projection["decision"] = {
        name: envelope["decision"][name]
        for name in ("action_effect", "data_sensitivity", "authority_scope")
    }
    projection["executor"] = {
        "requirements": envelope["executor"]["requirements"],
        "selected_executor": envelope["executor"]["selected_executor"],
    }
    projection["model"] = {
        "requirements": envelope["model"]["requirements"],
        "selected_model": envelope["model"]["selected_model"],
    }
    return projection


def material_digest(envelope: dict) -> str:
    return digest("noema-eg-material-r2", material_projection(envelope))


def envelope_digest(envelope: dict) -> str:
    if envelope.get("contract_revision") != 2:
        raise ValueError("envelope identity requires revision 2")
    return digest("noema-eg-envelope-r2", envelope)


def gate_fingerprint(envelope: dict, gate_id: str) -> str:
    intent = envelope["intent"]
    return digest("noema-eg-gate-r2", {
        "material_digest": material_digest(envelope), "gate_id": gate_id,
        "action_id": intent["action_id"], "attempt_id": intent["attempt_id"],
    })


def read_subject(envelope: dict, index: int, ref: dict) -> str:
    return digest("noema-eg-read-event-r2", {
        "execution_id": envelope["execution_id"],
        "event_index": index,
        "ref": ref,
    })
