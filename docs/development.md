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
uv run --frozen --all-extras --dev pytest tests/agent_regression
```

Tests under `tests/unit/` use synthetic fixtures and temporary databases.
`tests/agent_regression/` checks deterministic tool routing and evidence scoring;
external harness execution is opt-in and mocked in ordinary tests.
`tests/integration_requires_dicom_download/` uses a locally built official KB.
Set `DICOM_KB_CACHE_DIR` and `DICOM_KB_TEST_EDITION` to choose its cache and edition,
then run `make test-dicom-integration`. The current-edition network check and
strict release gate are separate opt-ins; see [release checks](release_checklist.md).

## Code map

Paths below are relative to `src/dicom_kb/`.

| Area | Responsibility |
| --- | --- |
| `sources/` | Resolve editions, acquire artifacts, record checksums, verify provenance. |
| `docbook/` | Parse generic XML structure, tables, variable lists, cross references, and text. |
| `parsers/part*.py` | Interpret a specific part's structures as canonical records. |
| `ir/models.py`, `ir/validators.py` | Canonical record types and identifier rules. |
| `db/models.py`, `db/migrations/` | SQLite connections and ordered, idempotent schema scripts. |
| `db/importers/` | Persist records in domain transactions; extract attribute value terms. |
| `db/repositories/` | Edition-filtered SQL lookups, joined records, and row conversion. |
| `build.py` | Order parsing/import, aggregate metrics, check gates, publish a completed database. |
| `query/resolver/` | Domain query responses behind the stable Python import surface. |
| `query/graph.py`, `query/conditions.py` | Context traversal, macro expansion, and bounded condition reasoning. |
| `query/answer_contracts.py`, `query/citations.py` | Shared response shapes, evidence classification, and citation assembly. |
| `cli/` | Command modules, shared options, and invocation-scoped configuration. |
| `mcp/` | Tool schemas, dispatch, registration, and stdio adapter. |
| `eval/` | Prompt cases, expected traces, execution, and scoring. |

The public imports `dicom_kb.query.resolver`, `dicom_kb.db.repositories`, and
`dicom_kb.db.importers` re-export supported operations. Internal modules import
specific siblings rather than their own package facade to avoid cycles.
Keep SQL in storage modules and domain reasoning in query modules; CLI and MCP
adapt arguments and serialize the shared response contract.

## Invariants and extension workflow

- Facts and relationships retain concrete `edition_id` and source references.
  Preserve citations, warnings, classification, parse confidence, and trace data.
  Ambiguous matches return candidates or explicit uncertainty instead of guesses.
- Repeating tags, conditional requirements, macro includes, and contextual value
  terms need explicit regression cases. Enumerated values and defined terms
  stay distinct. A null effective type is not permission to infer a requirement.
- Prefer synthetic, minimal DocBook fixtures under `tests/fixtures_synthetic/`.
  Include official-shaped table layouts, malformed rows, and unresolved links
  relevant to the parser change. Attributed excerpts follow the policy in
  `tests/fixtures_minimal_attributed/README.md`.
- For a new entity, update IR, a numbered migration, its importer and repository,
  resolver, CLI/MCP surfaces as appropriate, and affected contract tests.
  Keep `schemas/` aligned with Pydantic response models. Add build metrics and
  release requirements when introducing a required semantic table.
- Migrations are currently idempotent scripts, not a general upgrade framework.
  Keep scripts safe to reapply and update `build.SCHEMA_VERSION` when adding one.
  Validate schema and import behavior using the existing migration/build tests.
- Importers own their transactions. The builder stages all work on the target
  filesystem and publishes only after successful quality checks. Exceptions and
  failed gates leave the live database untouched; `--allow-gate-failures` opts
  into publishing a completed build with warnings.
- Use `db.models.read_sqlite()` when a query entrypoint owns its connection.
  Resolvers accept caller-owned connections. `connect_sqlite()` callers must
  close their connections; SQLite's native context manager only handles transactions.
- Preserve CLI > environment > config > default precedence. Keep invocation
  settings in `typer.Context`, not module globals. Several profile fields are
  accepted metadata rather than enforced policies; inspect call sites before
  claiming a setting changes runtime behavior.

## Documentation and distribution

Keep local docs limited to this guide, the release checklist, repository
instructions, legal notices, and short instructions beside executable examples
or fixtures. Do not duplicate the site's user guides, API tables, or coverage
catalog. Tests should check executable contracts, not historical progress prose.

Completed implementation/remediation plans and the old system specification are
available in Git history before the documentation cleanup; they are historical
context, not the current contract. Use `git log --all -- <path>` to locate them.
Track new proposals and investigations in issues or pull requests, and preserve
lasting implementation decisions beside the affected code or in this guide.

Releases contain original code, schemas, tests, and synthetic fixtures only.
Never commit or package official artifacts, full databases, full-text/vector
indexes, or bulk parsed exports. PS3.16 terminology, context groups, and coded
concepts follow the same restriction. Retain [LICENSE](../LICENSE),
[NOTICE](../NOTICE), and [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
