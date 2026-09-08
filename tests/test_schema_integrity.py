"""Repository-wide schema checks that do not depend on hand-picked fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator


_SCHEMA_ROOT = Path(__file__).resolve().parent.parent / "schemas"
_SCHEMAS = sorted(_SCHEMA_ROOT.rglob("*.schema.json"))


@pytest.mark.parametrize("schema_path", _SCHEMAS, ids=lambda path: path.name)
def test_every_schema_is_valid_draft_7(schema_path: Path):
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)


def test_payload_schema_files_follow_the_registry_filename_convention():
    """The SDK resolves payload schemas solely from id + version and filename."""
    for schema_path in _SCHEMA_ROOT.joinpath("payloads").glob("*.schema.json"):
        parts = schema_path.name.split(".")
        assert len(parts) == 4, schema_path.name
        assert parts[-3:] == ["v1", "schema", "json"], schema_path.name
