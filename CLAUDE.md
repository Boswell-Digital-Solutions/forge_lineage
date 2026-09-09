# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository.

## Project Overview

`forge_lineage` (ForgeLineage / ImpactGraph) is the shared contract corpus and Python SDK for
lineage tracking in the Forge ecosystem: JSON Schemas for nodes, edges, refs, receipts, and
envelopes, plus a `LineageClient` SDK that validates, hashes, and emits lineage records to
DataForge Local. It implements Phases 01 and 04 of the ForgeLineage plan and is intentionally
housed outside `forge-contract-core` because that repo only admits new contract families via RFC.

## Common Commands

```bash
python -m pytest tests/ -v -m "not integration"      # unit + schema/fixture/SDK tests
CHECK=1 bash doc/system/BUILD.sh                       # verify doc/LINSYSTEM.md is up to date
```

Cross-repository integration tests require a compatible `dataforge-Local` checkout:

```bash
DATAFORGE_LOCAL=/path/to/dataforge-Local python -m pytest tests/ -v -m integration
```

CI (`.github/workflows/checks.yml`) runs the unit tests, the doc-system build check, and
`git diff --check` on every push to `main` and on pull requests.

## Architecture

- `schemas/` — JSON Schemas for nodes, edges, refs, receipts, envelopes, errors, and node-payload
  sub-schemas.
- `fixtures/valid/` — known-good fixtures that pass schema validation.
- `fixtures/invalid/` — known-bad fixtures that must fail validation for a specific reason.
- `sdk/forge_lineage_sdk/` — the Python SDK (`LineageClient`), packaged separately as
  `forge-lineage-sdk` (`sdk/pyproject.toml`).
- `tests/` — schema, fixture, and SDK tests.
- `doc/system/` is the authored source for the canonical `doc/LINSYSTEM.md` reference; rebuild with
  `bash doc/system/BUILD.sh` rather than hand-editing the generated file.

## Notes

- DataForge owns durable lineage truth — the SDK never persists locally.
- Lineage is non-blocking for raw execution and fail-closed for governed promotion.
- Every node payload must declare `payload_schema_id` and `payload_schema_version`.
- Unknown causality cannot satisfy promotion, and pending edges cannot satisfy promotion.
