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
| `docbook/` | Parse generic XML structure, tables, variable lists, cross references, and text. |
| `parsers/part*.py` | Interpret a specific part's structures as canonical records. |
| `ir/models.py`, `ir/validators.py` | Canonical record types and identifier rules. |
| `db/models.py`, `db/migrations/` | SQLite connections and ordered, idempotent schema scripts. |
| `db/importers/` | Persist records in domain transactions; extract attribute value terms. |
| `db/repositories/` | Edition-filtered SQL lookups, joined records, and row conversion. |
| `build.py` | Run each part's parse and import as a step, log gaps, publish a completed database. |
| `query/resolver/` | Domain query responses behind the stable Python import surface. |
| `query/graph.py`, `query/conditions.py` | Context traversal, macro expansion, and bounded condition reasoning. |
| `query/answer_contracts.py`, `query/citations.py` | Resolver result shapes and source refs. |
| `query/markdown.py` | Render every answer as compact markdown with one source line. |
| `cli/` | Command modules, shared options, and invocation-scoped configuration. |
| `mcp/` | Tool names, dispatch, registration, and stdio adapter. |

The public imports `dicom_kb.query.resolver`, `dicom_kb.db.repositories`, and
`dicom_kb.db.importers` re-export supported operations. Internal modules import
specific siblings rather than their own package facade to avoid cycles.
Keep SQL in storage modules and domain reasoning in query modules; CLI and MCP
adapt arguments and print the markdown from `query/markdown.py`.

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
