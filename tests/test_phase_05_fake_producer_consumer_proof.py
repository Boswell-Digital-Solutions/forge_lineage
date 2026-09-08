"""Phase 05 — Fake Producer / Fake Consumer end-to-end proof.

Covers the acceptance criteria from
``07_PHASE_05_FAKE_PRODUCER_CONSUMER_PROOF.md``:

- accepted path works end-to-end (producer node, artifact, consumer node, consumed edge,
  receipts written, fake governance approval succeeds)
- governance promotion blocks on missing/invalid/pending edge
- raw fake execution can continue if lineage write fails (covered by raw-execution test)
- DataForge records all accepted and rejected attempts appropriately
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATAFORGE_LOCAL = _REPO_ROOT / "dataforge-Local"
if str(_DATAFORGE_LOCAL) not in sys.path:
    sys.path.insert(0, str(_DATAFORGE_LOCAL))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from forge_lineage_sdk import (
    EdgeRequirement,
    LineageClient,
    LocalOutcome,
    enforce_edge_for_promotion,
)
from forge_lineage_sdk.builders import build_edge, build_envelope, build_node


def _make_app() -> FastAPI:
    from app.lineage.router import router as lineage_router
    from app.lineage.service import LineageService

    fa = FastAPI()
    fa.include_router(lineage_router)
    fa.state.lineage_service = LineageService()
    return fa


@pytest.fixture
def app() -> FastAPI:
    return _make_app()


@pytest.fixture
def producer_sdk(app: FastAPI) -> LineageClient:
    test_client = TestClient(app)
    return LineageClient(
        base_url="http://testserver",
        writer_identity="fake-producer",
        writer_token="local-fake-producer",
        http_client=test_client,
    )


@pytest.fixture
def consumer_sdk(app: FastAPI) -> LineageClient:
    test_client = TestClient(app)
    return LineageClient(
        base_url="http://testserver",
        writer_identity="fake-consumer",
        writer_token="local-fake-consumer",
        http_client=test_client,
    )


# ------------------------------------------------------------------ helpers


def _producer_run_node(suffix: str = "0001") -> dict:
    return build_node(
        node_type="fake_producer_run",
        payload_schema_id="fake_producer_run",
        payload_schema_version="v1",
        payload={
            "schema_version": "fake_producer_run.v1",
            "run_id": f"run:fake:{suffix}",
            "started_at": "2026-05-04T15:00:00Z",
        },
        source_system="fake-producer",
        source_component="fake-producer/runner",
        trace_id=f"trace:phase05:{suffix}",
        writer_identity="fake-producer",
        stable_source_id=f"run:fake:{suffix}",
    )


def _producer_artifact_node(*, run_id: str, suffix: str) -> dict:
    return build_node(
        node_type="fake_producer_artifact",
        payload_schema_id="fake_producer_artifact",
        payload_schema_version="v1",
        payload={
            "schema_version": "fake_producer_artifact.v1",
            "artifact_id": f"artifact:{run_id}",
            "produced_at": "2026-05-04T15:00:01Z",
            "payload_hash": "0" * 64,
        },
        source_system="fake-producer",
        source_component="fake-producer/runner",
        trace_id=f"trace:phase05:{suffix}",
        writer_identity="fake-producer",
        stable_source_id=f"artifact:{run_id}",
    )


def _consumer_use_node(*, suffix: str) -> dict:
    return build_node(
        node_type="fake_consumer_use",
        payload_schema_id="fake_consumer_use",
        payload_schema_version="v1",
        payload={
            "schema_version": "fake_consumer_use.v1",
            "consumer_id": f"fake-consumer:{suffix}",
            "consumed_at": "2026-05-04T15:00:02Z",
        },
        source_system="fake-consumer",
        source_component="fake-consumer/runner",
        trace_id=f"trace:phase05:{suffix}",
        writer_identity="fake-consumer",
        stable_source_id=f"fake-consumer:{suffix}",
    )


def _consumed_edge(*, source_id: str, target_id: str, suffix: str) -> dict:
    return build_edge(
        source_node_id=source_id,
        target_node_id=target_id,
        edge_type="consumed",
        causality_class="deterministic",
        effect_class="calibration",
        trace_id=f"trace:phase05:{suffix}",
        writer_identity="fake-consumer",
        created_by_system="fake-consumer",
        stable_source_id=f"{source_id}->{target_id}",
    )


def _governance_approve(
    app: FastAPI,
    *,
    source_id: str,
    target_id: str,
    edge_type: str = "consumed",
):
    """Inline 'governance' check: pull the records from the LineageService and
    apply the SDK's enforcement helper. Mirrors what eval-cal-node Gate 3 will
    do later."""
    service = app.state.lineage_service
    src_node = service.get_node(source_id)
    tgt_node = service.get_node(target_id)
    edges = [
        e
        for e in (
            service._store.list_edges_by_source(source_id)  # type: ignore[attr-defined]
        )
        if e.record["target_node_id"] == target_id
    ]
    edge = edges[0].record if edges else None
    return enforce_edge_for_promotion(
        requirement=EdgeRequirement(
            source_node_id=source_id, target_node_id=target_id, edge_type=edge_type
        ),
        source_node=src_node,
        target_node=tgt_node,
        edge=edge,
    )


# ---------------------------------------------------------------- accepted


def test_accepted_path_end_to_end(
    app: FastAPI, producer_sdk: LineageClient, consumer_sdk: LineageClient
):
    suffix = "accepted"
    run_node = _producer_run_node(suffix)
    art_node = _producer_artifact_node(run_id=run_node["payload"]["run_id"], suffix=suffix)
    consumer_node = _consumer_use_node(suffix=suffix)
    edge = _consumed_edge(source_id=art_node["node_id"], target_id=consumer_node["node_id"], suffix=suffix)

    # Producer envelope: run + artifact + produced edge.
    p_env = build_envelope(
        writer_identity="fake-producer",
        trace_id=f"trace:phase05:{suffix}",
        nodes=[run_node, art_node],
        edges=[
            build_edge(
                source_node_id=run_node["node_id"],
                target_node_id=art_node["node_id"],
                edge_type="produced",
                causality_class="deterministic",
                effect_class="informational",
                trace_id=f"trace:phase05:{suffix}",
                writer_identity="fake-producer",
                created_by_system="fake-producer",
                stable_source_id=f"{run_node['node_id']}->{art_node['node_id']}",
            )
        ],
    )
    p_result = producer_sdk.emit_envelope(p_env)
    assert p_result.outcome == LocalOutcome.accepted

    # Consumer envelope.
    c_env = build_envelope(
        writer_identity="fake-consumer",
        trace_id=f"trace:phase05:{suffix}",
        nodes=[consumer_node],
        edges=[edge],
    )
    c_result = consumer_sdk.emit_envelope(c_env)
    assert c_result.outcome == LocalOutcome.accepted

    # Governance approval should succeed.
    decision = _governance_approve(
        app, source_id=art_node["node_id"], target_id=consumer_node["node_id"]
    )
    assert decision.allowed is True
    assert decision.availability == "lineage_available"

    # All accepted writes should have receipts persisted.
    receipts = app.state.lineage_service._store.all_receipts()  # type: ignore[attr-defined]
    assert any(r.record["record_type"] == "node" for r in receipts)
    assert any(r.record["record_type"] == "edge" for r in receipts)


# ---------------------------------------------------------------- negative


def test_promotion_blocks_when_no_edge(app: FastAPI, producer_sdk: LineageClient, consumer_sdk: LineageClient):
    suffix = "no-edge"
    run_node = _producer_run_node(suffix)
    art_node = _producer_artifact_node(run_id=run_node["payload"]["run_id"], suffix=suffix)
    consumer_node = _consumer_use_node(suffix=suffix)

    # Producer + consumer nodes accepted, but no consumed edge submitted.
    producer_sdk.emit_envelope(
        build_envelope(
            writer_identity="fake-producer",
            trace_id=f"trace:phase05:{suffix}",
            nodes=[run_node, art_node],
            edges=[],
        )
    )
    consumer_sdk.emit_node(consumer_node)

    decision = _governance_approve(
        app, source_id=art_node["node_id"], target_id=consumer_node["node_id"]
    )
    assert decision.allowed is False
    assert decision.availability == "lineage_missing"


def test_promotion_blocks_when_edge_pending(app: FastAPI, consumer_sdk: LineageClient):
    suffix = "pending"
    consumer_node = _consumer_use_node(suffix=suffix)
    consumer_sdk.emit_node(consumer_node)

    # Submit edge with a fabricated source id that was never written.
    edge = _consumed_edge(
        source_id="node:nonexistent",
        target_id=consumer_node["node_id"],
        suffix=suffix,
    )
    result = consumer_sdk.emit_edge(edge)
    assert result.outcome == LocalOutcome.pending

    decision = _governance_approve(
        app, source_id="node:nonexistent", target_id=consumer_node["node_id"]
    )
    assert decision.allowed is False
    assert decision.availability == "lineage_missing"


def test_promotion_blocks_when_causality_unknown(
    app: FastAPI, producer_sdk: LineageClient, consumer_sdk: LineageClient
):
    suffix = "unknown-causality"
    run_node = _producer_run_node(suffix)
    art_node = _producer_artifact_node(run_id=run_node["payload"]["run_id"], suffix=suffix)
    consumer_node = _consumer_use_node(suffix=suffix)

    producer_sdk.emit_envelope(
        build_envelope(
            writer_identity="fake-producer",
            trace_id=f"trace:phase05:{suffix}",
            nodes=[run_node, art_node],
            edges=[],
        )
    )
    consumer_sdk.emit_node(consumer_node)

    edge = build_edge(
        source_node_id=art_node["node_id"],
        target_node_id=consumer_node["node_id"],
        edge_type="consumed",
        causality_class="unknown",
        effect_class="informational",
        trace_id=f"trace:phase05:{suffix}",
        writer_identity="fake-consumer",
        created_by_system="fake-consumer",
        stable_source_id=f"{art_node['node_id']}->{consumer_node['node_id']}",
    )
    consumer_sdk.emit_edge(edge)

    decision = _governance_approve(
        app, source_id=art_node["node_id"], target_id=consumer_node["node_id"]
    )
    assert decision.allowed is False
    assert decision.reason_class == "edge_invalid"
    assert "unknown" in (decision.reason_message or "")


def test_unknown_writer_records_attempt_in_dead_letter_or_rejection(producer_sdk: LineageClient, app: FastAPI):
    """Schema-invalid envelope is dead-lettered explicitly, not silently dropped."""
    bad_envelope = {
        "schema_version": "LineageIngestEnvelope.v1",
        "envelope_id": "env:bad",
        "writer_identity": "fake-producer",
        "trace_id": "t",
        "submitted_at": "2026-05-04T15:00:00Z",
        # nodes + edges fields missing on purpose -> schema_invalid
    }
    result = producer_sdk.emit_envelope(bad_envelope)
    assert result.outcome == LocalOutcome.non_retryable_failure
    assert result.error is not None
    assert result.error.error_class == "schema_invalid"


def test_idempotency_with_changed_payload_is_blocked(producer_sdk: LineageClient):
    node = _producer_run_node("idem")
    first = producer_sdk.emit_node(node)
    assert first.outcome == LocalOutcome.accepted

    forged = dict(node)
    forged["payload_hash"] = "f" * 64
    second = producer_sdk.emit_node(forged)
    assert second.outcome == LocalOutcome.rejected
    assert second.error is not None
    assert second.error.error_class == "idempotency_conflict"


def test_raw_execution_continues_when_lineage_unavailable():
    """Raw fake-producer execution must not crash if the lineage service is offline.

    Modeled by a never-listening transport: the SDK returns retryable_failure
    and the simulated raw producer records its work locally regardless.
    """
    sdk = LineageClient(
        base_url="http://127.0.0.1:1",  # nothing listens here
        writer_identity="fake-producer",
        writer_token="local-fake-producer",
    )
    # Simulate raw work: the producer logs its own state; lineage is best-effort.
    raw_state = {"ran": False, "lineage_state": "lineage_missing"}
    raw_state["ran"] = True
    result = sdk.emit_node(_producer_run_node("offline"))
    assert raw_state["ran"] is True
    assert result.outcome == LocalOutcome.retryable_failure
    raw_state["lineage_state"] = "lineage_missing" if not result.accepted else "lineage_available"
    assert raw_state["lineage_state"] == "lineage_missing"
    sdk.close()
