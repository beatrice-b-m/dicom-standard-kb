# Release Checklist

Run these checks before cutting a release from a clean worktree.

## Offline Gates

```bash
make lint
make typecheck
make test
```

Confirm representative query envelopes include:

- `classification`
- `parse_confidence`
- `refs`
- `warnings`
- `notice`
- `trace`

## Build and Verification Gates

```bash
dicom-kb build-fixture --edition 2026b --force
dicom-kb verify --edition 2026b
```

Confirm build output and build metadata include aggregate `metrics` with:

- `include_rows_resolved`
- `include_rows_unresolved`
- `xrefs_total`
- `xrefs_unresolved`
- `parse_warnings`
- `source_refs`

For official editions, set explicit quality-gate thresholds or use
`--allow-gate-failures` only while establishing a new baseline.

## Config Compatibility

Validate both common profile shapes:

```yaml
dicom_kb:
  edition: 2026b
  artifact_dir: /tmp/dicom-standard-kb
  database_url: sqlite:////tmp/dicom-kb.sqlite
  require_citations: true
```

```yaml
dicom_kb:
  edition: current
  artifact_dir: /tmp/dicom-standard-kb
  allow_network_fetch: true
  require_edition_pin: true
  use_synthetic_fixtures_only: false
```

Commands must still work without a config file, and CLI flags must override
profile values.

## Local Official-Edition Gates

After fetching and building a local official edition:

```bash
make test-dicom-integration
make test-dicom-current
```

If these checks are skipped, record the missing local prerequisite in the
release notes, such as an absent official-edition cache or disabled current
network resolution.
