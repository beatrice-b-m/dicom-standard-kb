# Implementation Progress

Last updated: 2026-06-12

## Current stopping point

Stopped after adding `resolve_attribute_context` with IOD/SOP Class traversal,
macro expansion, and effective type computation. The repository now has a
working offline foundation through:

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
9. Work Order G, fourth v1 slice: SQLite-backed PS3.3 graph traversals,
   public response envelopes, and CLI commands for IOD module lists and module
   attribute lists with optional macro expansion.
10. Spec-mandated JSON Schema files for public tool responses, standard
    references, source manifests, and condition facts, plus offline drift tests
    against the implemented Python contracts.
11. Spec-mandated `tests/fixtures_synthetic/` directory containing shared
    synthetic DocBook XML fixtures for PS3.3 and PS3.6 parser/import/query
    tests.
12. Recursive `list_attributes_for_module(..., expand_macros=True)` expansion
    with effective `sequence_depth` adjustment, include-row provenance, and
    macro include cycle warnings.
13. Work Order F / G v1 slice: conservative PS3.4 service class and SOP Class
    table parsing, transactional SQLite import, repository traversal from SOP
    Class to linked IODs, and a shared synthetic PS3.4 fixture.
14. Public `lookup_iod` and `lookup_sop_class` response envelopes plus CLI
    commands `dicom-kb lookup iod` and `dicom-kb lookup sop-class`.
15. Public `resolve_attribute_context` response envelope plus CLI command
    `dicom-kb resolve attribute-context`, with PS3.6-backed attribute
    identity, IOD or SOP Class context resolution, recursive macro expansion,
    sequence-path reporting, and lowest effective type computation across
    multiple uses.

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
- `152f5e9 feat(query): add PS3.3 graph traversal`
- `b380b4f feat(schemas): add public JSON Schema contracts`
- `6e1dbe6 test(fixtures): move synthetic DocBook into fixture files`
- `01b8106 docs(progress): record synthetic fixture layout`
- `b9b0c6d docs(progress): record review gaps and next-step refinements`
- `324922a feat(query): expand macros recursively`
- `46c3087 docs(progress): record recursive macro expansion`
- `7a2814d feat(parsers): add PS3.4 SOP class import`
- `e63e678 feat(query): expose SOP Class and IOD lookups`
- `7cde527 docs(progress): record SOP Class lookup slice`
- `0f6296b feat(query): resolve attribute context`

## Verification at stop

The following offline checks passed after attribute context resolution work:

```bash
make lint
uv run mypy
uv run pytest
```

Observed test count: 59 passing tests.

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
  matching range rows; data-element lookup also accepts exact element names for
  context resolution.
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
- Repository traversal for PS3.3 IODs, modules, macros, ordered module-use
  rows, and ordered attribute-use rows.
- `list_modules_for_iod` resolver with exact IOD name/keyword lookup,
  citation-preserving module usage payloads, and not-found responses.
- `list_attributes_for_module` resolver with exact module lookup, include-row
  preservation, optional recursive macro expansion, citation-preserving
  attribute payloads, effective sequence-depth reporting, include cycle
  warnings, and not-found responses.
- CLI commands `dicom-kb iod modules` and `dicom-kb module attributes` that
  read an explicit local SQLite database path and emit JSON envelopes.
- PS3.4 parser for service class tables with explicit IOD, SOP Class Name, and
  SOP Class UID columns, preserving malformed UID rows as parser warnings.
- SQLite schema and transactional import for `service_class`, `sop_class`, and
  `sop_class_iod`, with foreign-key rollback when referenced IODs are absent.
- Repository traversal from SOP Class UID/name/PS3.6 UID keyword to linked IODs.
- `lookup_iod` resolver with exact IOD name/keyword lookup, citation-preserving
  payloads, and not-found responses.
- `lookup_sop_class` resolver with UID/name/keyword lookup, malformed UID
  validation errors, linked IOD traversal, PS3.3/PS3.4 citations, and
  not-found responses.
- CLI commands `dicom-kb lookup iod` and `dicom-kb lookup sop-class` that read
  an explicit local SQLite database path and emit JSON envelopes.
- `resolve_attribute_context` resolver with exact attribute lookup through
  PS3.6 tag/keyword/name identity, validation errors for malformed tag or SOP
  Class UID inputs, exact IOD context lookup, SOP Class → linked IOD traversal,
  recursive module macro expansion, sequence-path reporting for nested
  attributes, macro-path provenance for expanded attributes, and not-found
  responses for missing attributes or contexts.
- Effective attribute type computation across matching uses, selecting the
  lowest recognized DICOM type designation (`1`, `1C`, `2`, `2C`, `3`) and
  warning when multiple-use resolution assumes no description-text override.
- CLI command `dicom-kb resolve attribute-context` that reads an explicit local
  SQLite database path and emits the public context-resolution JSON envelope.
- JSON Schema contract files for tool response envelopes, standard references,
  source manifests, and condition facts.
- Offline schema drift tests that keep schema field names and response status
  enums aligned with the implemented Pydantic contracts.
- Shared synthetic DocBook XML fixture files for current PS3.3, PS3.4, and
  PS3.6 parser coverage, with importer/query/CLI tests consuming the same
  fixture source.

## Not yet implemented

- Official network fetch URL discovery for `current` edition metadata.
- CLI commands wired to fetch and build workflows.
- CLI default cache/database discovery; lookup currently requires `--db`.
- Full PS3.3 parser coverage beyond the first v1 CT-style synthetic fixture
  slice, including broader real-standard table variants.
- Spec query-layer modules beyond `query/resolver.py`: `query/graph.py`,
  `query/conditions.py`, `query/citations.py`, and `query/search.py` (Work
  Order H). Graph traversal currently lives in resolvers/repositories;
  FTS5-backed `search_standard_text` has not been started.
- `retrieve_standard_text` (v1 tool, SYSTEM_SPECS.md section 8.6); blocked on
  `doc_node` storage because no prose is persisted to retrieve.
- General citation builder beyond direct source-ref conversion.
- MCP server tool surface.
- Agent regression harness.
- Golden fixture coverage (SYSTEM_SPECS.md section 15.2) beyond the single
  synthetic CT-style PS3.3 fixture and PS3.6 registry fixture: MR Image,
  Enhanced CT Image (functional-group resolution exercised end-to-end through
  the query layer), Segmentation, Comprehensive SR, and Encapsulated PDF
  goldens are pending. These approach real-standard content, so they likely
  belong with the integration-test work rather than synthetic fixtures.
- Raw table IR persistence (SYSTEM_SPECS.md section 10.3): the DocBook layer
  builds table IR in memory, but the import stores only normalized
  `data_element`/`uid_registry_entry` rows. No `doc_node`, `xref`, or JSON
  table-snapshot storage exists yet, so parser bugs cannot be investigated
  without reparsing the source.
- Spec-mandated repository directories and files:
  `tests/fixtures_minimal_attributed/`, `tests/agent_regression/`, `examples/`,
  and `docbook/variablelists.py`.

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

Continue the v1 critical path by adding persisted `doc_node`/raw table IR
storage so `retrieve_standard_text` can be implemented with citation-preserving
short excerpts instead of reparsing source XML on every query.
