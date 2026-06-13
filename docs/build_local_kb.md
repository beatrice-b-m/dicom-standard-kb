# Build a Local Knowledge Base

```bash
dicom-kb fetch --edition current
dicom-kb build --edition 2026b
dicom-kb verify --edition 2026b
dicom-kb lookup tag Modality --edition 2026b
```

`fetch` resolves `current` from the official DICOM current release metadata
before writing a manifest. By default, official fetch downloads the DocBook
XML parts used by the implemented v1 parsers: PS3.3, PS3.4, and PS3.6.

Concrete historical editions are fetched from the official DICOM archive
directory instead of the mutable current-release directory:

```bash
dicom-kb fetch --edition 2025e --part PS3.6
```

To restrict the official fetch to one or more parts:

```bash
dicom-kb fetch --edition current --part PS3.6
```

To cache additional official formats for citation verification or local
inspection, repeat `--format`:

```bash
dicom-kb fetch --edition current --part PS3.6 --format docbook_xml --format pdf
dicom-kb fetch --edition current --part PS3.6 --format html --format targetdb
```

Supported official formats are `docbook_xml`, `pdf`, `html`, `chtml`, and
`targetdb`. The SQLite build reads the `docbook_xml` artifacts and preserves
the other artifact checksums in the manifest/build metadata.

By default, `--format chtml` downloads the part entry page. To mirror the full
per-part CHTML directory for local inspection, add `--mirror-chtml-tree`:

```bash
dicom-kb fetch --edition current --part PS3.6 --format chtml --mirror-chtml-tree
```

Local fixture or pre-downloaded XML registration is still available:

```bash
dicom-kb fetch --edition 2026b --docbook-xml PS3.6=/path/to/part06.xml
```

Generated databases live in the local cache and are not committed.

## Verification

After fetching and building, verify the local cache:

```bash
dicom-kb verify --edition 2026b
```

The verifier recomputes cached artifact checksums from the edition manifest
and checks database build metadata when a database for the edition is present.
Use `--db /path/to/file.sqlite` when the database is outside the default cache
location.

## Build Metrics and Quality Gates

`build` and `build-fixture` emit a `metrics` object with aggregate ingestion
quality counters, including resolved and unresolved include rows, resolved and
unresolved cross references, parse warnings, and source-ref counts. The same
metrics are persisted in build metadata.

Use quality gates to fail a build when a local threshold is exceeded:

```bash
dicom-kb build --edition 2026b \
  --max-unresolved-xref-rate 0.05 \
  --max-unresolved-include-rate 0.0 \
  --max-parse-warnings 0
```

Add `--allow-gate-failures` to emit warnings but keep the command exit code at
zero while establishing thresholds for a new edition.

## Configuration Profiles

All major command paths accept a root `--config` option with a top-level
`dicom_kb` YAML mapping:

```yaml
dicom_kb:
  edition: 2026b
  artifact_dir: /data/dicom-standard-kb
  database_url: sqlite:////data/dicom-standard-kb/db/2026b.sqlite
  allow_network_fetch: false
  require_citations: true
  require_edition_pin: true
```

CLI flags override environment variables, which override config values, which
override built-in defaults.

## Release Checks

The default offline release checks are:

```bash
make lint
make typecheck
make test
```

Run local official-edition integration checks only after an official edition
has been fetched and built in the local cache:

```bash
make test-dicom-integration
make test-dicom-current
```
