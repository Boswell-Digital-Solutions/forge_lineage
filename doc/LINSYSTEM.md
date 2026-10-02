        # forge_lineage - Compiled System Reference

        **Designation:** LIN
        **Document role:** Canonical compiled technical reference for ForgeLineage and ImpactGraph contracts
        **Source:** `doc/system/`
        **Build command:** `bash doc/system/BUILD.sh`
        **Document version:** 2.0 (2026-06-22) - canonical compliance migration
        **Protocol:** BDS Documentation Protocol v2.0; BDS Repo Documentation System Canonical Compliance Standard

        > **Generated artifact warning:** `doc/LINSYSTEM.md` is assembled output. Edit
        > the source modules under `doc/system/` and rebuild. Hand edits to the
        > compiled artifact are overwritten by the next build.

        Assembly contract:

        - Command: `bash doc/system/BUILD.sh`
        - Validation: `bash doc/system/validate_snapshots.sh` runs during assembly
        - Primary output: `doc/LINSYSTEM.md`

        This `doc/system/` tree is the canonical source of truth for forge_lineage. It uses
        explicit **truth classes**: canonical facts define repo role, authority
        boundaries, contract behavior, runtime behavior, and verification doctrine;
        snapshot facts are dated, audit-derived counts and current implementation
        inventory that may drift between audits.

        | Part | File | Contents |
        | --- | --- | --- |
        | §1 | `01-overview.md` | 01 Overview |
| §2 | `02-contract-surface.md` | 02 Contract Surface |
| §3 | `03-runtime-boundary.md` | 03 Runtime Boundary |
| §4 | `04-dependencies.md` | 04 Dependencies |
| §5 | `05-governance.md` | 05 Governance |
| §6 | `06-verification.md` | 06 Verification |
| §7 | `90-appendices.md` | Appendices |

        ## Quick Assembly

        ```bash
        bash doc/system/BUILD.sh
        ```

---

            # Overview

            **Document version:** 2.0 (2026-06-22) - canonical compliance migration

            `forge_lineage` is the shared contract corpus and Python SDK for ForgeLineage / ImpactGraph.

It intentionally lives outside `forge-contract-core` until a future RFC admits the family there.

---

            # Contract Surface

            **Document version:** 2.0 (2026-06-22) - canonical compliance migration

            Schema truth lives under `schemas/`, including nodes, edges, refs, receipts, ingest envelopes, validation errors, and node-payload schemas.

SDK truth lives under `sdk/forge_lineage_sdk/`. Fixtures under `fixtures/valid/` and `fixtures/invalid/` prove accepted and rejected shapes.

## FailureForge attestation node types

`failureforge_attestation_verdict` and `failureforge_attestation_revocation` are node types (RFC-FFQ-02 in `forge_contract_core`, `forge-smithy` ADR-012). Their payload schemas in `schemas/payloads/` check the shape only. `forge_contract_core` owns the families and their semantic rules.

A lineage write takes no credential, so a reader must not trust one of these nodes because it is in the store. A verdict embeds the signed approval proof, and a reader verifies it. The `node_id` is content-derived (`ffav-` or `ffar-` plus a SHA-256), because DataForge-Local keeps the first writer of an id.


---

            # Runtime Boundary

            **Document version:** 2.0 (2026-06-22) - canonical compliance migration

            The SDK never persists durable lineage truth locally. DataForge owns durable lineage truth.

Lineage is non-blocking for raw execution and fail-closed for governed promotion.

---

            # Dependencies

            **Document version:** 2.0 (2026-06-22) - canonical compliance migration

            The package contains JSON schemas, fixtures, tests, and a Python SDK.

Dependency truth is owned by `sdk/pyproject.toml` and the test environment used to run the schema and SDK checks.

---

            # Governance

            **Document version:** 2.0 (2026-06-22) - canonical compliance migration

            Every node payload must declare `payload_schema_id` and `payload_schema_version`.

Unknown causality and pending edges cannot satisfy promotion. Promotion into `forge-contract-core` requires a future governed RFC.

---

            # Verification

            **Document version:** 2.0 (2026-06-22) - canonical compliance migration

            The README names the test command:

```bash
cd contracts/forge_lineage
python -m pytest tests/ -v
```

Run the self-contained schema, fixture, SDK, and documentation checks before changing lineage contracts or adapters:

```bash
python -m pytest tests/ -v -m "not integration"
CHECK=1 bash doc/system/BUILD.sh
```

The cross-repository scenarios are marked `integration`. They require a compatible
`dataforge-Local` checkout and are intentionally skipped unless its path is supplied:

```bash
DATAFORGE_LOCAL=/path/to/dataforge-Local python -m pytest tests/ -v -m integration
```

## Which CI runs for which change

A change to documentation runs the Documentation CI and no code CI.
A change to any other file runs the code CI.
A change to both runs both.
No workflow runs on a schedule.

The code workflow `.github/workflows/checks.yml` (job `unit-and-docs`) uses a workflow-level `paths` filter on `push` and on `pull_request`:

```yaml
paths:
  - '**'
  - '!docs/**'
  - '!doc/**'
  - '!**/*.md'
```

The last matching pattern wins.
A change to `.github/workflows/**` is code, so it runs the code CI.
No test, SDK module or script reads a file under `doc/` or a Markdown file.
The SDK `pyproject.toml` names no README.
Therefore no documentation path needs a re-include.
The job `unit-and-docs` also builds `doc/LINSYSTEM.md`, and that step still runs on every code change.
If a test or script starts to read a documentation path, add that path as a re-include in the same change.

The Documentation CI is `.github/workflows/documentation.yml`.
It runs on a change under `docs/`, under `doc/`, to any `*.md` file, or to its own workflow file.
It runs `CHECK=1 bash doc/system/BUILD.sh`, fails if `git diff --exit-code -- doc` shows a difference, and runs `git diff --check`.
`BUILD.sh` does not read `CHECK`. The `git diff --exit-code` step is the real staleness check.

This repository has no secret scan workflow.
If a secret scan is added, it must run on every change and must not use a path filter.

Warning: do not add a required status check on a path-filtered workflow.
The check stays pending forever when the filter skips the workflow, and the merge stays blocked.

---

# Appendices

**Document version:** 2.0 (2026-06-22) - canonical compliance migration

Important surfaces include `schemas/payloads/`, `fixtures/valid/`, `fixtures/invalid/`, `tests/`, and `sdk/forge_lineage_sdk/adapters/`.
