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
