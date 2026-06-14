"""LineageClient — the only authorized way for subsystems to emit lineage.

The client is intentionally minimal:
- pre-send schema validation
- pre-send payload sub-schema validation
- payload hashing and stable idempotency keys (already done in builders)
- writer-identity header injection
- HTTP transport via httpx
- bounded retry on retryable transport errors (per Phase 04)
- stable LocalOutcome classification

The client never persists state locally and never decides truth.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from forge_lineage_sdk.outcomes import (
    LineageError,
    LineageWriteResult,
    LocalOutcome,
    classify_error,
)
from forge_lineage_sdk.validators import (
    SchemaValidationError,
    validate_edge,
    validate_envelope,
    validate_node,
    validate_payload_against_subschema,
)


_RETRYABLE_TRANSPORT_STATUSES = frozenset({502, 503, 504})


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    initial_backoff_s: float = 0.05
    max_backoff_s: float = 1.0


class LineageClient:
    """HTTP client that emits ForgeLineage records to DataForge Local."""

    def __init__(
        self,
        *,
        base_url: str,
        writer_identity: str,
        writer_token: str,
        timeout_s: float = 5.0,
        transport: httpx.BaseTransport | None = None,
        http_client: httpx.Client | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._writer_identity = writer_identity
        self._writer_token = writer_token
        self._owns_client = http_client is None
        if http_client is not None:
            self._client = http_client
            # Best-effort: ensure required headers are set on the supplied client.
            self._client.headers["X-ForgeLineage-Writer"] = writer_identity
            self._client.headers["X-ForgeLineage-Token"] = writer_token
            self._client.headers.setdefault("Content-Type", "application/json")
        else:
            self._client = httpx.Client(
                base_url=self._base_url,
                timeout=timeout_s,
                transport=transport,
                headers={
                    "X-ForgeLineage-Writer": writer_identity,
                    "X-ForgeLineage-Token": writer_token,
                    "Content-Type": "application/json",
                },
            )
        self._retry = retry_policy or RetryPolicy()

    # Public surface ----------------------------------------------------

    def emit_node(self, node: dict[str, Any]) -> LineageWriteResult:
        try:
            self._validate_node_pre_send(node)
        except SchemaValidationError as exc:
            return _result_from_pre_send_error(exc, record_type="node", record_id=node.get("node_id"))
        return self._post(
            "/api/v1/lineage/nodes",
            payload=node,
            record_type="node",
            record_id=node.get("node_id"),
        )

    def emit_edge(self, edge: dict[str, Any]) -> LineageWriteResult:
        try:
            validate_edge(edge)
        except SchemaValidationError as exc:
            return _result_from_pre_send_error(exc, record_type="edge", record_id=edge.get("edge_id"))
        return self._post(
            "/api/v1/lineage/edges",
            payload=edge,
            record_type="edge",
            record_id=edge.get("edge_id"),
        )

    def emit_envelope(self, envelope: dict[str, Any]) -> LineageWriteResult:
        try:
            validate_envelope(envelope)
            for n in envelope.get("nodes", []):
                self._validate_node_pre_send(n)
            for e in envelope.get("edges", []):
                validate_edge(e)
        except SchemaValidationError as exc:
            return _result_from_pre_send_error(
                exc, record_type="envelope", record_id=envelope.get("envelope_id")
            )
        return self._post(
            "/api/v1/lineage/envelopes",
            payload=envelope,
            record_type="envelope",
            record_id=envelope.get("envelope_id"),
        )

    def list_nodes(self, *, node_type: str, limit: int = 50) -> list[dict[str, Any]]:
        """Read lineage nodes of ``node_type`` (newest first) — a read-only discovery helper
        for producers that must resolve an upstream node's ``node_id`` before emitting a
        cross-producer edge (e.g. eval-cal finding the forge-eval bundle node; ForgeMath finding
        the eval-cal record node). Best-effort + fail-soft: returns ``[]`` on any transport or
        response error, so a caller that cannot discover its upstream simply omits the edge rather
        than blocking the run. No retry (discovery is advisory, not the write path)."""
        try:
            response = self._client.get(
                "/api/v1/lineage/nodes",
                params={"node_type": node_type, "limit": limit},
            )
            if response.status_code != 200:
                return []
            body = response.json()
        except (httpx.HTTPError, ValueError):
            return []
        nodes = body.get("nodes") if isinstance(body, dict) else None
        return nodes if isinstance(nodes, list) else []

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "LineageClient":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    # Internal ----------------------------------------------------------

    @staticmethod
    def _validate_node_pre_send(node: dict[str, Any]) -> None:
        validate_node(node)
        validate_payload_against_subschema(
            node.get("payload", {}),
            payload_schema_id=node["payload_schema_id"],
            payload_schema_version=node["payload_schema_version"],
        )

    def _post(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        record_type: str,
        record_id: str | None,
    ) -> LineageWriteResult:
        last_exc: Exception | None = None
        backoff = self._retry.initial_backoff_s
        for attempt in range(1, self._retry.max_attempts + 1):
            try:
                response = self._client.post(path, json=payload)
            except httpx.ConnectError as exc:
                last_exc = exc
                if attempt < self._retry.max_attempts:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, self._retry.max_backoff_s)
                    continue
                return LineageWriteResult(
                    outcome=LocalOutcome.retryable_failure,
                    error=LineageError(
                        error_class="connection_refused",
                        message=str(exc),
                        record_id=record_id,
                    ),
                    record_type=record_type,
                    record_id=record_id,
                )
            except httpx.TimeoutException as exc:
                last_exc = exc
                if attempt < self._retry.max_attempts:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, self._retry.max_backoff_s)
                    continue
                return LineageWriteResult(
                    outcome=LocalOutcome.retryable_failure,
                    error=LineageError(
                        error_class="timeout", message=str(exc), record_id=record_id
                    ),
                    record_type=record_type,
                    record_id=record_id,
                )

            return self._classify_response(response, record_type=record_type, record_id=record_id)

        # Unreachable but defensive.
        return LineageWriteResult(
            outcome=LocalOutcome.retryable_failure,
            error=LineageError(
                error_class="unknown",
                message=f"exhausted retries: {last_exc!r}",
                record_id=record_id,
            ),
            record_type=record_type,
            record_id=record_id,
        )

    def _classify_response(
        self,
        response: httpx.Response,
        *,
        record_type: str,
        record_id: str | None,
    ) -> LineageWriteResult:
        try:
            body = response.json()
        except Exception:
            body = {}

        if 200 <= response.status_code < 300:
            outcome = LocalOutcome.accepted
            validation_status = (body.get("validation_status") if isinstance(body, dict) else None) or (
                body.get("receipt", {}).get("validation_status") if isinstance(body, dict) else None
            )
            if validation_status == "accepted_duplicate":
                outcome = LocalOutcome.accepted_duplicate
            elif validation_status == "pending":
                outcome = LocalOutcome.pending
            return LineageWriteResult(
                outcome=outcome,
                receipt=body if isinstance(body, dict) else None,
                raw=body if isinstance(body, dict) else None,
                record_type=record_type,
                record_id=record_id,
            )

        # Pending edge convention: 202 Accepted with validation_status=pending.
        if response.status_code == 202:
            return LineageWriteResult(
                outcome=LocalOutcome.pending,
                receipt=body if isinstance(body, dict) else None,
                raw=body if isinstance(body, dict) else None,
                record_type=record_type,
                record_id=record_id,
            )

        if response.status_code in _RETRYABLE_TRANSPORT_STATUSES:
            return LineageWriteResult(
                outcome=LocalOutcome.retryable_failure,
                error=LineageError(
                    error_class="service_unavailable",
                    message=f"http {response.status_code}",
                    record_id=record_id,
                ),
                raw=body if isinstance(body, dict) else None,
                record_type=record_type,
                record_id=record_id,
            )

        # FastAPI wraps HTTPException details under {"detail": {...}}.
        if isinstance(body, dict) and "detail" in body and isinstance(body["detail"], dict):
            err_body = body["detail"]
        else:
            err_body = body if isinstance(body, dict) else {}

        # Body should be a LineageValidationError.v1 shape on 4xx.
        error_class = err_body.get("error_class") if err_body.get("error_class") else "unknown"
        message = err_body.get("message", f"http {response.status_code}")
        outcome = classify_error(error_class)

        # 409 is conventionally idempotency_conflict (mismatched payload for same key).
        if response.status_code == 409 and error_class in ("idempotency_conflict", "unknown"):
            error_class = "idempotency_conflict"
            outcome = LocalOutcome.rejected

        return LineageWriteResult(
            outcome=outcome,
            error=LineageError(
                error_class=error_class,
                message=message,
                field_path=err_body.get("field_path"),
                record_id=record_id,
                missing_node_id=err_body.get("missing_node_id"),
                idempotency_key=err_body.get("idempotency_key"),
            ),
            raw=body if isinstance(body, dict) else None,
            record_type=record_type,
            record_id=record_id,
        )


def _result_from_pre_send_error(
    exc: SchemaValidationError,
    *,
    record_type: str,
    record_id: str | None,
) -> LineageWriteResult:
    return LineageWriteResult(
        outcome=LocalOutcome.non_retryable_failure,
        error=LineageError(
            error_class=exc.error_class,
            message=exc.message,
            field_path=exc.field_path,
            record_id=record_id,
        ),
        record_type=record_type,
        record_id=record_id,
    )
