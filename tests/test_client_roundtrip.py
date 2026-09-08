"""End-to-end SDK roundtrip: LineageClient -> in-process FastAPI -> LineageService.

These tests prove the local outcome classifications named in
``06_PHASE_04_LINEAGE_SDK_AND_CLIENT_CONTRACT.md``:

- accepted
- accepted_duplicate
- pending
- rejected
- non_retryable_failure
- retryable_failure (covered by transport unit tests, not here)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# Add the dataforge-Local app to sys.path for in-process testing.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATAFORGE_LOCAL = _REPO_ROOT / "dataforge-Local"
if str(_DATAFORGE_LOCAL) not in sys.path:
    sys.path.insert(0, str(_DATAFORGE_LOCAL))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from forge_lineage_sdk import LineageClient, LocalOutcome
from forge_lineage_sdk.builders import build_edge, build_node


def _make_app() -> FastAPI:
    from app.lineage.router import router as lineage_router
    from app.lineage.service import LineageService

    fa = FastAPI()
    fa.include_router(lineage_router)
    fa.state.lineage_service = LineageService()
    return fa


@pytest.fixture
def sdk() -> LineageClient:
    app = _make_app()
    test_client = TestClient(app)
    return LineageClient(
        base_url="http://testserver",
        writer_identity="fake-producer",
        writer_token="local-fake-producer",
        http_client=test_client,
    )


def _producer_run_node() -> dict:
    return build_node(
        node_type="fake_producer_run",
        payload_schema_id="fake_producer_run",
        payload_schema_version="v1",
        payload={
            "schema_version": "fake_producer_run.v1",
            "run_id": "run:fake:002",
            "started_at": "2026-05-04T12:00:00Z",
        },
        source_system="fake-producer",
        source_component="fake-producer/runner",
        trace_id="trace:fake:002",
        writer_identity="fake-producer",
        stable_source_id="run:fake:002",
    )


def test_emit_node_returns_accepted(sdk: LineageClient):
    result = sdk.emit_node(_producer_run_node())
    assert result.outcome == LocalOutcome.accepted
    assert result.accepted is True
    assert result.receipt is not None


def test_emit_node_twice_returns_accepted_duplicate(sdk: LineageClient):
    node = _producer_run_node()
    first = sdk.emit_node(node)
    second = sdk.emit_node(node)
    assert first.outcome == LocalOutcome.accepted
    assert second.outcome == LocalOutcome.accepted_duplicate
    assert second.accepted is True


def test_emit_edge_with_missing_nodes_returns_pending(sdk: LineageClient):
    edge = build_edge(
        source_node_id="node:does-not-exist",
        target_node_id="node:also-not-here",
        edge_type="produced",
        causality_class="deterministic",
        effect_class="informational",
        trace_id="trace:fake:002",
        writer_identity="fake-producer",
        created_by_system="fake-producer",
        stable_source_id="missing-pair",
    )
    result = sdk.emit_edge(edge)
    assert result.outcome == LocalOutcome.pending


def test_pre_send_schema_failure_is_non_retryable(sdk: LineageClient):
    bad = _producer_run_node()
    bad["node_type"] = "definitely_not_a_real_type"
    result = sdk.emit_node(bad)
    assert result.outcome == LocalOutcome.non_retryable_failure
    assert result.error is not None
    assert result.error.error_class == "schema_invalid"


def test_pre_send_payload_subschema_failure_is_non_retryable(sdk: LineageClient):
    bad = _producer_run_node()
    bad["payload"].pop("started_at")
    result = sdk.emit_node(bad)
    assert result.outcome == LocalOutcome.non_retryable_failure
    assert result.error is not None
    assert result.error.error_class == "payload_schema_invalid"


def test_idempotency_conflict_classifies_as_rejected(sdk: LineageClient):
    node = _producer_run_node()
    first = sdk.emit_node(node)
    assert first.outcome == LocalOutcome.accepted

    forged = dict(node)
    forged["payload_hash"] = "f" * 64
    second = sdk.emit_node(forged)
    assert second.outcome == LocalOutcome.rejected
    assert second.error is not None
    assert second.error.error_class == "idempotency_conflict"


def test_unknown_writer_token_classifies_as_non_retryable():
    app = _make_app()
    test_client = TestClient(app)
    sdk = LineageClient(
        base_url="http://testserver",
        writer_identity="fake-producer",
        writer_token="WRONG_TOKEN",
        http_client=test_client,
    )
    result = sdk.emit_node(_producer_run_node())
    assert result.outcome == LocalOutcome.non_retryable_failure
    assert result.error is not None
    assert result.error.error_class == "forbidden"
