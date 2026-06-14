"""YellowJacket → ForgeLineage adapter (Phase 08).

Maps YellowJacket's local TypeScript artifacts (``WorkcellRequest``,
``RunTrace``, ``DependencyManifest``, ``ReviewPacket``, plus operator
decisions) into shared ``LineageNode`` + ``ImpactEdge`` records.

Doctrine reminders:

- Raw YellowJacket runs must not be blocked by lineage failure. Callers should
  treat all adapter outputs as advisory and continue raw execution on error.
- YellowJacket must not silently cause downstream changes — any downstream
  call to ForgeAgents/ForgeEval/ForgeMath/forgeHQ/NeuroForge/DataForge must
  eventually emit an ImpactEdge. ``YellowJacketAdapter.emit_downstream_call_edge``
  is the helper for that.
- Operator-accepted consequences fail closed without lineage. Use
  ``forge_lineage_sdk.enforce_edge_for_promotion`` from the consumer side
  (e.g. ForgeCommand) to verify before applying any operator-accepted
  downstream effect.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Iterable

from forge_lineage_sdk.builders import build_edge, build_envelope, build_node
from forge_lineage_sdk.client import LineageClient
from forge_lineage_sdk.outcomes import LocalOutcome

logger = logging.getLogger(__name__)


# ---- node mapping helpers ------------------------------------------------


def _hash(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def map_workcell_request_to_node(
    artifact: dict[str, Any], *, trace_id: str
) -> dict[str, Any]:
    """``artifact`` is the YellowJacket WorkcellRequest JSON shape.
    Returns a fully-formed LineageNode dict."""
    request_id = (
        artifact.get("workcell_request_id")
        or artifact.get("artifact_id")
        or f"workcell_request:{_hash(artifact)[:16]}"
    )
    payload = {
        "schema_version": "yellowjacket_workcell_request.v1",
        "workcell_request_id": str(request_id),
        "workcell_id": str(artifact.get("workcell_id", "unknown-workcell")),
        "requested_at": str(
            artifact.get("requested_at")
            or artifact.get("created_at")
            or artifact.get("provenance", {}).get("recorded_at")
            or "2026-05-04T00:00:00Z"
        ),
    }
    if "workcell_version" in artifact:
        payload["workcell_version"] = str(artifact["workcell_version"])
    if "requested_by" in artifact:
        payload["requested_by"] = str(artifact["requested_by"])
    return build_node(
        node_type="yellowjacket_workcell_request",
        payload_schema_id="yellowjacket_workcell_request",
        payload_schema_version="v1",
        payload=payload,
        source_system="yellowjacket",
        source_component="yellowjacket/workcell",
        trace_id=trace_id,
        writer_identity="yellowjacket",
        stable_source_id=f"yj:workcell_request:{request_id}",
    )


def map_run_trace_to_node(artifact: dict[str, Any], *, trace_id: str) -> dict[str, Any]:
    run_trace_id = (
        artifact.get("run_trace_id")
        or artifact.get("artifact_id")
        or f"run_trace:{_hash(artifact)[:16]}"
    )
    payload: dict[str, Any] = {
        "schema_version": "yellowjacket_run_trace.v1",
        "run_trace_id": str(run_trace_id),
        "captured_at": str(
            artifact.get("captured_at")
            or artifact.get("provenance", {}).get("recorded_at")
            or "2026-05-04T00:00:00Z"
        ),
        "trace_payload_hash": _hash(artifact),
    }
    if "workcell_id" in artifact:
        payload["workcell_id"] = str(artifact["workcell_id"])
    events = artifact.get("event_sequence")
    if isinstance(events, list):
        payload["event_count"] = len(events)
    transitions = artifact.get("state_transitions")
    if isinstance(transitions, list):
        payload["state_transition_count"] = len(transitions)
    degraded = artifact.get("degraded_events")
    if isinstance(degraded, list):
        payload["degraded_event_count"] = len(degraded)
    return build_node(
        node_type="yellowjacket_run_trace",
        payload_schema_id="yellowjacket_run_trace",
        payload_schema_version="v1",
        payload=payload,
        source_system="yellowjacket",
        source_component="yellowjacket/runtime",
        trace_id=trace_id,
        writer_identity="yellowjacket",
        stable_source_id=f"yj:run_trace:{run_trace_id}",
    )


def map_dependency_manifest_to_node(
    artifact: dict[str, Any], *, trace_id: str
) -> dict[str, Any]:
    manifest_id = (
        artifact.get("manifest_id")
        or artifact.get("artifact_id")
        or f"dep_manifest:{_hash(artifact)[:16]}"
    )
    payload: dict[str, Any] = {
        "schema_version": "yellowjacket_dependency_manifest.v1",
        "manifest_id": str(manifest_id),
        "captured_at": str(
            artifact.get("captured_at")
            or artifact.get("provenance", {}).get("recorded_at")
            or "2026-05-04T00:00:00Z"
        ),
        "manifest_payload_hash": _hash(artifact),
    }
    deps = artifact.get("dependencies")
    if isinstance(deps, list):
        payload["dependency_count"] = len(deps)
    return build_node(
        node_type="yellowjacket_dependency_manifest",
        payload_schema_id="yellowjacket_dependency_manifest",
        payload_schema_version="v1",
        payload=payload,
        source_system="yellowjacket",
        source_component="yellowjacket/dependencies",
        trace_id=trace_id,
        writer_identity="yellowjacket",
        stable_source_id=f"yj:dep_manifest:{manifest_id}",
    )


def map_review_packet_to_node(artifact: dict[str, Any], *, trace_id: str) -> dict[str, Any]:
    packet_id = (
        artifact.get("review_packet_id")
        or artifact.get("artifact_id")
        or f"review_packet:{_hash(artifact)[:16]}"
    )
    payload: dict[str, Any] = {
        "schema_version": "yellowjacket_review_packet.v1",
        "review_packet_id": str(packet_id),
        "captured_at": str(
            artifact.get("captured_at")
            or artifact.get("provenance", {}).get("recorded_at")
            or "2026-05-04T00:00:00Z"
        ),
    }
    if "run_status" in artifact:
        payload["run_status"] = str(artifact["run_status"])
    if "verification_status" in artifact:
        payload["verification_status"] = str(artifact["verification_status"])
    candidates = artifact.get("candidate_outputs")
    if isinstance(candidates, list):
        payload["candidate_output_count"] = len(candidates)
    bundles = artifact.get("evidence_bundle_refs")
    if isinstance(bundles, list):
        payload["evidence_bundle_ref_count"] = len(bundles)
    return build_node(
        node_type="yellowjacket_review_packet",
        payload_schema_id="yellowjacket_review_packet",
        payload_schema_version="v1",
        payload=payload,
        source_system="yellowjacket",
        source_component="yellowjacket/review",
        trace_id=trace_id,
        writer_identity="yellowjacket",
        stable_source_id=f"yj:review_packet:{packet_id}",
    )


def map_operator_decision_to_node(
    decision: dict[str, Any], *, trace_id: str, writer_identity: str = "forgecommand"
) -> dict[str, Any]:
    decision_id = decision.get("decision_id") or f"decision:{_hash(decision)[:16]}"
    payload = {
        "schema_version": "operator_decision.v1",
        "decision_id": str(decision_id),
        "decided_by": str(decision.get("decided_by", "operator")),
        "decided_at": str(decision.get("decided_at", "2026-05-04T00:00:00Z")),
        "outcome": str(decision.get("outcome", "approved")),
    }
    if "decision_kind" in decision:
        payload["decision_kind"] = str(decision["decision_kind"])
    if "reason" in decision:
        payload["reason"] = str(decision["reason"])
    return build_node(
        node_type="operator_decision",
        payload_schema_id="operator_decision",
        payload_schema_version="v1",
        payload=payload,
        source_system=writer_identity,
        source_component=f"{writer_identity}/operator",
        trace_id=trace_id,
        writer_identity=writer_identity,
        stable_source_id=f"{writer_identity}:operator_decision:{decision_id}",
    )


# ---- adapter -------------------------------------------------------------


@dataclass
class YellowJacketEmissionStatus:
    workcell_request_node_id: str | None = None
    run_trace_node_id: str | None = None
    dependency_manifest_node_id: str | None = None
    review_packet_node_id: str | None = None
    operator_decision_node_id: str | None = None
    edges_emitted: tuple[str, ...] = ()
    outcome: str = "lineage_missing"
    error: str | None = None


class YellowJacketAdapter:
    """Top-level helper that builds the YJ → ForgeLineage envelope."""

    WRITER_IDENTITY = "yellowjacket"

    def __init__(self, client: LineageClient) -> None:
        self._client = client

    def emit_run_chain(
        self,
        *,
        run_trace: dict[str, Any],
        workcell_request: dict[str, Any] | None = None,
        dependency_manifest: dict[str, Any] | None = None,
        review_packet: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> YellowJacketEmissionStatus:
        """Emit the standard YJ chain:

        - workcell_request --produced--> run_trace
        - run_trace --produced--> dependency_manifest
        - run_trace --informed--> review_packet
        """
        try:
            return self._emit_run_chain(
                run_trace=run_trace,
                workcell_request=workcell_request,
                dependency_manifest=dependency_manifest,
                review_packet=review_packet,
                trace_id=trace_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("yellowjacket lineage emission raised", exc_info=exc)
            return YellowJacketEmissionStatus(
                outcome="lineage_missing", error=f"{type(exc).__name__}: {exc}"
            )

    def emit_review_to_operator_decision_edge(
        self,
        *,
        review_packet_node_id: str,
        operator_decision: dict[str, Any],
        trace_id: str,
    ) -> YellowJacketEmissionStatus:
        """``review_packet required_review operator_decision`` —
        causality_class=operator_asserted (so DecisionRef is required by schema)."""
        try:
            return self._emit_review_to_operator_decision_edge(
                review_packet_node_id=review_packet_node_id,
                operator_decision=operator_decision,
                trace_id=trace_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("yellowjacket operator-decision lineage emission raised", exc_info=exc)
            return YellowJacketEmissionStatus(
                outcome="lineage_missing", error=f"{type(exc).__name__}: {exc}"
            )

    def emit_downstream_call_edge(
        self,
        *,
        run_trace_node_id: str,
        downstream_target_node_id: str,
        edge_type: str = "informed",
        causality_class: str = "derived",
        effect_class: str = "advisory",
        trace_id: str,
        evidence_refs: Iterable[dict[str, Any]] | None = None,
    ) -> YellowJacketEmissionStatus:
        """Record that a YellowJacket run triggered a downstream subsystem call.

        Per the plan: any downstream call to ForgeAgents/ForgeEval/ForgeMath/
        forgeHQ/NeuroForge/DataForge must eventually emit an ImpactEdge.
        """
        try:
            edge = build_edge(
                source_node_id=run_trace_node_id,
                target_node_id=downstream_target_node_id,
                edge_type=edge_type,
                causality_class=causality_class,
                effect_class=effect_class,
                trace_id=trace_id,
                writer_identity=self.WRITER_IDENTITY,
                created_by_system=self.WRITER_IDENTITY,
                stable_source_id=f"{run_trace_node_id}->{downstream_target_node_id}:{edge_type}",
                evidence_refs=list(evidence_refs) if evidence_refs is not None else None,
            )
            result = self._client.emit_edge(edge)
            if result.outcome in (LocalOutcome.accepted, LocalOutcome.accepted_duplicate):
                return YellowJacketEmissionStatus(
                    edges_emitted=(edge["edge_id"],), outcome="lineage_available"
                )
            if result.outcome == LocalOutcome.pending:
                return YellowJacketEmissionStatus(
                    edges_emitted=(edge["edge_id"],), outcome="lineage_pending"
                )
            return YellowJacketEmissionStatus(
                edges_emitted=(edge["edge_id"],),
                outcome="lineage_degraded",
                error=(result.error.message if result.error else f"non-accept: {result.outcome}"),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("yellowjacket downstream-edge emission raised", exc_info=exc)
            return YellowJacketEmissionStatus(
                outcome="lineage_missing", error=f"{type(exc).__name__}: {exc}"
            )

    # ---- internals ----

    def _emit_run_chain(
        self,
        *,
        run_trace: dict[str, Any],
        workcell_request: dict[str, Any] | None,
        dependency_manifest: dict[str, Any] | None,
        review_packet: dict[str, Any] | None,
        trace_id: str | None,
    ) -> YellowJacketEmissionStatus:
        rt_id = (
            run_trace.get("run_trace_id")
            or run_trace.get("artifact_id")
            or f"run_trace:{_hash(run_trace)[:16]}"
        )
        trace = trace_id or f"trace:yj:{rt_id}"

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        edge_ids: list[str] = []

        run_trace_node = map_run_trace_to_node(run_trace, trace_id=trace)
        nodes.append(run_trace_node)

        wc_node = None
        if workcell_request is not None:
            wc_node = map_workcell_request_to_node(workcell_request, trace_id=trace)
            nodes.append(wc_node)
            wc_to_rt = build_edge(
                source_node_id=wc_node["node_id"],
                target_node_id=run_trace_node["node_id"],
                edge_type="produced",
                causality_class="deterministic",
                effect_class="informational",
                trace_id=trace,
                writer_identity=self.WRITER_IDENTITY,
                created_by_system=self.WRITER_IDENTITY,
                stable_source_id=f"{wc_node['node_id']}->{run_trace_node['node_id']}",
            )
            edges.append(wc_to_rt)
            edge_ids.append(wc_to_rt["edge_id"])

        dep_node = None
        if dependency_manifest is not None:
            dep_node = map_dependency_manifest_to_node(dependency_manifest, trace_id=trace)
            nodes.append(dep_node)
            rt_to_dep = build_edge(
                source_node_id=run_trace_node["node_id"],
                target_node_id=dep_node["node_id"],
                edge_type="produced",
                causality_class="observed",
                effect_class="informational",
                trace_id=trace,
                writer_identity=self.WRITER_IDENTITY,
                created_by_system=self.WRITER_IDENTITY,
                stable_source_id=f"{run_trace_node['node_id']}->{dep_node['node_id']}",
            )
            edges.append(rt_to_dep)
            edge_ids.append(rt_to_dep["edge_id"])

        review_node = None
        if review_packet is not None:
            review_node = map_review_packet_to_node(review_packet, trace_id=trace)
            nodes.append(review_node)
            rt_to_review = build_edge(
                source_node_id=run_trace_node["node_id"],
                target_node_id=review_node["node_id"],
                edge_type="informed",
                causality_class="derived",
                effect_class="advisory",
                trace_id=trace,
                writer_identity=self.WRITER_IDENTITY,
                created_by_system=self.WRITER_IDENTITY,
                stable_source_id=f"{run_trace_node['node_id']}->{review_node['node_id']}",
            )
            edges.append(rt_to_review)
            edge_ids.append(rt_to_review["edge_id"])

        envelope = build_envelope(
            writer_identity=self.WRITER_IDENTITY,
            trace_id=trace,
            nodes=nodes,
            edges=edges,
        )
        result = self._client.emit_envelope(envelope)

        outcome = "lineage_available"
        err = None
        if result.outcome not in (LocalOutcome.accepted, LocalOutcome.accepted_duplicate):
            outcome = "lineage_degraded" if result.outcome != LocalOutcome.pending else "lineage_pending"
            err = result.error.message if result.error else f"non-accept: {result.outcome}"

        return YellowJacketEmissionStatus(
            workcell_request_node_id=(wc_node["node_id"] if wc_node else None),
            run_trace_node_id=run_trace_node["node_id"],
            dependency_manifest_node_id=(dep_node["node_id"] if dep_node else None),
            review_packet_node_id=(review_node["node_id"] if review_node else None),
            edges_emitted=tuple(edge_ids),
            outcome=outcome,
            error=err,
        )

    def _emit_review_to_operator_decision_edge(
        self,
        *,
        review_packet_node_id: str,
        operator_decision: dict[str, Any],
        trace_id: str,
    ) -> YellowJacketEmissionStatus:
        # Operator decisions are written by ForgeCommand/operator; the YJ
        # adapter creates the node *and* the edge using the forgecommand
        # writer identity (matches the security matrix in
        # 13_SECURITY_AUTHORITY_AND_THREAT_MODEL.md). To do that the supplied
        # client must have the forgecommand identity. If the supplied client
        # is the YJ client we still attempt — the server will reject unknown
        # writer combinations.
        decision_node = map_operator_decision_to_node(
            operator_decision, trace_id=trace_id, writer_identity="forgecommand"
        )
        # The node will only be accepted if our client is authenticated as
        # forgecommand. When it isn't, we return lineage_degraded so the
        # caller can re-emit through a forgecommand-identified client.
        node_result = self._client.emit_node(decision_node)
        if node_result.outcome not in (LocalOutcome.accepted, LocalOutcome.accepted_duplicate):
            return YellowJacketEmissionStatus(
                outcome="lineage_degraded",
                error=(
                    node_result.error.message
                    if node_result.error
                    else f"operator decision node not accepted: {node_result.outcome}"
                ),
            )

        edge = build_edge(
            source_node_id=review_packet_node_id,
            target_node_id=decision_node["node_id"],
            edge_type="required_review",
            causality_class="operator_asserted",
            effect_class="promotion",
            trace_id=trace_id,
            writer_identity="forgecommand",
            created_by_system="forgecommand",
            stable_source_id=f"{review_packet_node_id}->{decision_node['node_id']}",
            decision_ref={
                "schema_version": "DecisionRef.v1",
                "decision_id": decision_node["payload"]["decision_id"],
                "decided_by": decision_node["payload"]["decided_by"],
                "decided_at": decision_node["payload"]["decided_at"],
                "decision_kind": decision_node["payload"].get("decision_kind", "operator"),
            },
        )
        edge_result = self._client.emit_edge(edge)
        if edge_result.outcome in (LocalOutcome.accepted, LocalOutcome.accepted_duplicate):
            return YellowJacketEmissionStatus(
                operator_decision_node_id=decision_node["node_id"],
                edges_emitted=(edge["edge_id"],),
                outcome="lineage_available",
            )
        return YellowJacketEmissionStatus(
            operator_decision_node_id=decision_node["node_id"],
            outcome="lineage_degraded",
            error=(edge_result.error.message if edge_result.error else f"non-accept: {edge_result.outcome}"),
        )
