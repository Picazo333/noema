"""Bounded EG persistence policy; rejected values never enter diagnostics."""

from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile
from urllib.parse import parse_qsl, unquote, urlsplit


_SENSITIVE_KEYS = {
    "authorization", "authentication", "authheader", "cookie", "setcookie",
    "apikey", "xapikey", "accesstoken", "refreshtoken", "idtoken",
    "bearertoken", "sessiontoken", "clientsecret", "password",
    "credential", "privatekey", "secretkey", "accesskey", "clientkey",
}
_SAFE_KEYS = {"providertokens"}
_SECRET_TEXT = re.compile(
    r"(?i)(?:\bauthorization\s*:\s*(?:bearer|basic)\b|"
    r"\bbearer\s+[A-Za-z0-9._~+/-]{8,}|"
    r"\b(?:access|refresh|id|session|bearer)[_-]?token\s*[:=]|"
    r"\b(?:api[_-]?key|client[_-]?secret|password|cookie)\s*[:=])"
)

_METADATA_FIELDS = {
    "action_id", "attempt_id", "requested_action", "target_ref", "data_sensitivity",
    "deliberation", "dependency_depth", "architecture_impact", "high_uncertainty",
    "already_complete", "complex_context", "required_evidence_unavailable",
    "resolver_required", "requires_external", "independent_review_required",
    "required_resources", "required_interfaces", "tool_requirements",
    "model_requirements", "executor_requirements", "context_hints",
    "recovery_refs", "evidence_bindings", "role_id", "branch", "workspace",
    "frontier_ref", "checkpoint_ref", "rollback_ref", "idempotency_key",
    "parallel_isolated", "serialized_publication", "write_scopes", "role_bindings",
    "exact_target_required", "regression_sensitive", "required_grader_classes",
}
_CANDIDATE_FIELDS = {
    "id", "candidate", "capabilities", "interfaces", "modalities", "allowed",
    "available", "availability", "qualification", "source_relation",
    "adds_material_evidence", "required",
}


def project_r2_inputs(metadata: dict, candidates: dict) -> tuple[dict, dict]:
    """Allow only governance fields used by the revision-2 planner."""
    if not isinstance(metadata, dict) or set(metadata) - _METADATA_FIELDS:
        raise ValueError("EG metadata contains unsupported fields")
    if not isinstance(candidates, dict) or set(candidates) - {
        "tools", "models", "resources", "interfaces", "executor_runtime"
    }:
        raise ValueError("EG candidate snapshot contains unsupported fields")
    for name in ("tool_requirements", "model_requirements", "executor_requirements"):
        value = metadata.get(name)
        if value is not None and (not isinstance(value, dict) or set(value) - {
            "capabilities", "interfaces", "modalities", "max_cost", "max_latency_ms"
        }):
            raise ValueError("EG requirements contain unsupported fields")
    for category in ("tools", "models", "resources", "interfaces"):
        values = candidates.get(category, [])
        if not isinstance(values, list):
            raise ValueError("EG candidate category must be a list")
        for value in values:
            if not isinstance(value, dict) or set(value) - _CANDIDATE_FIELDS:
                raise ValueError("EG candidate contains unsupported fields")
    from .semantics import raise_for_issues, validate_candidate_snapshot_semantics

    raise_for_issues(validate_candidate_snapshot_semantics(candidates))
    assert_persistable(metadata)
    assert_persistable(candidates)
    return dict(metadata), dict(candidates)


def _key_is_sensitive(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
    if normalized in _SAFE_KEYS:
        return False
    return normalized in _SENSITIVE_KEYS or normalized.endswith(
        ("token", "secret", "password", "credential", "privatekey")
    )


def _string_is_sensitive(value: str) -> bool:
    if _SECRET_TEXT.search(value):
        return True
    decoded = value
    for _ in range(2):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
        if _SECRET_TEXT.search(decoded):
            return True
    for candidate in (value, decoded, "https://" + decoded):
        parsed = urlsplit(candidate)
        if parsed.username or parsed.password:
            return True
        if any(_key_is_sensitive(key) for key, _ in parse_qsl(parsed.query, keep_blank_values=True)):
            return True
    return False


def assert_persistable(value: object) -> None:
    """Reject defined credential families throughout a durable EG projection."""
    if isinstance(value, dict):
        for key, child in value.items():
            if _key_is_sensitive(key):
                raise ValueError("EG output contains a credential-like field")
            assert_persistable(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            assert_persistable(child)
    elif isinstance(value, str) and _string_is_sensitive(value):
        raise ValueError("EG output contains credential-like text")


def safe_diagnostic(exc: Exception) -> str:
    """Never echo caller-controlled exception text into a durable log or CLI."""
    return type(exc).__name__


def atomic_write(path: Path, content: str) -> None:
    """Write only a prechecked complete projection, with no partial artifact."""
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".noema-eg-", suffix=".tmp", delete=False,
        ) as stream:
            temporary = stream.name
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
