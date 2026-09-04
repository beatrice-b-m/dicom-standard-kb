# dicom-standard-kb

Build a local, edition-pinned SQLite knowledge base from official DICOM
Standard artifacts, then query it through the CLI, Python, or MCP. Lookups
return structured facts, citations, edition metadata, and explicit uncertainty.

This project is a builder and query layer. It does not redistribute the DICOM
Standard, official source artifacts, or a prebuilt knowledge base.

[Documentation](https://dicom-standard-kb-docs.beatricebm.workers.dev/) ·
[Developer guide](docs/development.md) ·
[Examples](examples/README.md)

## Status

The parser surface covers PS3.3, PS3.4, PS3.5, PS3.6, PS3.10, PS3.16, and
PS3.18. Selected PS3.7 and PS3.8 prose is available through cited text retrieval.
Structured coverage is bounded; inspect response warnings and citations.

## Install

Requires Python 3.12 or newer. From a source checkout, use `uv`:

```bash
git clone https://github.com/beatrice-b-m/dicom-standard-kb.git
cd dicom-standard-kb
make install
uv run dicom-kb --help
uv run dicom-kb doctor
```

For a standalone CLI installation from the checkout:

```bash
uv tool install .
```

Include MCP support with `uv tool install '.[mcp]'`. The installed executable
can be used without `uv run`. The `build-fixture` command requires a source
checkout because synthetic test fixtures are not bundled in the wheel.

## Try the synthetic fixture

From the source checkout, build a tiny, synthetic database without downloading
DICOM content:

```bash
uv run dicom-kb build-fixture --edition 2026b \
  --db /tmp/dicom-kb-fixture.sqlite --force
uv run dicom-kb lookup tag Modality --edition 2026b \
  --db /tmp/dicom-kb-fixture.sqlite
```

The fixture demonstrates API behavior; it is not official DICOM content.

## Build from official sources

Network access is needed to fetch official artifacts. Resolve `current` to a
concrete edition, then use the edition reported by `fetch`:

```bash
uv run dicom-kb fetch --edition current
uv run dicom-kb build --edition <concrete-edition>
uv run dicom-kb verify --edition <concrete-edition>
uv run dicom-kb lookup tag Modality --edition <concrete-edition>
```

Artifacts default to `~/.cache/dicom-standard-kb/`, with databases under
`db/<edition>.sqlite`. Use `--cache-dir` or `--db` for explicit locations.
A rebuild requires `--force`; failed builds preserve the previous database.

For an MCP client, launch the stdio server against your local database:

```bash
uv run --extra mcp dicom-kb mcp serve --edition <concrete-edition>
```

The [documentation website](https://dicom-standard-kb-docs.beatricebm.workers.dev/)
contains setup guides, CLI and Python references, configuration, MCP tools,
parser coverage, and limitations. It documents the source state recorded in the
[documentation repository](https://github.com/beatrice-b-m/dicom-standard-kb-docs);
this checkout can contain unreleased changes.

## Development

```bash
make install
make check
```

See the [developer guide](docs/development.md) for the code map, extension
workflow, and test layers, and the [release checklist](docs/release_checklist.md)
for official-edition validation and distribution checks.

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
