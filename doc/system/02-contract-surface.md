            # Contract Surface

            **Document version:** 2.0 (2026-06-22) - canonical compliance migration

            Schema truth lives under `schemas/`, including nodes, edges, refs, receipts, ingest envelopes, validation errors, and node-payload schemas.

SDK truth lives under `sdk/forge_lineage_sdk/`. Fixtures under `fixtures/valid/` and `fixtures/invalid/` prove accepted and rejected shapes.

## FailureForge attestation node types

`failureforge_attestation_verdict` and `failureforge_attestation_revocation` are node types (RFC-FFQ-02 in `forge_contract_core`, `forge-smithy` ADR-012). Their payload schemas in `schemas/payloads/` check the shape only. `forge_contract_core` owns the families and their semantic rules.

A lineage write takes no credential, so a reader must not trust one of these nodes because it is in the store. A verdict embeds the signed approval proof, and a reader verifies it. The `node_id` is content-derived (`ffav-` or `ffar-` plus a SHA-256), because DataForge-Local keeps the first writer of an id.

