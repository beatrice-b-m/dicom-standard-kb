# dicom-standard-kb

Build a local SQLite knowledge base from the current DICOM Standard, fetched
from NEMA, then query it offline through an MCP server or the CLI. Answers are
compact markdown that ends with the part and table they come from.

This project is a builder and query layer. It does not redistribute the DICOM
Standard, official source artifacts, or a prebuilt knowledge base.

[Developer guide](docs/development.md)

## Status

Every section and table of all 20 published parts can be searched and read
as markdown, with each cross reference kept as its target (`See Section
C.7.3.1.1.1`, `BCID 7010`). Structured lookups (data elements, UIDs, IODs,
modules, SOP Classes, context groups) cover PS3.3, PS3.4, PS3.5, PS3.6, PS3.10,
PS3.16, and PS3.18. A warning appears only when an answer is missing something
the source has.

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
uv run dicom-kb iod "CT Image" --db /tmp/dicom-kb-fixture.sqlite
```

The fixture demonstrates API behavior; it is not official DICOM content.

## Build from official sources

`fetch` downloads the current edition's DocBook for every part from
dicom.nema.org (about 125 MB); everything after that works offline:

```bash
uv run dicom-kb fetch
uv run dicom-kb build
uv run dicom-kb element Modality
uv run dicom-kb iod "CT Image" --expand
uv run dicom-kb module "General Series"
uv run dicom-kb search "undefined length sequence delimitation"
uv run dicom-kb read "PS3.5 7.5.2"
```

`element` lists the modules and IODs that use a tag or keyword (add `--iod` for
where it sits in one IOD). `iod` takes an IOD name or SOP Class name or UID and
lists its modules; `--expand` turns that into the full attribute checklist.
`module` takes a module or macro name or table (`Table 10-2`). Each macro is
expanded the first time it appears and marked "listed above" after that.

`read` takes a section, table, annex, CID or TID (`PS3.3 Table C.7-5a`,
`Annex A`, `CID 7010`) and pages long answers at about 4k tokens.

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

Its `dicom_element`, `dicom_iod`, `dicom_module`, `dicom_search` and
`dicom_read` tools do the same as the matching commands.

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
