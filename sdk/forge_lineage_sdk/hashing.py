"""Canonical payload hashing and idempotency-key construction."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical_json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def canonical_payload_hash(payload: Any) -> str:
    """Return a hex sha256 of the canonical JSON form of ``payload``."""
    encoded = _canonical_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_idempotency_key(
    *,
    schema_version: str,
    record_type: str,
    source_system: str,
    stable_source_id: str,
    payload_hash: str,
) -> str:
    """Build a stable idempotency key.

    Per Phase 04, the key must include schema_version, record_type, source_system,
    a stable source id, and the payload hash. The key is deterministic: the same
    inputs produce the same key, so retries do not create duplicate records.
    """
    parts = [schema_version, record_type, source_system, stable_source_id, payload_hash]
    digest_input = "|".join(parts).encode("utf-8")
    digest = hashlib.sha256(digest_input).hexdigest()
    return f"flk:{record_type}:{digest[:32]}"
