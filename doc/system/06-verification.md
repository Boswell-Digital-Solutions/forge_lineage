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
