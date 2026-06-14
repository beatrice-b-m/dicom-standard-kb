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
- `trace`

Confirm the v2 public surfaces are covered by offline tests:

- PS3.5 encoding: `lookup_vr`, `lookup_transfer_syntax`, and
  `explain_encoding_rule`.
- PS3.10/PS3.18 media and web services: `lookup_media_type` and
  `lookup_dicomweb_transaction`.
- PS3.16 content mapping: `lookup_sr_template`, `lookup_context_group`, and
  `lookup_code_meaning`.
- Contextual value terms: `lookup_enumerated_values` and
  `lookup_defined_terms` with deterministic IOD, SOP Class, module, or macro
  contexts.
- Cited text fallback: `retrieve_standard_text` for prose-only PS3.7, PS3.8,
  and PS3.10 rules.
- Agent regression: at least 100 prompt cases, with deterministic expected
  tool traces before answer synthesis.

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
- `parse_warnings_by_part`
- `source_refs`

For v2 builds, also confirm parser-warning and unresolved-reference metrics
can be inspected per parsed standard part:

- PS3.5 encoding tables and transfer syntax details.
- PS3.7 selected message/service behavior tables.
- PS3.8 selected networking behavior tables.
- PS3.10 file meta and media storage tables.
- PS3.16 SR template, context group, and coded concept tables.
- PS3.18 DICOMweb transaction and media type tables.

For official editions, set explicit quality-gate thresholds or use
`--allow-gate-failures` only while establishing a new baseline.

## V2 Official-Edition Goldens

Before declaring v2 release-ready, run official-edition goldens against a
locally built concrete edition. The representative set must include:

- PS3.5 transfer syntax lookup for implicit, explicit, deflated, and
  encapsulated transfer syntaxes.
- PS3.10 media-type or file-format fallback behavior.
- PS3.16 SR template, context group, and code lookup behavior.
- PS3.18 DICOMweb route lookup and media negotiation behavior.
- Contextual enumerated value or defined term lookup with a deterministic
  IOD, SOP Class, module, or macro context.

The strict release gate is separate from smoke coverage. It requires a local
official KB with DocBook artifacts for PS3.3, PS3.4, PS3.5, PS3.6, PS3.7,
PS3.8, PS3.10, PS3.16, and PS3.18; nonzero rows for every v2 semantic table;
and citation-preserving DocBook structure rows for each required part.

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
make test-dicom-release
make test-dicom-current
```

`make test-dicom-integration` is smoke coverage for whatever official KB is
available locally. `make test-dicom-release` is the strict v2 release gate and
must fail rather than skip when a partial official KB is missing required v2
parts or semantic rows. If these checks are skipped, record the missing local
prerequisite in the release notes, such as an absent official-edition cache or
disabled current network resolution.

## Distribution Audit

Confirm the release artifacts remain code-only:

- No official DICOM XML, PDF, HTML, target database, generated full database,
  full-text index, vector index, or bulk parsed JSON is committed or packaged.
- No standalone PS3.16 terminology dump, context-group export, or coded
  concept export is committed or packaged.
- Docker and PyPI artifacts require users to fetch and build official
  editions locally.
- `README.md`, `NOTICE`, generated manifests, and `/about` metadata continue
  to carry the DICOM/NEMA non-affiliation and trademark notice.
