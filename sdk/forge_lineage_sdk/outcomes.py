"""Local outcome classification returned by the SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LocalOutcome(str, Enum):
    """Stable local outcomes returned by the SDK regardless of transport details."""

    accepted = "accepted"
    accepted_duplicate = "accepted_duplicate"
    pending = "pending"
    rejected = "rejected"
    retryable_failure = "retryable_failure"
    non_retryable_failure = "non_retryable_failure"


@dataclass
class LineageError:
    error_class: str
    message: str
    field_path: str | None = None
    record_id: str | None = None
    missing_node_id: str | None = None
    idempotency_key: str | None = None


@dataclass
class LineageWriteResult:
    outcome: LocalOutcome
    receipt: dict[str, Any] | None = None
    error: LineageError | None = None
    raw: dict[str, Any] | None = None
    record_type: str | None = None
    record_id: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.outcome in (LocalOutcome.accepted, LocalOutcome.accepted_duplicate)


_RETRYABLE_ERROR_CLASSES: frozenset[str] = frozenset(
    {
        "connection_refused",
        "timeout",
        "storage_unavailable",
        "service_unavailable",
        "storage_error",
    }
)

_NON_RETRYABLE_ERROR_CLASSES: frozenset[str] = frozenset(
    {
        "schema_invalid",
        "payload_schema_invalid",
        "unknown_writer",
        "signature_invalid",
        "forbidden",
        "duplicate_accepted",
    }
)


def classify_error(error_class: str) -> LocalOutcome:
    if error_class in _RETRYABLE_ERROR_CLASSES:
        return LocalOutcome.retryable_failure
    if error_class in _NON_RETRYABLE_ERROR_CLASSES:
        return LocalOutcome.non_retryable_failure
    return LocalOutcome.rejected
