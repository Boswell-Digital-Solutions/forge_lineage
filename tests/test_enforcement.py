"""Governance enforcement: lineage is fail-closed for promoted consequences."""

from __future__ import annotations

from forge_lineage_sdk.enforcement import (
    EdgeRequirement,
    enforce_edge_for_promotion,
)


def _node(node_id: str, payload_hash: str = "h" * 64) -> dict:
    return {
        "schema_version": "LineageNode.v1",
        "node_id": node_id,
        "payload_hash": payload_hash,
        "validation_status": "accepted",
    }


def _edge(*, source: str, target: str, edge_type: str, causality: str = "deterministic", state: str = "accepted") -> dict:
    return {
        "schema_version": "ImpactEdge.v1",
        "source_node_id": source,
        "target_node_id": target,
        "edge_type": edge_type,
        "causality_class": causality,
        "validation_status": state,
    }


def test_missing_source_node_blocks_promotion():
    req = EdgeRequirement(source_node_id="src", target_node_id="tgt", edge_type="consumed")
    result = enforce_edge_for_promotion(
        requirement=req, source_node=None, target_node=_node("tgt"), edge=_edge(source="src", target="tgt", edge_type="consumed")
    )
    assert result.allowed is False
    assert result.reason_class == "source_node_missing"
    assert result.availability == "lineage_missing"


def test_missing_target_node_blocks_promotion():
    req = EdgeRequirement(source_node_id="src", target_node_id="tgt", edge_type="consumed")
    result = enforce_edge_for_promotion(
        requirement=req, source_node=_node("src"), target_node=None, edge=_edge(source="src", target="tgt", edge_type="consumed")
    )
    assert result.allowed is False
    assert result.reason_class == "target_node_missing"


def test_missing_edge_blocks_promotion():
    req = EdgeRequirement(source_node_id="src", target_node_id="tgt", edge_type="consumed")
    result = enforce_edge_for_promotion(
        requirement=req, source_node=_node("src"), target_node=_node("tgt"), edge=None
    )
    assert result.allowed is False
    assert result.reason_class == "edge_invalid"


def test_pending_edge_blocks_promotion():
    req = EdgeRequirement(source_node_id="src", target_node_id="tgt", edge_type="consumed")
    result = enforce_edge_for_promotion(
        requirement=req,
        source_node=_node("src"),
        target_node=_node("tgt"),
        edge=_edge(source="src", target="tgt", edge_type="consumed", state="pending"),
    )
    assert result.allowed is False
    assert result.availability == "lineage_pending"
    assert result.reason_class == "edge_pending"


def test_unknown_causality_blocks_promotion():
    req = EdgeRequirement(source_node_id="src", target_node_id="tgt", edge_type="approved_for_promotion")
    result = enforce_edge_for_promotion(
        requirement=req,
        source_node=_node("src"),
        target_node=_node("tgt"),
        edge=_edge(
            source="src", target="tgt", edge_type="approved_for_promotion", causality="unknown"
        ),
    )
    assert result.allowed is False
    assert result.reason_class == "edge_invalid"


def test_valid_edge_allows_promotion():
    req = EdgeRequirement(source_node_id="src", target_node_id="tgt", edge_type="consumed")
    result = enforce_edge_for_promotion(
        requirement=req,
        source_node=_node("src"),
        target_node=_node("tgt"),
        edge=_edge(source="src", target="tgt", edge_type="consumed"),
    )
    assert result.allowed is True
    assert result.availability == "lineage_available"


def test_source_payload_hash_mismatch_blocks_promotion():
    req = EdgeRequirement(
        source_node_id="src",
        target_node_id="tgt",
        edge_type="consumed",
        expected_source_payload_hash="a" * 64,
    )
    result = enforce_edge_for_promotion(
        requirement=req,
        source_node=_node("src", payload_hash="b" * 64),
        target_node=_node("tgt"),
        edge=_edge(source="src", target="tgt", edge_type="consumed"),
    )
    assert result.allowed is False
    assert result.availability == "lineage_stale"


def test_stale_edge_blocks_promotion():
    req = EdgeRequirement(source_node_id="src", target_node_id="tgt", edge_type="consumed")
    result = enforce_edge_for_promotion(
        requirement=req,
        source_node=_node("src"),
        target_node=_node("tgt"),
        edge=_edge(source="src", target="tgt", edge_type="consumed", state="stale"),
    )
    assert result.allowed is False
    assert result.availability == "lineage_stale"
