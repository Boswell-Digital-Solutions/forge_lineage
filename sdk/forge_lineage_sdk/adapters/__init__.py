"""Adapters that map subsystem-local artifacts to ForgeLineage envelopes.

These exist because subsystems written in non-Python runtimes (e.g. YellowJacket
in TypeScript/Bun) can produce their local artifacts and hand them off to a
Python orchestration layer for lineage emission. The TypeScript-native
client port is on the deferred list per Phase 04 §"TypeScript-oriented shape later".
"""

from forge_lineage_sdk.adapters.yellowjacket import (
    YellowJacketAdapter,
    YellowJacketEmissionStatus,
    map_run_trace_to_node,
    map_workcell_request_to_node,
    map_dependency_manifest_to_node,
    map_review_packet_to_node,
    map_operator_decision_to_node,
)

__all__ = [
    "YellowJacketAdapter",
    "YellowJacketEmissionStatus",
    "map_run_trace_to_node",
    "map_workcell_request_to_node",
    "map_dependency_manifest_to_node",
    "map_review_packet_to_node",
    "map_operator_decision_to_node",
]
