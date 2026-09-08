"""ForgeLineage SDK.

Public surface: :class:`LineageClient` plus helpers in
:mod:`forge_lineage_sdk.builders` and outcome enums in
:mod:`forge_lineage_sdk.outcomes`.
"""

from forge_lineage_sdk.client import LineageClient
from forge_lineage_sdk.outcomes import (
    LocalOutcome,
    LineageWriteResult,
    LineageError,
)
from forge_lineage_sdk.hashing import canonical_payload_hash, build_idempotency_key
from forge_lineage_sdk.validators import (
    validate_node,
    validate_edge,
    validate_envelope,
    validate_validation_error,
    validate_write_receipt,
    validate_payload_against_subschema,
    SchemaValidationError,
)
from forge_lineage_sdk.enforcement import (
    EdgeRequirement,
    EnforcementResult,
    enforce_edge_for_promotion,
)

__all__ = [
    "LineageClient",
    "LocalOutcome",
    "LineageWriteResult",
    "LineageError",
    "canonical_payload_hash",
    "build_idempotency_key",
    "validate_node",
    "validate_edge",
    "validate_envelope",
    "validate_validation_error",
    "validate_write_receipt",
    "validate_payload_against_subschema",
    "SchemaValidationError",
    "EdgeRequirement",
    "EnforcementResult",
    "enforce_edge_for_promotion",
]
