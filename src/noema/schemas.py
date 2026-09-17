from __future__ import annotations

from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from .loader import load_json

SCHEMA_FILES = {
    "common": "schemas/common/v1.schema.json",
    "project-manifest": "schemas/project-manifest/v1.schema.json",
    "storage-ref": "schemas/storage-ref/v1.schema.json",
    "artifact": "schemas/artifact/v1.schema.json",
    "work-order": "schemas/work-order/v1.schema.json",
    "handoff": "schemas/handoff/v1.schema.json",
    "eval-result": "schemas/eval-result/v1.schema.json",
    "decision": "schemas/decision/v1.schema.json",
    "harvest-candidate": "schemas/harvest-candidate/v1.schema.json",
    "ecosystem-index": "schemas/ecosystem-index/v1.schema.json",
}


def schema_root(protocol_root: Path | None = None) -> Path:
    if protocol_root is not None:
        return protocol_root
    return Path(__file__).resolve().parents[2]


def load_schema_bundle(protocol_root: Path | None = None):
    base = schema_root(protocol_root)
    schemas = {name: load_json(base / rel) for name, rel in SCHEMA_FILES.items()}
    registry = Registry()
    for schema in schemas.values():
        uri = schema.get("$id")
        if uri:
            registry = registry.with_resource(uri, Resource.from_contents(schema))
    return schemas, registry


def validator_for(name: str, protocol_root: Path | None = None) -> Draft202012Validator:
    schemas, registry = load_schema_bundle(protocol_root)
    if name not in schemas:
        raise KeyError(f"Unknown schema: {name}")
    return Draft202012Validator(
        schemas[name],
        registry=registry,
        format_checker=FormatChecker(),
    )


def validation_errors(name: str, data, protocol_root: Path | None = None):
    validator = validator_for(name, protocol_root)
    return sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
