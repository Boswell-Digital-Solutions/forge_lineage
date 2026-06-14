"""Helpers to construct fully-formed lineage records.

The SDK does this rather than letting subsystems hand-build dicts so that
hashing, idempotency, and required-field handling is consistent.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from forge_lineage_sdk.hashing import canonical_payload_hash, build_idempotency_key


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def build_node(
    *,
    node_id: str | None = None,
    node_type: str,
    payload_schema_id: str,
    payload_schema_version: str,
    payload: dict[str, Any],
    source_system: str,
    source_component: str,
    trace_id: str,
    writer_identity: str,
    stable_source_id: str,
    run_ref: dict[str, Any] | None = None,
    artifact_ref: dict[str, Any] | None = None,
    signature: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    payload_hash = canonical_payload_hash(payload)
    idem = build_idempotency_key(
        schema_version="LineageNode.v1",
        record_type="node",
        source_system=source_system,
        stable_source_id=stable_source_id,
        payload_hash=payload_hash,
    )
    node: dict[str, Any] = {
        "schema_version": "LineageNode.v1",
        "node_id": node_id or f"node:{node_type}:{uuid.uuid4()}",
        "node_type": node_type,
        "payload_schema_id": payload_schema_id,
        "payload_schema_version": payload_schema_version,
        "payload": payload,
        "payload_hash": payload_hash,
        "source_system": source_system,
        "source_component": source_component,
        "trace_id": trace_id,
        "idempotency_key": idem,
        "writer_identity": writer_identity,
        "recorded_at": recorded_at or _utc_now_iso(),
        "validation_status": "accepted",
    }
    if run_ref is not None:
        node["run_ref"] = run_ref
    if artifact_ref is not None:
        node["artifact_ref"] = artifact_ref
    if signature is not None:
        node["signature"] = signature
    return node


def build_edge(
    *,
    edge_id: str | None = None,
    source_node_id: str,
    target_node_id: str,
    edge_type: str,
    causality_class: str,
    effect_class: str,
    trace_id: str,
    writer_identity: str,
    created_by_system: str,
    stable_source_id: str,
    evidence_refs: list[dict[str, Any]] | None = None,
    decision_ref: dict[str, Any] | None = None,
    signature: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    body = {
        "source_node_id": source_node_id,
        "target_node_id": target_node_id,
        "edge_type": edge_type,
        "causality_class": causality_class,
        "effect_class": effect_class,
        "evidence_refs": evidence_refs or [],
    }
    payload_hash = canonical_payload_hash(body)
    idem = build_idempotency_key(
        schema_version="ImpactEdge.v1",
        record_type="edge",
        source_system=created_by_system,
        stable_source_id=stable_source_id,
        payload_hash=payload_hash,
    )
    edge: dict[str, Any] = {
        "schema_version": "ImpactEdge.v1",
        "edge_id": edge_id or f"edge:{edge_type}:{uuid.uuid4()}",
        "source_node_id": source_node_id,
        "target_node_id": target_node_id,
        "edge_type": edge_type,
        "causality_class": causality_class,
        "effect_class": effect_class,
        "evidence_refs": evidence_refs or [],
        "trace_id": trace_id,
        "payload_hash": payload_hash,
        "idempotency_key": idem,
        "writer_identity": writer_identity,
        "created_by_system": created_by_system,
        "created_at": created_at or _utc_now_iso(),
        "validation_status": "accepted",
    }
    if decision_ref is not None:
        edge["decision_ref"] = decision_ref
    if signature is not None:
        edge["signature"] = signature
    return edge


def build_envelope(
    *,
    envelope_id: str | None = None,
    writer_identity: str,
    trace_id: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    submitted_at: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "LineageIngestEnvelope.v1",
        "envelope_id": envelope_id or f"env:{uuid.uuid4()}",
        "writer_identity": writer_identity,
        "trace_id": trace_id,
        "submitted_at": submitted_at or _utc_now_iso(),
        "nodes": nodes,
        "edges": edges,
    }
