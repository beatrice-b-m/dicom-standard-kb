# dicom-standard-kb

Build a local SQLite knowledge base from the current DICOM Standard, fetched
from NEMA, then query it offline through an MCP server or the CLI. Answers are
compact markdown that ends with the part and table they come from.

This project is a builder and query layer. It does not redistribute the DICOM
Standard, official source artifacts, or a prebuilt knowledge base.

[Developer guide](docs/development.md)

## Status

The parser surface covers PS3.3, PS3.4, PS3.5, PS3.6, PS3.10, PS3.16, and
PS3.18. Selected PS3.7 and PS3.8 prose is available through cited text retrieval.
Structured coverage is bounded; a warning appears only when an answer is
missing something the source has.

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
uv run dicom-kb build-fixture --db /tmp/dicom-kb-fixture.sqlite --force
uv run dicom-kb lookup tag Modality --db /tmp/dicom-kb-fixture.sqlite
```

The fixture demonstrates API behavior; it is not official DICOM content.

## Build from official sources

`fetch` downloads the current edition's DocBook from dicom.nema.org (about
100 MB); everything after that works offline:

```bash
uv run dicom-kb fetch
uv run dicom-kb build
uv run dicom-kb lookup tag Modality
```

Files go under `~/.cache/dicom-standard-kb/`, with the database at
`db/<edition>.sqlite`. Commands use the newest fetched or built edition unless
you pass `--edition`; use `--cache-dir` or `--db` for other locations. A
rebuild requires `--force`, and a failed build leaves the previous database in
place. The build never stops on a gap in the source: it logs each one to
`db/<edition>.gaps.txt` and prints the count per part.

For an MCP client, add the stdio server as one config entry:

```bash
uv run --extra mcp dicom-kb mcp serve
```

The [documentation website](https://dicom-standard-kb-docs.beatricebm.workers.dev/)
describes the earlier JSON tools and is out of date until the rebuild finishes.

## Development

```bash
make install
make check
```

See the [developer guide](docs/development.md) for the code map, extension
workflow, and test layers.

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
