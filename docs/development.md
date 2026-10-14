# Working in this repository

This guide describes the current checkout. Public tutorials and API reference
belong in the [documentation repository](https://github.com/beatrice-b-m/dicom-standard-kb-docs),
whose `docs-source.json` pins the state it documents. Coordinate behavioral
changes with that site's next release synchronization; do not update its pin
for an unreleased refactor.

## Setup and checks

Use Python 3.12+ and `uv` from the repository root:

```bash
make install
make check
make format
```

`install` synchronizes the locked runtime, MCP, and development dependencies.
`check` runs lint, formatting verification, strict mypy, and offline tests.
`format` applies the shared Ruff style. Commit dependency declarations and
`uv.lock` together; use `uv lock` when intentionally changing dependencies.

For focused work, run the relevant existing tests:

```bash
uv run --frozen --all-extras --dev pytest tests/unit/test_query_resolver.py
```

Tests under `tests/unit/` use synthetic fixtures and temporary databases.
`tests/integration_requires_dicom_download/` runs smoke checks against a KB
built locally from the current NEMA edition (`dicom-kb fetch` then
`dicom-kb build`). It uses the newest build in `DICOM_KB_CACHE_DIR` unless
`DICOM_KB_TEST_EDITION` names one; run it with `make test-integration`.
Always validate against the current edition from NEMA, never an older mirror.

## Code map

Paths below are relative to `src/dicom_kb/`.

| Area | Responsibility |
| --- | --- |
| `sources/` | Fetch the current DocBook release from NEMA or register local copies; write the manifest. |
| `docbook/` | Parse generic XML structure and tables; `targets.py` indexes every labelled target across parts and `markdown.py` renders DocBook as markdown with each reference resolved to its label. |
| `parsers/part*.py` | Interpret a specific part's structures as canonical records. |
| `ir/models.py`, `ir/validators.py` | Canonical record types and identifier rules. |
| `db/models.py`, `db/migrations/` | SQLite connections and ordered, idempotent schema scripts. |
| `db/importers/` | Persist records in domain transactions; extract attribute value terms. |
| `db/repositories/` | Edition-filtered SQL lookups, joined records, and row conversion. |
| `build.py` | Run each part's parse and import as a step, log gaps, publish a completed database. |
| `query/resolver/` | Domain query responses behind the stable Python import surface; `standard.py` reads and searches the stored sections and tables; `identifiers.py` lets `dicom_read` answer a UID or VR; `objects.py` answers `dicom_element`, `dicom_iod` and `dicom_module`, expanding each macro once; `values.py` answers `dicom_values` and `codes.py` answers `dicom_code`. |
| `query/answer_contracts.py` | The resolver response and its source refs. |
| `query/markdown.py` | Render every answer as compact markdown with one source line. |
| `cli/` | Command modules, shared options, and invocation-scoped configuration. |
| `mcp/` | Tool names, dispatch, registration, and stdio adapter. |

The public imports `dicom_kb.query.resolver`, `dicom_kb.db.repositories`, and
`dicom_kb.db.importers` re-export supported operations. Internal modules import
specific siblings rather than their own package facade to avoid cycles.
Keep SQL in storage modules and domain reasoning in query modules; CLI and MCP
adapt arguments and print the markdown from `query/markdown.py`.

## Standard text

The build parses every part twice: once to index every labelled target
(section, table, figure, CID, TID, bibliography and glossary entry) across all
parts, then again to render each section and table as markdown against that
index, so `<xref>` and `<olink>` read as `Section C.7.3.1.1.1` or `PS3.5
Section 7.5.2` instead of nothing. A reference whose target no part defines is
logged as a gap. Each section's markdown holds a `[[table:<id>]]` placeholder
where its tables go; `dicom_read` swaps the table markdown in, renders a
subtree whole when it fits in a page and otherwise lists its subsections.
Parsers read cell text as the plain-text form of the same markdown, so
attribute descriptions keep their references too. `doc_node_fts` indexes
titles and own text (tables separately) for `dicom_search`, which ranks
normative nodes before informative annexes and examples.

## Transfer syntaxes and VRs

`parsers/part05_encoding.py` reads each transfer syntax from the PS3.5 Annex A
section that names its UID (notes excluded). That section states the Data
Set's VR style and byte order, or takes them from the section it says to
encode by first (A.5 from A.2) or from its parent (A.4.1 from A.4). Pixel Data
is Encapsulated when the rules say "shall be Encapsulated Format", referenced
when they replace it with the Pixel Data Provider URL, and Native otherwise.
The DICOM-RTV syntaxes take their metadata encoding from PS3.22 7.1. A current
UID with no Annex A section is logged as a gap; a retired one is answered as no
longer specified. VRs are not parsed into a table: `dicom_read` takes the row
from Table 6.2-1's stored markdown and the header layout from the titles of
Tables 7.1-1 and 7.1-2.

## Invariants and extension workflow

- Answers are judged by whether they give an agent what the standard says in
  fewer tokens than the source. Do not add envelope fields, confidence labels or
  caveats; a warning belongs in an answer only when something it needs is
  missing. Ambiguous matches return candidates instead of guesses.
- Repeating tags, conditional requirements, macro includes, and contextual value
  terms need explicit regression cases. Enumerated values and defined terms
  stay distinct. A null effective type is not permission to infer a requirement.
- Prefer synthetic, minimal DocBook fixtures under `tests/fixtures_synthetic/`.
  Include official-shaped table layouts, malformed rows, and unresolved links
  relevant to the parser change. Attributed excerpts follow the policy in
  `tests/fixtures_minimal_attributed/README.md`.
- For a new entity, update IR, a numbered migration, its importer and repository,
  resolver, CLI/MCP surfaces as appropriate, and affected contract tests.
  Add build metrics when introducing a semantic table.
- Migrations are currently idempotent scripts, not a general upgrade framework.
  Keep scripts safe to reapply and update `build.SCHEMA_VERSION` when adding one.
  Validate schema and import behavior using the existing migration/build tests.
- Importers own their transactions. The builder runs each part's parse and
  import as a step: a data-shaped failure (bad row, dangling link) rolls back
  that step, is logged as a gap, and the build continues. Storage and I/O errors
  abort it. All work is staged on the target filesystem and published only when
  the build completes, so an aborted build leaves the live database untouched.
- Use `db.models.read_sqlite()` when a query entrypoint owns its connection.
  Resolvers accept caller-owned connections. `connect_sqlite()` callers must
  close their connections; SQLite's native context manager only handles transactions.
- Preserve CLI > environment > config > default precedence, falling back to
  the newest edition in the cache. Keep invocation settings in `typer.Context`,
  not module globals.

## Documentation and distribution

Keep local docs limited to this guide, repository instructions, legal notices, and short instructions beside executable examples
or fixtures. Do not duplicate the site's user guides, API tables, or coverage
catalog. Tests should check executable contracts, not historical progress prose.

Completed implementation/remediation plans and the old system specification are
available in Git history before the documentation cleanup; they are historical
context, not the current contract. Use `git log --all -- <path>` to locate them.
Track new proposals and investigations in issues or pull requests, and preserve
lasting implementation decisions beside the affected code or in this guide.

Releases contain original code, tests, and synthetic fixtures only.
Never commit or package official artifacts, full databases, full-text/vector
indexes, or bulk parsed exports. PS3.16 terminology, context groups, and coded
concepts follow the same restriction. Retain [LICENSE](../LICENSE),
[NOTICE](../NOTICE), and [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
