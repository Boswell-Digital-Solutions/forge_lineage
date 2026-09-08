"""JSON Schema validation for ForgeLineage records.

Validators load the bundled schema set lazily and resolve cross-schema $refs by
filename. Callers can also register additional payload sub-schemas at runtime.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as _JSValidationError
from referencing import Registry, Resource


_SCHEMA_ROOT = Path(__file__).resolve().parent.parent.parent / "schemas"


class SchemaValidationError(Exception):
    """Raised when a record does not validate against its schema."""

    def __init__(self, error_class: str, message: str, *, field_path: str | None = None):
        super().__init__(message)
        self.error_class = error_class
        self.message = message
        self.field_path = field_path


def _read_schema(name: str) -> dict[str, Any]:
    path = _SCHEMA_ROOT / name
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _schema_uri(name: str) -> str:
    """Return the canonical local URI used to resolve a bundled schema."""
    return (_SCHEMA_ROOT / name).as_uri()


@lru_cache(maxsize=64)
def _load_core_schema(filename: str) -> dict[str, Any]:
    schema = _read_schema(filename)
    # Core schemas use relative $refs but predate explicit IDs. Assigning a
    # canonical file URI gives the supported reference registry a stable base.
    schema.setdefault("$id", _schema_uri(filename))
    return schema


@lru_cache(maxsize=128)
def _load_payload_subschema(payload_schema_id: str, payload_schema_version: str) -> dict[str, Any]:
    name = f"payloads/{payload_schema_id}.{payload_schema_version}.schema.json"
    return _read_schema(name)


_CROSS_REFERENCED_SCHEMAS = (
    "LineageNode.v1.schema.json",
    "ImpactEdge.v1.schema.json",
    "LineageIngestEnvelope.v1.schema.json",
    "LineageWriteReceipt.v1.schema.json",
    "LineageValidationError.v1.schema.json",
    "ArtifactRef.v1.schema.json",
    "RunRef.v1.schema.json",
    "EvidenceRef.v1.schema.json",
    "DecisionRef.v1.schema.json",
)


@lru_cache(maxsize=1)
def _schema_registry() -> Registry:
    """Load core schemas into jsonschema's supported reference registry."""
    resources: list[tuple[str, Resource]] = []
    for name in _CROSS_REFERENCED_SCHEMAS:
        schema = _load_core_schema(name)
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def _format_path(path) -> str:  # noqa: ANN001
    if not path:
        return ""
    return "/" + "/".join(str(p) for p in path)


def _validate(schema: dict[str, Any], doc: Any, *, error_class: str) -> None:
    validator = Draft7Validator(schema, registry=_schema_registry())
    try:
        validator.validate(doc)
    except _JSValidationError as exc:
        raise SchemaValidationError(
            error_class,
            f"{error_class}: {exc.message}",
            field_path=_format_path(list(exc.absolute_path)),
        ) from exc


def validate_node(node: dict[str, Any]) -> None:
    schema = _load_core_schema("LineageNode.v1.schema.json")
    _validate(schema, node, error_class="schema_invalid")


def validate_edge(edge: dict[str, Any]) -> None:
    schema = _load_core_schema("ImpactEdge.v1.schema.json")
    _validate(schema, edge, error_class="schema_invalid")


def validate_envelope(envelope: dict[str, Any]) -> None:
    schema = _load_core_schema("LineageIngestEnvelope.v1.schema.json")
    _validate(schema, envelope, error_class="schema_invalid")


def validate_write_receipt(receipt: dict[str, Any]) -> None:
    """Validate a server write receipt before a consumer relies on it."""
    schema = _load_core_schema("LineageWriteReceipt.v1.schema.json")
    _validate(schema, receipt, error_class="schema_invalid")


def validate_validation_error(error: dict[str, Any]) -> None:
    """Validate a structured server validation error."""
    schema = _load_core_schema("LineageValidationError.v1.schema.json")
    _validate(schema, error, error_class="schema_invalid")


def validate_payload_against_subschema(
    payload: dict[str, Any], *, payload_schema_id: str, payload_schema_version: str
) -> None:
    try:
        sub_schema = _load_payload_subschema(payload_schema_id, payload_schema_version)
    except FileNotFoundError as exc:
        raise SchemaValidationError(
            "payload_schema_invalid",
            f"payload_schema_invalid: no schema for {payload_schema_id}/{payload_schema_version}",
        ) from exc
    _validate(sub_schema, payload, error_class="payload_schema_invalid")
