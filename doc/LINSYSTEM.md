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

---

# Appendices

**Document version:** 2.0 (2026-06-22) - canonical compliance migration

Important surfaces include `schemas/payloads/`, `fixtures/valid/`, `fixtures/invalid/`, `tests/`, and `sdk/forge_lineage_sdk/adapters/`.
