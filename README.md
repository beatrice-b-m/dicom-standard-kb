# dicom-standard-kb

`dicom-standard-kb` builds a local, edition-pinned SQLite knowledge base from
official DICOM Standard artifacts. It provides deterministic CLI, Python, and
MCP query surfaces for looking up DICOM data elements, UIDs, IODs, modules,
SOP Classes, defined terms, enumerated values, and cited standard text.

This project is a builder and query layer. It does not redistribute the DICOM
Standard, official source artifacts, or a prebuilt knowledge base.

## Status

The v1 implementation supports local source acquisition, DocBook parsing,
SQLite import, CLI queries, Python resolver APIs, and MCP stdio tools. The
implemented parser surface is focused on PS3.3, PS3.4, and PS3.6.

## Requirements

- Python 3.12 or newer
- `uv` for the recommended source checkout workflow
- Network access only when fetching official DICOM artifacts

Generated artifacts are stored outside the repository under
`~/.cache/dicom-standard-kb/` by default. Use `--cache-dir` on CLI commands to
choose a different location.

## Install from Source

Clone the repository and install all runtime, optional, and development
dependencies:

```bash
git clone <repo-url>
cd dicom-kb
make install
```

The `make install` target runs:

```bash
uv sync --all-extras --dev
```

Verify the CLI:

```bash
uv run dicom-kb --help
uv run dicom-kb doctor
```

To install `dicom-kb` as a standalone `uv` tool from a source checkout, run
the install command from the repository root:

```bash
cd dicom-kb
uv tool install .
```

This puts the `dicom-kb` executable on uv's tool path so it can be launched
without `uv run`:

```bash
dicom-kb --help
dicom-kb doctor
```

For MCP support in the tool install, include the optional extra:

```bash
uv tool install '.[mcp]'
```

If you already installed the CLI-only tool and later need MCP support,
reinstall it with the extra:

```bash
uv tool install --reinstall '.[mcp]'
```

## Quickstart Without Network Access

Use the synthetic fixture to confirm the install and learn the command shape.
The fixture is intentionally small and is not official DICOM Standard content.

```bash
uv run dicom-kb build-fixture \
  --edition 2026b \
  --db /tmp/dicom-kb-fixture.sqlite \
  --force

uv run dicom-kb lookup tag '(0008,0060)' \
  --edition 2026b \
  --db /tmp/dicom-kb-fixture.sqlite
```

Every query command returns a JSON envelope containing the result, citations,
edition metadata, deterministic response classification, parse-confidence
metadata, and a notice to consult the official DICOM Standard for authoritative
text.

## Build a Real Local Knowledge Base

Fetch official artifacts into the local cache, then build SQLite from the
cached DocBook XML. Fetching `current` resolves the mutable current release to
a concrete edition; use the concrete edition reported in the fetch output for
the build and query commands.

```bash
uv run dicom-kb fetch --edition current
uv run dicom-kb build --edition <concrete-edition>
uv run dicom-kb verify --edition <concrete-edition>
```

The default official fetch downloads the v1 DocBook XML parts used by the
builder: PS3.3, PS3.4, and PS3.6.

To fetch a concrete archived edition:

```bash
uv run dicom-kb fetch --edition 2025e
uv run dicom-kb build --edition 2025e
```

To fetch only selected parts or keep additional official formats in the cache:

```bash
uv run dicom-kb fetch --edition current --part PS3.6
uv run dicom-kb fetch --edition current --part PS3.6 \
  --format docbook_xml \
  --format pdf
```

Supported official formats are `docbook_xml`, `pdf`, `html`, `chtml`, and
`targetdb`. SQLite builds read `docbook_xml`; the other formats are cached for
local inspection or citation verification.

If you already have local DocBook XML files, register them instead of
downloading:

```bash
uv run dicom-kb fetch --edition 2026b \
  --docbook-xml PS3.6=/path/to/part06.xml
uv run dicom-kb build --edition 2026b
```

By default, generated databases are written to:

```text
~/.cache/dicom-standard-kb/db/<edition>.sqlite
```

Pass `--db /path/to/file.sqlite` to build or query against an explicit database
path.

Build commands emit ingestion metrics and can enforce quality gates:

```bash
uv run dicom-kb build --edition <edition> \
  --max-unresolved-xref-rate 0.05 \
  --max-unresolved-include-rate 0.0 \
  --max-parse-warnings 0
```

Add `--allow-gate-failures` to keep the command warning-only while tuning
thresholds.

## CLI Usage

Show command help:

```bash
uv run dicom-kb --help
uv run dicom-kb lookup --help
uv run dicom-kb resolve --help
```

Common lookups:

```bash
uv run dicom-kb lookup tag Modality --edition <edition>
uv run dicom-kb lookup tag '(0008,0060)' --edition <edition>
uv run dicom-kb lookup uid ExplicitVRLittleEndian --edition <edition>
uv run dicom-kb lookup iod 'CT Image' --edition <edition>
uv run dicom-kb lookup sop-class 'CT Image Storage' --edition <edition>
```

Graph and context queries:

```bash
uv run dicom-kb iod modules 'CT Image' --edition <edition>
uv run dicom-kb module attributes 'Patient' --edition <edition>
uv run dicom-kb module attributes 'Patient' --edition <edition> --expand-macros
uv run dicom-kb resolve attribute-context Modality \
  --edition <edition> \
  --iod 'CT Image'
uv run dicom-kb context attribute Modality \
  --edition <edition> \
  --iod 'CT Image'
```

Attribute-context resolution reports an `effective_type` when it is
machine-resolvable. For multiple applicable uses it applies the DICOM
lowest-type rule after inspecting matched row descriptions and condition text
for bounded override language such as "shall be Type 1". Conflicting or
ambiguous override prose leaves `effective_type` null and reports source-ref
warnings.

Defined terms, enumerated values, and text search:

```bash
uv run dicom-kb lookup defined-terms Modality --edition <edition>
uv run dicom-kb lookup enumerated-values PatientSex --edition <edition>
uv run dicom-kb search-text 'transfer syntax' --edition <edition> --part PS3.6
uv run dicom-kb retrieve-text PS3.6 <section-or-anchor> --edition <edition>
```

Use a YAML profile to supply shared defaults. CLI flags take precedence over
environment variables, which take precedence over config values:

```yaml
dicom_kb:
  edition: 2026b
  artifact_dir: /tmp/dicom-standard-kb
  database_url: sqlite:////tmp/dicom-kb.sqlite
  require_citations: true
```

```bash
uv run dicom-kb --config ./dicom-kb.yaml lookup tag Modality
```

## MCP Usage

Install the MCP extra, build or point to a local SQLite knowledge base, then
launch the stdio server from an MCP client:

```bash
uv sync --extra mcp
uv run dicom-kb mcp serve --edition <edition>
```

For an explicit database path:

```bash
uv run dicom-kb mcp serve \
  --edition 2026b \
  --db /tmp/dicom-kb-fixture.sqlite
```

The MCP server exposes the same deterministic query operations as the CLI.

## Python Usage

Resolver functions are available from `dicom_kb.query.resolver` for direct
Python use against a SQLite connection.

```bash
uv run python examples/python/lookup_modality.py \
  --db /tmp/dicom-kb-fixture.sqlite \
  --edition 2026b
```

See `examples/python/lookup_modality.py` for a minimal connection and resolver
call.

## Development

Install development dependencies:

```bash
make install
```

Run local checks:

```bash
make lint
make typecheck
make test
```

Integration tests that require a locally built official knowledge base live in
`tests/integration_requires_dicom_download`:

```bash
make test-integration
make test-dicom-integration
make test-dicom-current
```

Useful make targets:

```bash
make ingest-fixture
make run-mcp
```

## Documentation

- `docs/build_local_kb.md`: detailed official fetch and local build workflow
- `docs/release_checklist.md`: release verification checklist
- `docs/architecture.md`: system architecture notes
- `docs/agent_tools.md`: guidance for coding agents using deterministic tools
- `docs/legal.md`: legal and redistribution notes
- `examples/`: CLI, MCP, Python, and validator examples

## Legal Notice

This project is not affiliated with, sponsored by, or endorsed by NEMA, MITA,
or the DICOM Standards Committee. DICOM is a registered trademark of the
National Electrical Manufacturers Association (NEMA). The DICOM Standard is
copyright owned by NEMA. Users should obtain the official current standard
from dicomstandard.org. This project does not provide official DICOM
conformance certification.

The Apache-2.0 license applies to this repository's original source code. It
does not apply to the DICOM Standard or to third-party terminology content
referenced by the DICOM Standard. Do not publish official artifacts, generated
full standard JSON, generated full-text indexes, or generated full knowledge
base databases from this project.
