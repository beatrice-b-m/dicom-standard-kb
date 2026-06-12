# Implementation Progress

Last updated: 2026-06-12

## Current stopping point

Stopped after completing the R1 real-edition validation slice from
`PROGRESS_REVIEW.md`: official `current` was fetched and resolved to concrete
edition `2026b`, the local KB builds from real PS3.3/PS3.4/PS3.6 DocBook XML,
and `make test-integration` now has a real-download integration tier that
passes with local artifacts and skips cleanly without them. The repository now
has a working v1 foundation through:

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
16. Additive `doc_node`, `xref`, and `raw_table_ir` SQLite storage with a
    transactional DocBook structure importer, deterministic source refs,
    parent linkage, xref resolution, and raw table JSON snapshot hashes.
17. Public `retrieve_standard_text` response envelope plus CLI command
    `dicom-kb retrieve-text`, resolving persisted DocBook nodes by part and
    anchor/section number, returning capped excerpts and related table refs.
18. Public `search_standard_text` response envelope plus CLI command
    `dicom-kb search-text`, using a local SQLite FTS5 index over persisted
    DocBook node titles/text with part filtering, bounded result limits,
    snippets, and citation-preserving refs.
19. Local SQLite build orchestration that reads immutable source manifests,
    imports cached DocBook XML artifacts in dependency order, records build
    metadata, and writes the conventional cache database at
    `db/<edition>.sqlite`.
20. CLI workflow commands `dicom-kb fetch`, `dicom-kb build`, and
    `dicom-kb build-fixture`, plus default cache/database discovery for query
    commands when `--db` is omitted.
21. First v1 MCP server adapter exposing the implemented query resolvers as
    spec-prefixed `dicom_*` tools, with a `dicom-kb mcp serve` CLI command
    over stdio and optional dependency handling.
22. Offline MCP adapter integration coverage using an in-process FastMCP
    double to verify v1 tool registration, descriptions, argument mapping into
    public response envelopes, and stdio transport invocation.
23. First Work Order J slice: edition-pinned agent regression prompt cases,
    expected tool traces, deterministic scoring contracts, and offline scoring
    tests under `tests/agent_regression/`.
24. Official current-release source acquisition for v1 DocBook XML parts,
    including concrete edition discovery from DICOM release metadata,
    immutable manifest writing, CLI `dicom-kb fetch --edition current`, and
    offline unit coverage with mocked URL reads.
25. Optional official current-release artifact fetch for per-part PDF, HTML,
    CHTML entry page, and target database files via repeatable
    `dicom-kb fetch --format`, with format-specific cache paths and mocked
    offline CLI/downloader coverage.
26. Official concrete-edition archive fetch for v1 parts and supported
    artifact formats, using `current` metadata only for mutable current-release
    requests and the official archive root for explicit editions.
27. Recursive CHTML tree mirroring for official fetches via
    `dicom-kb fetch --format chtml --mirror-chtml-tree`, with same-release URL
    containment checks, safe cache-relative path handling, per-file manifest
    entries, and mocked offline downloader/CLI coverage.
28. Work Order J scorecard reporting for recorded agent transcripts, including
    JSON transcript loading, aggregate pass/fail reports, unknown-case
    diagnostics, and a `dicom-kb eval score` CLI command suitable for offline
    CI gating.
29. R1 real-edition parser hardening: official 2026b DocBook section/table
    parsing now handles processing instructions, DocBook HTML-style
    `caption`/`tr`/`th`/`td` tables, numeric spans, real PS3.3 `IE` headers,
    no-usage IOD module tables, and PS3.4 SOP Class `olink` references to
    PS3.3 IOD section anchors.
30. R1 integration tier under `tests/integration_requires_dicom_download/`
    that discovers a local cache/edition, skips when no built KB exists,
    checks manifest shape, asserts real-KB entity count floors, and exercises
    public resolvers for Modality, transfer syntaxes, CT Image modules,
    CT Image Storage SOP Class traversal, and range-tag lookup.

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
- `174851a feat(db): persist DocBook structure`
- `014cd42 feat(query): retrieve standard text excerpts`
- `64cd07f docs(progress): record text retrieval slice`
- `03631f8 feat(query): search persisted standard text`
- `c05d12f feat(cli): build local SQLite knowledge bases`
- `8890264 feat(cli): register local DocBook artifacts`
- `63dbfb9 feat(mcp): expose query resolvers as MCP tools`
- `2d246d3 test(mcp): cover FastMCP tool registration`
- `8f3b719 feat(eval): add agent regression scoring`
- `0d7d4f6 docs(progress): record agent scoring harness`
- `1210ba8 feat(sources): fetch official DocBook artifacts`
- `d3fd7b6 docs(progress): record official fetch slice`
- `1dbba9b feat(sources): fetch additional official formats`
- `f0844fa feat(sources): fetch concrete editions from archive`
- `0e4d72f feat(sources): mirror CHTML part trees`
- `7f5481a feat(eval): add agent scorecard reporting`
- `0c927e1 fix(docbook): parse real DocBook table vocabulary`
- `81983d8 fix(parsers): resolve real SOP class IOD links`
- `80f190f test(integration): add real KB smoke coverage`

## Verification at stop

The following offline checks passed after the R1 integration work:

```bash
uv run --dev ruff check .
uv run --dev mypy
uv run --dev pytest
```

Observed offline test count: 112 passing tests.

The following integration checks were also run against locally fetched and
built official DICOM edition `2026b`:

```bash
make test-integration
```

Observed integration result with artifacts: 5 passing tests.

The no-artifact path was verified with an empty cache:

```bash
DICOM_KB_CACHE_DIR=/private/tmp/dicom-kb-empty-cache \
  uv run --dev pytest tests/integration_requires_dicom_download
```

Observed no-artifact result: 5 skipped tests, exit code 0.

The real 2026b build imports:

- PS3.6: 5308 data elements, 489 UID registry entries.
- PS3.3: 192 IODs, 403 modules, 3401 IOD module uses, 303 macros,
  8955 attribute uses.
- PS3.4: 181 SOP Classes and 181 SOP Class to IOD edges.

Accepted R1 parser warning class: 446 `unresolved functional group` warnings
from PS3.3 functional-group usage tables. The real build no longer crashes,
and the R1 smoke assertions do not depend on functional-group traversal. This
remains a documented parser limitation for R2 Enhanced CT/functional-group
golden coverage.

## Implemented behavior

- Python 3.12 package scaffold managed by `uv`.
- Required legal notice in README, NOTICE, docs, and shared metadata.
- Offline CI, Dockerfile, Makefile, lint, typecheck, and pytest targets.
- Concrete edition resolution with safe handling of mutable `current`.
- SHA-256 helpers and immutable source manifests.
- Local artifact registration into the external cache layout.
- Official current-release discovery from DICOM directory metadata, resolving
  `current` to one concrete edition before manifest storage.
- Official DocBook XML download into the external cache for the v1 parsed
  parts PS3.3, PS3.4, and PS3.6, with optional `--part` filtering and
  source URLs/checksums recorded in manifests.
- Optional official PDF, single-page HTML, CHTML part-entry page, and target
  database download into the external cache with repeatable `--format`
  selection and source URLs/checksums recorded in manifests.
- Official fetch of explicit concrete editions from the DICOM archive root
  (for example `https://dicom.nema.org/medical/dicom/2025e/`) instead of the
  mutable current-release directory, with archive listing validation and a CLI
  `--archive-base-url` override for deterministic tests.
- Opt-in recursive CHTML tree mirroring through `--mirror-chtml-tree` when
  `--format chtml` is requested, preserving each mirrored file as a separate
  manifest artifact and rejecting traversal outside the selected part tree.
- Namespace-aware DocBook section, table, span, xref, and include-row parsing.
- DocBook section/table parent and ordinal metadata for persistent structure
  storage.
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
- SQLite schema and transactional import for `doc_node`, `xref`, and
  `raw_table_ir`, preserving document structure, local cross-reference
  resolution, and raw table JSON snapshot hashes for parser debugging.
- SQLite FTS5 schema and transactional import population for local full-text
  search over persisted DocBook titles and plain text.
- Repository traversal from SOP Class UID/name/PS3.6 UID keyword to linked IODs.
- Repository lookup of persisted DocBook nodes by part and exact `xml:id`,
  anchor, or section number, with recursive table listing below matched nodes.
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
- `retrieve_standard_text` resolver with part/max-character validation,
  persisted DocBook node lookup, capped text excerpts, truncation warnings, and
  citation-preserving related table refs.
- CLI command `dicom-kb retrieve-text` that reads an explicit local SQLite
  database path and emits the public text-retrieval JSON envelope.
- `search_standard_text` resolver with query/part/limit validation,
  deterministic FTS query construction, not-found responses, SQLite-generated
  snippets, and citation-preserving match refs.
- CLI command `dicom-kb search-text` that reads an explicit local SQLite
  database path, supports `--part` and `--limit`, and emits the public search
  JSON envelope.
- `dicom-kb fetch` command that registers local DocBook XML artifacts via
  repeatable `--docbook-xml PART=PATH` arguments or downloads official
  current-release artifacts into the immutable external cache manifest.
- `dicom-kb build` command that reads cached manifest artifacts and builds a
  local SQLite KB under `~/.cache/dicom-standard-kb/db/<edition>.sqlite` by
  default, with optional `--db`, `--cache-dir`, `--backend sqlite`, and
  `--force`.
- `dicom-kb build-fixture` command that builds the shared synthetic fixture KB
  through the same manifest/build pipeline.
- Query CLI commands now discover the conventional cache database from
  `--edition` and `--cache-dir` when `--db` is omitted.
- Generated SQLite databases record build metadata including build time,
  parser version, schema version, manifest digest, source checksums, and
  repository commit when available.
- JSON Schema contract files for tool response envelopes, standard references,
  source manifests, and condition facts.
- Offline schema drift tests that keep schema field names and response status
  enums aligned with the implemented Pydantic contracts.
- Shared synthetic DocBook XML fixture files for current PS3.3, PS3.4, and
  PS3.6 parser coverage, with importer/query/CLI tests consuming the same
  fixture source.
- MCP server adapter for the nine v1 query tools:
  `dicom_lookup_data_element`, `dicom_lookup_uid`,
  `dicom_lookup_sop_class`, `dicom_lookup_iod`,
  `dicom_list_modules_for_iod`, `dicom_list_attributes_for_module`,
  `dicom_resolve_attribute_context`, `dicom_retrieve_standard_text`, and
  `dicom_search_standard_text`.
- `dicom-kb mcp serve --edition <edition>` command serving the MCP adapter
  over stdio from an explicit `--db` or the conventional cache database.
- Offline FastMCP registration tests that verify the adapter exposes the v1
  tool set, preserves tool descriptions, maps registered tool arguments
  through the public query envelopes, and invokes stdio transport.
- `dicom_kb.eval` package with committed agent prompt cases, expected
  tool-call traces, transcript models, and deterministic scorecards.
- Agent regression scoring checks for required tools, expected trace order,
  exact expected arguments, response metadata, source-reference evidence,
  edition-aware answers, and unsupported normative claims.
- `tests/agent_regression/` test coverage for passing transcripts, missing
  tools/citations, unsupported claims, and argument mismatch diagnostics.
- Agent transcript report loading for single-run JSON objects, JSON arrays, or
  objects with top-level `runs`, with aggregate pass/fail scorecards and
  unknown-case diagnostics.
- `dicom-kb eval score` command for scoring recorded agent transcripts,
  emitting stable JSON reports and exiting nonzero by default when any run
  fails.
- Real DocBook table IR accepts official HTML-style table vocabulary in
  addition to the existing CALS fixture vocabulary.
- Real PS3.3 IOD module parsing handles `IE` header aliases and IOD module
  tables that omit Usage/Information Entity columns while still registering
  the IOD and module edge.
- Real PS3.4 SOP Class parsing can resolve empty rendered IOD cells through
  preserved `olink targetptr` anchors mapped to imported PS3.3 IODs during
  `dicom-kb build`.
- `tests/integration_requires_dicom_download/` covers local real-KB discovery,
  skip-clean behavior without artifacts, source-manifest shape validation,
  real entity count floors, and well-known resolver smoke assertions.

## Not yet implemented

- Full PS3.3 functional-group macro resolution for real standard tables. The
  2026b build currently reports 446 `unresolved functional group` warnings.
- Spec query-layer modules beyond `query/resolver.py`: `query/graph.py`,
  `query/conditions.py`, `query/citations.py`, and `query/search.py` (Work
  Order H). Graph traversal and FTS5-backed text search currently live in
  resolvers/repositories.
- General citation builder beyond direct source-ref conversion.
- MCP server is present for the implemented v1 query resolvers with offline
  registration coverage. External MCP protocol/client smoke testing is still
  pending.
- Agent regression harness has offline scoring and scorecard CLI/reporting. A
  configured external-agent runner, committed recorded answer transcripts, and
  the spec target of at least 50 v1 prompt cases are still pending.
- Golden fixture coverage (SYSTEM_SPECS.md section 15.2) beyond the R1 smoke
  assertions: MR Image, Enhanced CT Image functional-group traversal,
  Segmentation, Comprehensive SR, and Encapsulated PDF goldens are pending.
  These should build on `tests/integration_requires_dicom_download/` and use
  strict xfails where parser limitations remain.
- Spec-mandated repository directories and files:
  `tests/fixtures_minimal_attributed/`, `examples/`, and
  `docbook/variablelists.py`.

## Known broken placeholders

These Makefile targets are forward declarations that currently fail or no-op
if run:

- `make run-mcp` now invokes the MCP stdio server with the optional `mcp`
  extra, but it still requires a local `2026b` database to exist in the
  conventional cache path.

## Recommended next work order

Continue the v1 critical path with R2 golden integration coverage over the
real 2026b KB, starting with CT Image, MR Image, Encapsulated PDF, the §15.2
data element/UID set, and strict-xfail documentation for any still-blocked
Enhanced CT functional-group traversal.
