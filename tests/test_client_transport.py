"""Transport behavior that must remain independent of DataForge's implementation."""

from __future__ import annotations

import httpx

from forge_lineage_sdk import LineageClient, LocalOutcome
from forge_lineage_sdk.builders import build_node
from forge_lineage_sdk.client import RetryPolicy


def _node() -> dict:
    return build_node(
        node_type="fake_producer_run",
        payload_schema_id="fake_producer_run",
        payload_schema_version="v1",
        payload={
            "schema_version": "fake_producer_run.v1",
            "run_id": "run:transport:001",
            "started_at": "2026-05-04T12:00:00Z",
        },
        source_system="fake-producer",
        source_component="test",
        trace_id="trace:transport:001",
        writer_identity="fake-producer",
        stable_source_id="run:transport:001",
    )


def _client(handler) -> LineageClient:  # noqa: ANN001
    return LineageClient(
        base_url="http://lineage.test",
        writer_identity="fake-producer",
        writer_token="test-token",
        transport=httpx.MockTransport(handler),
        retry_policy=RetryPolicy(max_attempts=3, initial_backoff_s=0),
    )


def test_retries_retryable_http_statuses_before_accepting():
    responses = iter((503, 502, 201))
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(next(responses), json={"validation_status": "accepted"})

    result = _client(handler).emit_node(_node())

    assert calls == 3
    assert result.outcome is LocalOutcome.accepted


def test_returns_retryable_failure_after_retryable_http_statuses_are_exhausted():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(504, json={"error_class": "service_unavailable"})

    result = _client(handler).emit_node(_node())

    assert calls == 3
    assert result.outcome is LocalOutcome.retryable_failure
    assert result.error is not None
    assert result.error.error_class == "service_unavailable"
