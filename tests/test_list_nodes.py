"""LineageClient.list_nodes — the read-only discovery helper.

Producers use it to resolve an upstream node's node_id (by a stable id they hold) before emitting a
cross-producer edge. It is best-effort + fail-soft: any non-200 / transport / decode error yields [].
"""
from __future__ import annotations

import httpx

from forge_lineage_sdk import LineageClient


def _client(handler) -> LineageClient:
    return LineageClient(
        base_url="http://df-local",
        writer_identity="t",
        writer_token="t",
        transport=httpx.MockTransport(handler),
    )


def test_list_nodes_returns_nodes_and_passes_query():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["path"] = req.url.path
        seen["node_type"] = req.url.params.get("node_type")
        seen["limit"] = req.url.params.get("limit")
        return httpx.Response(200, json={"nodes": [{"node_id": "node:x:1", "payload": {"k": "v"}}]})

    nodes = _client(handler).list_nodes(node_type="forge_eval_evidence_bundle", limit=25)
    assert seen["path"] == "/api/v1/lineage/nodes"
    assert seen["node_type"] == "forge_eval_evidence_bundle"
    assert seen["limit"] == "25"
    assert nodes == [{"node_id": "node:x:1", "payload": {"k": "v"}}]


def test_list_nodes_is_fail_soft_on_error_status():
    assert _client(lambda r: httpx.Response(500)).list_nodes(node_type="x") == []


def test_list_nodes_is_fail_soft_on_transport_error():
    def boom(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=req)

    assert _client(boom).list_nodes(node_type="x") == []


def test_list_nodes_handles_missing_nodes_key():
    assert _client(lambda r: httpx.Response(200, json={})).list_nodes(node_type="x") == []
