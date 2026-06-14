"""JSON Schema validation for ForgeLineage records.

Validators load the bundled schema set lazily and resolve cross-schema $refs by
filename. Callers can also register additional payload sub-schemas at runtime.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as _JSValidationError


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


@lru_cache(maxsize=64)
def _load_core_schema(filename: str) -> dict[str, Any]:
    return _read_schema(filename)


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


def _resolver_for(schema: dict[str, Any]) -> jsonschema.RefResolver:
    base_uri = _SCHEMA_ROOT.as_uri() + "/"
    # Pre-populate the resolver store with every cross-referenced schema, keyed
    # by the file:// URI the schema would be addressed by from this base.
    store: dict[str, dict[str, Any]] = {}
    for name in _CROSS_REFERENCED_SCHEMAS:
        try:
            doc = _read_schema(name)
        except FileNotFoundError:
            continue
        # By bare filename ref (relative)…
        store[base_uri + name] = doc
        # …and by the file's own $id if it has one (defensive — Draft 7 may
        # rebase under $id otherwise).
        if isinstance(doc, dict) and "$id" in doc:
            store[doc["$id"]] = doc

    def _handler(uri: str) -> dict[str, Any]:
        rel = uri.replace(base_uri, "")
        return _read_schema(rel)

    return jsonschema.RefResolver(
        base_uri=base_uri,
        referrer=schema,
        store=store,
        handlers={"file": _handler},
    )


def _format_path(path) -> str:  # noqa: ANN001
    if not path:
        return ""
    return "/" + "/".join(str(p) for p in path)


def _validate(schema: dict[str, Any], doc: Any, *, error_class: str) -> None:
    resolver = _resolver_for(schema)
    validator = Draft7Validator(schema, resolver=resolver)
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
