# Implementation Progress

Last updated: 2026-06-12

## Current stopping point

Stopped after completing the first PS3.3 parser/storage slice. The repository
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
7. Work Order E, first v1 slice: PS3.3 IOD module tables, module attribute
   tables, macro attribute tables, include rows, functional-group usage rows,
   and nested sequence attribute rows parsed from DocBook table IR.
8. Work Order G, third v1 slice: additive SQLite graph schema and
   transactional PS3.3 graph import for IODs, modules, macros, module usage,
   functional-group usage, and attribute-use rows.

## Completed commits

- `b02f0b5 chore(project): scaffold Python package and legal docs`
- `3aba19a feat(sources): add edition manifests and artifact registry`
- `39e9556 feat(docbook): parse sections tables and xrefs`
- `2e60149 feat(parsers): parse PS3.6 registries`
- `2eb2d22 feat(db): import PS3.6 records into SQLite`
- `c590570 docs(progress): record v1 implementation stopping point`
- `e01b7e0 docs(progress): record untracked gaps and broken placeholder targets`
- `9172252 feat(query): add PS3.6 lookup envelopes`
- `6732828 docs(progress): record PS3.6 lookup slice`
- `cfd383d feat(parsers): parse PS3.3 graph tables`
- `c0b5bd0 fix(parsers): prefer PS3.3 definition table identities`
- `9d3f372 feat(db): import PS3.3 graph records`

## Verification at stop

The following offline checks passed after the PS3.3 parser/storage work:

```bash
make lint
uv run mypy
uv run pytest
```

Observed test count: 32 passing tests.

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
- PS3.3 parser for CT-style IOD module tables with Information Entity, Module,
  Reference, and Usage columns, including conditional usage text.
- PS3.3 parser for module and macro attribute tables, including Type
  designations, source refs, include rows resolved by table reference, and
  nested sequence parent links from `>` depth markers.
- PS3.3 parser for functional-group macro usage tables, preserving unresolved
  references as warnings instead of guessing.
- SQLite graph schema for `condition`, `iod`, `module`, `macro`,
  `iod_module_use`, `iod_functional_group_use`, and `attribute_use`.
- Transactional PS3.3 graph import with source-ref coverage and rollback on
  uniqueness/foreign-key failures.

## Not yet implemented

- Official network fetch URL discovery for `current` edition metadata.
- CLI commands wired to fetch and build workflows.
- CLI default cache/database discovery; lookup currently requires `--db`.
- Full PS3.3 parser coverage beyond the first v1 CT-style synthetic fixture
  slice, including broader real-standard table variants.
- PS3.4 SOP class parser.
- General citation builder beyond direct source-ref conversion.
- Query resolvers and CLI commands for PS3.3 graph traversal
  (`list_modules_for_iod`, `list_attributes_for_module`, macro expansion).
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

Continue the PS3.3 work order by adding graph query traversal:

1. Add repository methods for lookup by IOD name, module name, macro table/name,
   and ordered attribute-use rows.
2. Implement `list_modules_for_iod` and `list_attributes_for_module`, including
   optional query-time macro expansion that preserves both include-row and macro
   source refs.
3. Add CLI commands for `dicom-kb iod modules` and
   `dicom-kb module attributes` using an explicit `--db` path, matching the
   existing PS3.6 lookup style.
4. Broaden PS3.3 parser fixtures toward minimal attributed CT Image material
   once local artifact handling for attributed fixtures is in place.

Before MCP work, also add the spec-mandated JSON Schema files for the current
response envelope contracts.
