# Release checklist

Run from a clean source checkout. A passing offline suite alone does not establish
official-edition parser coverage.

## Local verification

```bash
make install
make check
uv build
```

Build a synthetic fixture into a temporary cache, then verify its manifest and
database. Inspect metrics, warnings, citations, and representative query output.
Keep the synthetic cache separate from official-edition release checks.

```bash
uv run dicom-kb build-fixture --edition 2026b --cache-dir /tmp/dicom-kb-release-fixture
uv run dicom-kb verify --edition 2026b --cache-dir /tmp/dicom-kb-release-fixture
```

Exercise changed CLI/Python/MCP contracts and agent regression cases. Check
configuration precedence and successful/failed quality gates when changing
build or config behavior. Use explicit thresholds for official builds;
`--allow-gate-failures` is for establishing a baseline, not bypassing release review.

## Official-edition checks

Fetch and build a concrete official edition in an external cache. Set
`DICOM_KB_CACHE_DIR` and `DICOM_KB_TEST_EDITION` to that cache and edition:

```bash
make test-dicom-integration
make test-dicom-release
make test-dicom-current
```

The integration target is smoke coverage. The release target fails on missing prerequisites and requires all
baseline parts and positive semantic examples; its required tables, parts, and
cases live in `tests/integration_requires_dicom_download/release_requirements.py`
and `test_release_goldens.py`. Update those executable requirements with new
required entities. The current-edition check requires network access.
Record the edition, manifest digest, gate results, and any missing prerequisites.
Do not describe skipped or unavailable release checks as passed.

## Distribution and documentation

- Inspect wheels, source distributions, and Docker inputs for official artifacts,
  generated databases/indexes, bulk JSON, and standalone PS3.16 terminology exports.
  Preserve `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.md`, and runtime notices.
- The wheel contains the Python package and migrations. `build-fixture` is a
  source-checkout workflow; do not depend on test fixtures in installed-wheel checks.
- Verify the package version agrees with `metadata.__version__` and update both
  when releasing. Record externally visible behavior changes in release notes.
- Submit corresponding public documentation changes to the
  [documentation repository](https://github.com/beatrice-b-m/dicom-standard-kb-docs).
  Follow its instructions to select the stable release, update `docs-source.json`
  and affected pages together, validate, and review the preview before merge.
