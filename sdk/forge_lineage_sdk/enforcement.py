"""Consumer-side governance enforcement for lineage edges.

Enforcement is applied at the governance boundary (e.g. eval-cal-node Gate 3,
forgeHQ reviewability promotion, ForgeCommand operator accept). Raw subsystem
execution does not call into this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


_GOVERNANCE_BLOCKING_VALIDATION_STATES = frozenset(
    {"pending", "rejected", "stale", "superseded"}
)


@dataclass
class EdgeRequirement:
    """What the consumer needs to find before promoting."""

    source_node_id: str
    target_node_id: str
    edge_type: str
    expected_source_payload_hash: str | None = None
    forbid_unknown_causality: bool = True


@dataclass
class EnforcementResult:
    allowed: bool
    availability: str
    reason_class: str | None
    reason_message: str | None
    edge: dict[str, Any] | None = None
    source_node: dict[str, Any] | None = None
    target_node: dict[str, Any] | None = None


def enforce_edge_for_promotion(
    *,
    requirement: EdgeRequirement,
    source_node: dict[str, Any] | None,
    target_node: dict[str, Any] | None,
    edge: dict[str, Any] | None,
) -> EnforcementResult:
    """Decide whether the supplied (source, target, edge) tuple is sufficient
    for governance promotion.

    Returns an EnforcementResult. If ``allowed`` is False, the caller MUST NOT
    proceed with the governed consequence (per the doctrine that lineage is
    fail-closed for governed promotion). The ``availability`` field uses the
    canonical lineage availability vocabulary.
    """

    if source_node is None:
        return EnforcementResult(
            allowed=False,
            availability="lineage_missing",
            reason_class="source_node_missing",
            reason_message=f"source node {requirement.source_node_id} not found",
        )
    if target_node is None:
        return EnforcementResult(
            allowed=False,
            availability="lineage_missing",
            reason_class="target_node_missing",
            reason_message=f"target node {requirement.target_node_id} not found",
        )
    if edge is None:
        return EnforcementResult(
            allowed=False,
            availability="lineage_missing",
            reason_class="edge_invalid",
            reason_message="no edge connecting source to target",
            source_node=source_node,
            target_node=target_node,
        )

    if edge.get("source_node_id") != requirement.source_node_id or edge.get(
        "target_node_id"
    ) != requirement.target_node_id:
        return EnforcementResult(
            allowed=False,
            availability="lineage_invalid",
            reason_class="edge_invalid",
            reason_message="edge endpoints do not match requirement",
            edge=edge,
            source_node=source_node,
            target_node=target_node,
        )
    if edge.get("edge_type") != requirement.edge_type:
        return EnforcementResult(
            allowed=False,
            availability="lineage_invalid",
            reason_class="edge_invalid",
            reason_message=f"edge type {edge.get('edge_type')} != required {requirement.edge_type}",
            edge=edge,
            source_node=source_node,
            target_node=target_node,
        )

    edge_state = edge.get("validation_status")
    if edge_state == "pending":
        return EnforcementResult(
            allowed=False,
            availability="lineage_pending",
            reason_class="edge_pending",
            reason_message="edge is pending; cannot satisfy promotion",
            edge=edge,
            source_node=source_node,
            target_node=target_node,
        )
    if edge_state in _GOVERNANCE_BLOCKING_VALIDATION_STATES:
        return EnforcementResult(
            allowed=False,
            availability="lineage_invalid" if edge_state != "stale" else "lineage_stale",
            reason_class="edge_invalid",
            reason_message=f"edge validation_status={edge_state} cannot satisfy promotion",
            edge=edge,
            source_node=source_node,
            target_node=target_node,
        )

    if requirement.forbid_unknown_causality and edge.get("causality_class") == "unknown":
        return EnforcementResult(
            allowed=False,
            availability="lineage_invalid",
            reason_class="edge_invalid",
            reason_message="edge causality_class=unknown cannot satisfy promotion",
            edge=edge,
            source_node=source_node,
            target_node=target_node,
        )

    if requirement.expected_source_payload_hash is not None:
        actual = source_node.get("payload_hash")
        if actual != requirement.expected_source_payload_hash:
            return EnforcementResult(
                allowed=False,
                availability="lineage_stale",
                reason_class="edge_invalid",
                reason_message="source payload hash does not match consumed source",
                edge=edge,
                source_node=source_node,
                target_node=target_node,
            )

    return EnforcementResult(
        allowed=True,
        availability="lineage_available",
        reason_class=None,
        reason_message=None,
        edge=edge,
        source_node=source_node,
        target_node=target_node,
    )
