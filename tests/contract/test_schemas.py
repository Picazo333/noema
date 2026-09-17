from jsonschema import Draft202012Validator
from noema.schemas import load_schema_bundle, schema_root


def test_all_schemas_are_valid_json_schema():
    schemas, _ = load_schema_bundle(schema_root())
    for schema in schemas.values():
        Draft202012Validator.check_schema(schema)
