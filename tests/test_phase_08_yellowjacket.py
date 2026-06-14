"""Phase 08 — YellowJacket Trace Integration tests.

Acceptance criteria from ``10_PHASE_08_YELLOWJACKET_TRACE_INTEGRATION.md``:

- YellowJacket emits a shared node from local RunTrace.
- RunTrace preserves parent/source artifact references.
- Dependency events are mapped to evidence refs, not freeform strings only.
- Review packet links to operator decision.
- Missing downstream edge blocks governance promotion.
- Raw YellowJacket run may degrade, but operator-accepted consequences fail
  closed without lineage.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATAFORGE_LOCAL = _REPO_ROOT / "dataforge-Local"
if str(_DATAFORGE_LOCAL) not in sys.path:
    sys.path.insert(0, str(_DATAFORGE_LOCAL))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from forge_lineage_sdk import (  # noqa: E402
    EdgeRequirement,
    LineageClient,
    enforce_edge_for_promotion,
)
from forge_lineage_sdk.adapters import (  # noqa: E402
    YellowJacketAdapter,
    map_run_trace_to_node,
)


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
def http(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def yj_client(http: TestClient) -> LineageClient:
    return LineageClient(
        base_url="http://testserver",
        writer_identity="yellowjacket",
        writer_token="local-yellowjacket",
        http_client=http,
    )


@pytest.fixture
def fc_client(app: FastAPI) -> LineageClient:
    return LineageClient(
        base_url="http://testserver",
        writer_identity="forgecommand",
        writer_token="local-forgecommand",
        http_client=TestClient(app),
    )


# -------------------------------- artifacts (YJ-shape JSON) ----------------


def _workcell_request(suffix: str = "001") -> dict:
    return {
        "artifact_type": "WorkcellRequest",
        "workcell_request_id": f"workcell_request:{suffix}",
        "workcell_id": f"workcell:demo:{suffix}",
        "workcell_version": "v1.1",
        "requested_at": "2026-05-04T17:00:00Z",
        "requested_by": "yellowjacket-runtime",
    }


def _run_trace(suffix: str = "001") -> dict:
    return {
        "artifact_type": "RunTrace",
        "run_trace_id": f"run_trace:{suffix}",
        "workcell_id": f"workcell:demo:{suffix}",
        "captured_at": "2026-05-04T17:00:05Z",
        "event_sequence": ["request", "admitted", "planned", "completed"],
        "state_transitions": [
            {"from": None, "to": "request", "at": "2026-05-04T17:00:00Z"},
            {"from": "request", "to": "admitted", "at": "2026-05-04T17:00:01Z"},
            {"from": "admitted", "to": "planned", "at": "2026-05-04T17:00:02Z"},
            {"from": "planned", "to": "completed", "at": "2026-05-04T17:00:05Z"},
        ],
        "dependency_events": ["forge-eval:reachable", "forgemath:reachable"],
        "error_events": [],
        "degraded_events": [],
        "checkpoint_events": [],
        "timing_summary": {"total_ms": 5000},
    }


def _dependency_manifest(suffix: str = "001") -> dict:
    return {
        "artifact_type": "DependencyManifest",
        "manifest_id": f"dep_manifest:{suffix}",
        "captured_at": "2026-05-04T17:00:06Z",
        "dependencies": [
            {"name": "forge-eval", "version": "v1.0", "health": "ready"},
            {"name": "forgemath", "version": "v0.4", "health": "ready"},
        ],
    }


def _review_packet(suffix: str = "001") -> dict:
    return {
        "artifact_type": "ReviewPacket",
        "review_packet_id": f"review_packet:{suffix}",
        "captured_at": "2026-05-04T17:00:07Z",
        "run_status": "completed",
        "verification_status": "passed",
        "candidate_outputs": ["output:001", "output:002"],
        "evidence_bundle_refs": ["bundle:abc"],
        "operator_actions": ["accept", "defer"],
    }


# ---------------------------------------------------------------- happy path


def test_yj_emits_full_chain_from_run_trace(yj_client, app):
    adapter = YellowJacketAdapter(yj_client)
    status = adapter.emit_run_chain(
        run_trace=_run_trace(),
        workcell_request=_workcell_request(),
        dependency_manifest=_dependency_manifest(),
        review_packet=_review_packet(),
    )
    assert status.outcome == "lineage_available"
    assert status.run_trace_node_id is not None
    assert status.workcell_request_node_id is not None
    assert status.dependency_manifest_node_id is not None
    assert status.review_packet_node_id is not None
    assert len(status.edges_emitted) == 3

    service = app.state.lineage_service
    rt = service.get_node(status.run_trace_node_id)
    assert rt is not None
    # RunTrace node payload preserves event/state counts.
    assert rt["payload"]["event_count"] == 4
    assert rt["payload"]["state_transition_count"] == 4
    assert rt["payload"]["workcell_id"] == "workcell:demo:001"


def test_run_trace_node_alone_is_emittable_when_other_artifacts_missing(yj_client):
    adapter = YellowJacketAdapter(yj_client)
    status = adapter.emit_run_chain(run_trace=_run_trace(suffix="solo"))
    assert status.outcome == "lineage_available"
    assert status.run_trace_node_id is not None
    assert status.workcell_request_node_id is None
    assert status.dependency_manifest_node_id is None
    assert status.review_packet_node_id is None
    assert status.edges_emitted == ()


def test_review_packet_links_to_operator_decision(yj_client, fc_client, app, http):
    adapter = YellowJacketAdapter(yj_client)
    chain = adapter.emit_run_chain(
        run_trace=_run_trace(suffix="opdec"),
        review_packet=_review_packet(suffix="opdec"),
    )

    fc_adapter = YellowJacketAdapter(fc_client)
    decision_status = fc_adapter.emit_review_to_operator_decision_edge(
        review_packet_node_id=chain.review_packet_node_id,
        operator_decision={
            "decision_id": "decision:opdec:001",
            "decided_by": "operator:demo",
            "decided_at": "2026-05-04T17:01:00Z",
            "outcome": "approved",
            "decision_kind": "yj_review",
            "reason": "approved by demo operator",
        },
        trace_id="trace:yj:opdec",
    )
    assert decision_status.outcome == "lineage_available"
    assert decision_status.operator_decision_node_id is not None

    # Verify the required_review edge exists with operator_asserted causality
    # and a DecisionRef attached.
    down = http.get(
        f"/api/v1/lineage/nodes/{chain.review_packet_node_id}/downstream",
        params={"max_depth": 1},
    ).json()
    matching = [
        e
        for e in down["edges"]
        if e["target_node_id"] == decision_status.operator_decision_node_id
        and e["edge_type"] == "required_review"
    ]
    assert len(matching) == 1
    edge = matching[0]
    assert edge["causality_class"] == "operator_asserted"
    assert edge["decision_ref"]["decision_id"] == "decision:opdec:001"


# -------------------------------------------------- downstream-edge tests


def test_downstream_call_edge_is_emitted_on_call_to_subsystem(yj_client, app):
    """YJ runtime called forge-eval — record the impact edge (informed)."""
    adapter = YellowJacketAdapter(yj_client)
    chain = adapter.emit_run_chain(run_trace=_run_trace(suffix="downcall"))

    # Pretend forge-eval emitted a forge_eval_run node already (out of scope
    # here; we just need a target node for the downstream edge).
    from forge_lineage_sdk.builders import build_node

    fe_run_node = build_node(
        node_type="forge_eval_run",
        payload_schema_id="forge_eval_run",
        payload_schema_version="v1",
        payload={
            "schema_version": "forge_eval_run.v1",
            "forge_eval_run_id": "fe-from-yj",
            "repository_id": "repo:demo",
            "head_ref": "abc",
            "deterministic": True,
        },
        source_system="forge-eval",
        source_component="forge-eval/stage_runner",
        trace_id="trace:yj:downcall",
        writer_identity="forge-eval",
        stable_source_id="forge-eval:run:fe-from-yj",
    )
    fe_client = LineageClient(
        base_url="http://testserver",
        writer_identity="forge-eval",
        writer_token="local-forge-eval",
        http_client=TestClient(app),
    )
    fe_client.emit_node(fe_run_node)

    edge_status = adapter.emit_downstream_call_edge(
        run_trace_node_id=chain.run_trace_node_id,
        downstream_target_node_id=fe_run_node["node_id"],
        edge_type="informed",
        causality_class="derived",
        effect_class="advisory",
        trace_id="trace:yj:downcall",
    )
    assert edge_status.outcome == "lineage_available"
    assert len(edge_status.edges_emitted) == 1


# -------------------------------- governance enforcement (operator-accepted)


def test_operator_accepted_consequence_blocks_without_required_review_edge(
    yj_client, app, http
):
    """Per plan: 'operator-accepted consequences fail closed without lineage'.
    Build a review packet with no required_review edge to an operator decision
    and verify enforcement blocks promotion."""
    adapter = YellowJacketAdapter(yj_client)
    chain = adapter.emit_run_chain(
        run_trace=_run_trace(suffix="block-no-review"),
        review_packet=_review_packet(suffix="block-no-review"),
    )
    # No operator decision was emitted. Look for a required_review edge.
    decision_node_id_we_expect = "decision:does-not-exist"
    src_resp = http.get(f"/api/v1/lineage/nodes/{chain.review_packet_node_id}")
    src = src_resp.json() if src_resp.status_code == 200 else None
    decision_node = None  # never emitted
    edge = None
    decision = enforce_edge_for_promotion(
        requirement=EdgeRequirement(
            source_node_id=chain.review_packet_node_id,
            target_node_id=decision_node_id_we_expect,
            edge_type="required_review",
        ),
        source_node=src,
        target_node=decision_node,
        edge=edge,
    )
    assert decision.allowed is False
    assert decision.availability == "lineage_missing"


def test_missing_downstream_edge_blocks_governance_promotion(yj_client, app, http):
    """If YJ called a downstream subsystem but failed to emit the impact edge,
    operator-accepted promotion of the consequence must fail closed."""
    adapter = YellowJacketAdapter(yj_client)
    chain = adapter.emit_run_chain(run_trace=_run_trace(suffix="no-down-edge"))

    # Pretend a forge_eval_run node was created downstream by YJ's effect, but
    # the impact edge was never emitted.
    from forge_lineage_sdk.builders import build_node

    fe_run_node = build_node(
        node_type="forge_eval_run",
        payload_schema_id="forge_eval_run",
        payload_schema_version="v1",
        payload={
            "schema_version": "forge_eval_run.v1",
            "forge_eval_run_id": "fe-no-edge",
            "repository_id": "repo:demo",
            "head_ref": "abc",
            "deterministic": True,
        },
        source_system="forge-eval",
        source_component="forge-eval/stage_runner",
        trace_id="trace:yj:no-down-edge",
        writer_identity="forge-eval",
        stable_source_id="forge-eval:run:fe-no-edge",
    )
    fe_client = LineageClient(
        base_url="http://testserver",
        writer_identity="forge-eval",
        writer_token="local-forge-eval",
        http_client=TestClient(app),
    )
    fe_client.emit_node(fe_run_node)

    src = app.state.lineage_service.get_node(chain.run_trace_node_id)
    tgt = app.state.lineage_service.get_node(fe_run_node["node_id"])
    decision = enforce_edge_for_promotion(
        requirement=EdgeRequirement(
            source_node_id=chain.run_trace_node_id,
            target_node_id=fe_run_node["node_id"],
            edge_type="informed",
        ),
        source_node=src,
        target_node=tgt,
        edge=None,
    )
    assert decision.allowed is False


# -------------------------------- raw execution non-blocking


def test_raw_yj_execution_continues_when_lineage_unreachable():
    """YJ's run may produce its local RunTrace even if the lineage service is
    offline. The adapter must return a status, never raise."""
    bad = LineageClient(
        base_url="http://127.0.0.1:1",
        writer_identity="yellowjacket",
        writer_token="local-yellowjacket",
    )
    adapter = YellowJacketAdapter(bad)
    status = adapter.emit_run_chain(run_trace=_run_trace(suffix="offline"))
    assert status.outcome in ("lineage_missing", "lineage_degraded")


def test_run_trace_node_mapping_is_deterministic_for_same_artifact():
    """Same input artifact => same payload hash. Idempotency keys are stable."""
    a = map_run_trace_to_node(_run_trace(suffix="determ"), trace_id="trace:test")
    b = map_run_trace_to_node(_run_trace(suffix="determ"), trace_id="trace:test")
    assert a["payload"]["trace_payload_hash"] == b["payload"]["trace_payload_hash"]
    assert a["payload_hash"] == b["payload_hash"]
    assert a["idempotency_key"] == b["idempotency_key"]
