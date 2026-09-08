# forge_lineage

Shared contract corpus and Python SDK for **ForgeLineage / ImpactGraph**.

This package implements Phases 01 and 04 of the ForgeLineage updated plan
(`docs/plans/forgelineage-updated-plan-set-2026-05-04`).

## Why this lives outside `forge-contract-core`

`forge-contract-core` admits new contract families only via RFC, and its
admitted-family list is currently scoped to the proving slice and execution
bridge. ForgeLineage contracts are intentionally housed here so they do not
violate that governance rule. A future RFC can promote them.

## Layout

- `schemas/` — JSON Schemas for nodes, edges, refs, receipts, envelopes, errors, and node-payload sub-schemas.
- `fixtures/valid/` — known-good fixtures (pass schema validation).
- `fixtures/invalid/` — known-bad fixtures (must fail validation for a specific reason).
- `sdk/forge_lineage_sdk/` — Python SDK (`LineageClient`).
- `tests/` — schema, fixture, and SDK tests.

## Doctrine

- DataForge owns durable lineage truth. The SDK never persists locally.
- Lineage is non-blocking for raw execution and fail-closed for governed promotion.
- Every node payload must declare `payload_schema_id` and `payload_schema_version`.
- Unknown causality cannot satisfy promotion.
- Pending edges cannot satisfy promotion.

## Running tests

```bash
python -m pytest tests/ -v -m "not integration"
CHECK=1 bash doc/system/BUILD.sh
```

Cross-repository tests require a compatible `dataforge-Local` checkout:

```bash
DATAFORGE_LOCAL=/path/to/dataforge-Local python -m pytest tests/ -v -m integration
```
