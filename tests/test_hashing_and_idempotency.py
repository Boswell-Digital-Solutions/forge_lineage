"""Hashing and idempotency-key construction must be stable and deterministic."""

from __future__ import annotations

from forge_lineage_sdk.hashing import build_idempotency_key, canonical_payload_hash


def test_payload_hash_is_deterministic_irrespective_of_key_order():
    a = {"x": 1, "y": [1, 2, 3], "z": {"a": True, "b": None}}
    b = {"z": {"b": None, "a": True}, "y": [1, 2, 3], "x": 1}
    assert canonical_payload_hash(a) == canonical_payload_hash(b)


def test_payload_hash_changes_with_payload():
    a = {"x": 1}
    b = {"x": 2}
    assert canonical_payload_hash(a) != canonical_payload_hash(b)


def test_idempotency_key_is_deterministic():
    key_a = build_idempotency_key(
        schema_version="LineageNode.v1",
        record_type="node",
        source_system="forge-eval",
        stable_source_id="run:123",
        payload_hash=canonical_payload_hash({"x": 1}),
    )
    key_b = build_idempotency_key(
        schema_version="LineageNode.v1",
        record_type="node",
        source_system="forge-eval",
        stable_source_id="run:123",
        payload_hash=canonical_payload_hash({"x": 1}),
    )
    assert key_a == key_b


def test_idempotency_key_changes_with_payload_hash():
    key_a = build_idempotency_key(
        schema_version="LineageNode.v1",
        record_type="node",
        source_system="forge-eval",
        stable_source_id="run:123",
        payload_hash=canonical_payload_hash({"x": 1}),
    )
    key_b = build_idempotency_key(
        schema_version="LineageNode.v1",
        record_type="node",
        source_system="forge-eval",
        stable_source_id="run:123",
        payload_hash=canonical_payload_hash({"x": 2}),
    )
    assert key_a != key_b
