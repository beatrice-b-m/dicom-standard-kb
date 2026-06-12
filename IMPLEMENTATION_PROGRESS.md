# Implementation Progress

Last updated: 2026-06-12

## Current stopping point

Stopped after completing the PS3.6 query/CLI lookup work order. The repository
now has a working offline foundation through:

1. Work Order A: repository/build/legal scaffold.
2. Work Order B: local source acquisition primitives.
3. Work Order C: DocBook parser core.
4. Work Order D: PS3.6 data element and UID registry parser.
5. Work Order G, first v1 slice: SQLite schema, migration runner,
   transactional PS3.6 import, and repository lookups.
6. Work Order G, second v1 slice: public response envelopes,
   SQLite-backed PS3.6 query resolvers, and `dicom-kb lookup tag` /
   `dicom-kb lookup uid`.

## Completed commits

- `b02f0b5 chore(project): scaffold Python package and legal docs`
- `3aba19a feat(sources): add edition manifests and artifact registry`
- `39e9556 feat(docbook): parse sections tables and xrefs`
- `2e60149 feat(parsers): parse PS3.6 registries`
- `2eb2d22 feat(db): import PS3.6 records into SQLite`
- `c590570 docs(progress): record v1 implementation stopping point`
- `e01b7e0 docs(progress): record untracked gaps and broken placeholder targets`
- `9172252 feat(query): add PS3.6 lookup envelopes`

## Verification at stop

The following offline checks passed after the database work order:

```bash
make lint
make typecheck
make test
```

Observed test count: 27 passing tests.

## Implemented behavior

- Python 3.12 package scaffold managed by `uv`.
- Required legal notice in README, NOTICE, docs, and shared metadata.
- Offline CI, Dockerfile, Makefile, lint, typecheck, and pytest targets.
- Concrete edition resolution with safe handling of mutable `current`.
- SHA-256 helpers and immutable source manifests.
- Local artifact registration into the external cache layout.
- Namespace-aware DocBook section, table, span, xref, and include-row parsing.
- Zero-width character removal and normalized text helpers.
- PS3.6 data element parsing with tag normalization, retired markers, malformed
  row warnings, and range-tag detection.
- PS3.6 UID registry parsing with UID validation, retired markers, malformed
  row warnings, and zero-width keyword cleanup.
- SQLite schema for editions, artifacts, source refs, data elements, and UID
  registry entries.
- Transactional PS3.6 import with rollback on uniqueness failures.
- Repository lookup by tag, keyword, UID value, UID keyword, and concrete tags
  matching range rows.
- Shared query response envelope contracts with refs, warnings, legal notice,
  and trace metadata.
- `lookup_data_element` resolver with tag/keyword parity, malformed tag
  validation errors, not-found responses, retired-element reporting, and
  range-match warnings.
- `lookup_uid` resolver with UID value/keyword lookup, validation errors for
  malformed UID-shaped input, not-found responses, and retired UID reporting.
- CLI commands `dicom-kb lookup tag` and `dicom-kb lookup uid` that read an
  explicit local SQLite database path and emit JSON envelopes.

## Not yet implemented

- Official network fetch URL discovery for `current` edition metadata.
- CLI commands wired to fetch and build workflows.
- CLI default cache/database discovery; lookup currently requires `--db`.
- PS3.3 IOD/module/macro parser.
- PS3.4 SOP class parser.
- General citation builder beyond direct source-ref conversion.
- MCP server tool surface.
- Agent regression harness.
- Raw table IR persistence (SYSTEM_SPECS.md section 10.3): the DocBook layer
  builds table IR in memory, but the import stores only normalized
  `data_element`/`uid_registry_entry` rows. No `doc_node`, `xref`, or JSON
  table-snapshot storage exists yet, so parser bugs cannot be investigated
  without reparsing the source.
- Spec-mandated repository directories and files: `schemas/` (the four JSON
  Schema files; Python response-envelope contracts exist, but JSON Schema
  files have not been generated/committed yet),
  `tests/fixtures_synthetic/`, `tests/fixtures_minimal_attributed/`,
  `tests/agent_regression/`, `examples/`, and `docbook/variablelists.py`.

## Known broken placeholders

These Makefile targets are forward declarations that currently fail or no-op
if run:

- `make test-integration` points at `tests/integration_requires_dicom_download/`,
  which does not exist yet (pytest exits with a collection error).
- `make run-mcp` invokes `dicom-kb mcp serve`, a CLI command that does not
  exist yet.
- `make ingest-fixture` runs the `build-fixture` placeholder, which only
  prints a not-implemented message.

## Recommended next work order

Resume the spec sequence with PS3.3 IOD/module/macro parsing:

1. Add `docbook/variablelists.py` if needed by PS3.3 table prose parsing.
2. Implement a PS3.3 IOD/module/macro parser focused on the CT Image IOD
   fixture and Include-row preservation.
3. Extend the SQLite schema/importer for IODs, modules, macros,
   `iod_module_use`, and `attribute_use`.
4. Add focused synthetic/minimal attributed fixtures and tests for CT Image
   modules and macro include rows.

Before MCP work, also add the spec-mandated JSON Schema files for the current
response envelope contracts.
