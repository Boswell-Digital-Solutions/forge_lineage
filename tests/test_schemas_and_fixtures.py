"""Validate that valid fixtures pass and invalid fixtures fail (with a specific reason)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge_lineage_sdk.validators import (
    SchemaValidationError,
    validate_node,
    validate_edge,
    validate_envelope,
    validate_payload_against_subschema,
    validate_validation_error,
    validate_write_receipt,
)
from forge_lineage_sdk.builders import build_envelope


_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


# -------- valid fixtures ---------------------------------------------------


def test_valid_fake_producer_run_node_passes():
    node = _load(_FIXTURES / "valid" / "lineage_node_fake_producer_run.json")
    validate_node(node)
    validate_payload_against_subschema(
        node["payload"],
        payload_schema_id=node["payload_schema_id"],
        payload_schema_version=node["payload_schema_version"],
    )


def test_valid_produced_edge_passes():
    edge = _load(_FIXTURES / "valid" / "impact_edge_produced.json")
    validate_edge(edge)


def test_valid_network_verification_observation_node_passes():
    node = _load(_FIXTURES / "valid" / "lineage_node_network_verification_observation.json")
    validate_node(node)
    validate_payload_against_subschema(
        node["payload"],
        payload_schema_id=node["payload_schema_id"],
        payload_schema_version=node["payload_schema_version"],
    )


def test_valid_network_verification_baseline_diff_node_passes():
    node = _load(_FIXTURES / "valid" / "lineage_node_network_verification_baseline_diff.json")
    validate_node(node)
    validate_payload_against_subschema(
        node["payload"],
        payload_schema_id=node["payload_schema_id"],
        payload_schema_version=node["payload_schema_version"],
    )


def test_valid_write_receipt_passes():
    receipt = _load(_FIXTURES / "valid" / "lineage_write_receipt.json")
    validate_write_receipt(receipt)


def test_valid_envelope_resolves_node_schema_reference():
    node = _load(_FIXTURES / "valid" / "lineage_node_fake_producer_run.json")
    envelope = build_envelope(
        envelope_id="env:fixture:001",
        writer_identity="fake-producer",
        trace_id=node["trace_id"],
        submitted_at="2026-05-04T15:00:05Z",
        nodes=[node],
        edges=[],
    )
    validate_envelope(envelope)


def test_validation_error_shape_passes():
    validate_validation_error(
        {
            "schema_version": "LineageValidationError.v1",
            "error_class": "schema_invalid",
            "message": "node_type is required",
            "field_path": "/node_type",
        }
    )


# -------- invalid fixtures: must fail for the expected reason -------------


def test_missing_schema_version_fails_schema_invalid():
    bad = _load(_FIXTURES / "invalid" / "missing_schema_version.json")
    with pytest.raises(SchemaValidationError) as exc:
        validate_node(bad)
    assert exc.value.error_class == "schema_invalid"


def test_unknown_node_type_fails_schema_invalid():
    bad = _load(_FIXTURES / "invalid" / "unknown_node_type.json")
    with pytest.raises(SchemaValidationError) as exc:
        validate_node(bad)
    assert exc.value.error_class == "schema_invalid"


def test_unknown_edge_type_fails_schema_invalid():
    bad = _load(_FIXTURES / "invalid" / "unknown_edge_type.json")
    with pytest.raises(SchemaValidationError) as exc:
        validate_edge(bad)
    assert exc.value.error_class == "schema_invalid"


def test_freeform_payload_without_schema_fails():
    bad = _load(_FIXTURES / "invalid" / "freeform_payload_without_schema.json")
    # Top-level node validation rejects it because payload_schema_id and
    # payload_schema_version are required.
    with pytest.raises(SchemaValidationError) as exc:
        validate_node(bad)
    assert exc.value.error_class == "schema_invalid"


def test_promotion_edge_with_unknown_causality_is_schema_valid_but_enforcement_blocks():
    """Schema permits causality=unknown so the data is recordable, but
    enforcement (Phase 04 governance protocol) rejects it for promotion."""
    bad = _load(_FIXTURES / "invalid" / "promotion_edge_with_unknown_causality.json")
    validate_edge(bad)  # passes JSON Schema by design
    # Enforcement is asserted in test_enforcement.py.


# -------- payload sub-schema enforcement -----------------------------------


def test_payload_subschema_lookup_for_unknown_returns_payload_schema_invalid():
    with pytest.raises(SchemaValidationError) as exc:
        validate_payload_against_subschema(
            {"schema_version": "totally_made_up.v1"},
            payload_schema_id="totally_made_up",
            payload_schema_version="v1",
        )
    assert exc.value.error_class == "payload_schema_invalid"
