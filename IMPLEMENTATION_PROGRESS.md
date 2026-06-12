# Implementation Progress

Last updated: 2026-06-12

## Current stopping point

Stopped after the third R7 differential-testing slice from
`PROGRESS_REVIEW.md`: the integration tier now has skip-clean external
differential checks for optional Innolitics JSON and optional pydicom. The
Innolitics harness reads `DICOM_KB_INNOLITICS_PATH`, compares parseable PS3.6
data element fields and CT Image module lists against the local KB, and the
pydicom harness compares local PS3.6 data element fields against pydicom's
packaged data dictionary when that optional dependency is installed. A
pydicom-installed run against a freshly rebuilt temporary 2026b KB now passes
with five explicit accepted differences: two pydicom VM simplifications, two
pydicom keyword edition skews, and one pydicom retired-flag edition skew. The
pydicom run also exposed and fixed a real PS3.6 parser bug: the official data
element table's retired marker column can have an empty header and use `RET`
without spelling out "Retired". A real Innolitics JSON run has not yet been
performed in this environment, so R7 remains open until configured Innolitics
data produces zero unexplained mismatches or documented allowlisted
differences. R6 repository-layout reconciliation is complete: the public query
API now retains `resolver.py` as a thin entry-point layer while citation
assembly, condition payload shaping, PS3.3 graph traversal, recursive macro
expansion, and SQLite FTS query construction live in the spec-aligned
`query/citations.py`, `query/conditions.py`, `query/graph.py`, and
`query/search.py` modules; the MCP adapter now keeps `mcp/server.py` focused on
configuration, dependency loading, and stdio transport while tool metadata and
resolver dispatch live in `mcp/schemas.py` and `mcp/tools.py`; DocBook
`<variablelist>` parsing now lives in `docbook/variablelists.py`; and the
spec-listed `examples/` and `tests/fixtures_minimal_attributed/` paths now
exist. Storage/import wiring for parsed variable lists remains intentionally
pending for a later value-constraint slice, and post-v1 `api/` plus v2 parser
paths remain absent by design. Official `current` was fetched and resolved to
concrete edition `2026b`, the local KB builds from real PS3.3/PS3.4/PS3.6
DocBook XML, `make test-integration` has a real-download integration tier that
passes with local artifacts and skips cleanly without them, and the §15.2 golden
entity set now has real-KB integration assertions. Two R2 parser limitations
remain captured as strict xfails: real PS3.3 include rows are not yet persisted
as macro include provenance, and Enhanced CT functional-group usage rows are not
yet persisted. The repository now has a working v1 foundation through:

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
31. R2 real-KB golden integration coverage for CT Image, MR Image, Enhanced CT
    Image, Segmentation, Comprehensive SR, and Encapsulated PDF IODs; anchor
    modules; core modules and General Series Modality type; the §15.2 data
    element and UID sets; and CT/Segmentation SOP Class to IOD traversals.
    Golden expectations are checked through public resolvers with PS3.3/PS3.6
    source-ref anchors where the public response envelope exposes them.
32. R3 Work Order J prompt-case expansion from three cases to 65 committed
    agent regression cases. The cases are pinned to concrete edition `2026b`,
    systematically cover golden IODs, modules, data elements, UIDs, SOP Class
    traversals, attribute context queries, text retrieval, text search,
    multi-tool workflows, and 10 error/ambiguity paths, with an offline test
    enforcing the coverage floors.
33. R4 Work Order J reference-agent runner and CLI. `dicom-kb eval run` opens a
    local KB, runs selected or all committed prompt cases through deterministic
    public resolver routes, writes compact transcript JSON consumable by
    `dicom-kb eval score`, and has offline synthetic-fixture coverage plus a
    real-KB integration scorecard over all 65 prompt cases.
34. R5 MCP protocol smoke coverage. An offline test launches `dicom-kb mcp
    serve` as a subprocess, connects with the official MCP Python stdio client,
    exercises initialize, `tools/list`, and two `tools/call` requests against
    the synthetic fixture KB, and verifies all nine v1 tools expose input
    schemas.
35. R6 query layout reconciliation, first slice. `resolver.py` now keeps the
    public entry points while citation/trace assembly, condition payload
    shaping, PS3.3 graph traversal, recursive macro expansion, and FTS query
    construction live in `query/citations.py`, `query/conditions.py`,
    `query/graph.py`, and `query/search.py` with no public API change.
36. R6 MCP layout reconciliation, second slice. `mcp/server.py` now keeps the
    runtime configuration and stdio transport helpers while tool-name metadata
    lives in `mcp/schemas.py` and resolver dispatch plus FastMCP registration
    live in `mcp/tools.py`, preserving the public CLI and MCP behavior.
37. R6 DocBook variable-list parser, third slice. `docbook/variablelists.py`
    parses `<variablelist>` entries into term/definition IR with parent section
    context, stable XML ids, row order, and embedded references; `ParsedDocument`
    exposes the parsed lists for future enumerated-value and defined-term
    storage.
38. R6 examples and minimal-attributed fixture policy, fourth slice. The
    spec-listed `examples/python/`, `examples/cli/`, `examples/mcp/`,
    `examples/coding_agent_harness/`, `examples/validators/`, and
    `tests/fixtures_minimal_attributed/` paths exist; examples target the
    synthetic fixture KB, executable examples have offline smoke coverage, and
    the attributed fixture directory starts with policy only.
39. R7 differential testing, first slice. The integration tier has an optional
    Innolitics JSON differential harness that skips without
    `DICOM_KB_INNOLITICS_PATH`, compares overlapping PS3.6 element fields and
    CT Image module names when a JSON file/directory is supplied, and records
    accepted differences only through an explicit allowlist file.
40. R5 MCP startup regression hardening. Missing-KB CLI assertions now
    normalize Typer/Rich styling before matching actionable fetch/build advice,
    and the missing optional MCP dependency path uses an explicit fixture DB so
    it remains isolated from whatever default cache exists on a developer
    machine.
41. R7 differential testing, second slice. The integration tier now has an
    optional pydicom data dictionary comparison for PS3.6 element fields, and
    differential allowlist entries must include the external source,
    classification, and reason before they can suppress a mismatch.
42. R7 parser hardening from pydicom differential feedback. PS3.6 data element
    and UID parsers now treat an empty trailing registry-table header as the
    retired marker column and recognize `RET` markers even when the name does
    not include "(Retired)", with synthetic fixture coverage.
43. R7 pydicom differential triage. The pydicom adapter now normalizes
    pydicom-specific dictionary conventions, and the focused pydicom run
    against a rebuilt 2026b KB passes with five explicit accepted differences
    recorded as interpretation or edition skew.

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
- `7e53994 docs(progress): record R1 real KB validation`
- `f770617 test(integration): add real KB golden coverage`
- `ecaad27 docs(progress): record R2 golden coverage`
- `9c8a3ec feat(eval): expand agent prompt cases`
- `f473605 docs(progress): record R3 prompt expansion`
- `4322f97 feat(eval): add reference agent runner`
- `336544f docs(progress): record R4 reference runner`
- `e7569ca test(mcp): add stdio protocol smoke coverage`
- `4910279 refactor(query): split resolver internals by concern`
- `3fd10ed docs(progress): record R6 query layout split`
- `5ea3d2c refactor(mcp): split server transport from tool mapping`
- `1cb59ec docs(progress): record R6 MCP layout split`
- `6190d63 feat(docbook): parse variable lists`
- `096fb61 docs(progress): record R6 variable-list parser`
- `cbd7dc8 feat(examples): add fixture-oriented sample workflows`
- `9c73bb4 docs(progress): record R6 layout completion`
- `5c33713 test(integration): add Innolitics differential harness`
- `78033dd docs(progress): record R7 differential harness`
- `97a00f0 test(mcp): isolate server startup failure cases`
- `96820fd test(integration): add pydicom differential check`
- `7b96148 docs(progress): record pydicom differential slice`
- `4abf56f fix(parsers): detect PS3.6 RET retired markers`
- `e75c528 test(integration): triage pydicom dictionary skew`

## Verification at stop

The following checks passed after the R7 pydicom differential triage slice:

```bash
uv run --dev ruff check .
uv run --dev mypy
uv run --dev pytest
```

Observed local test result without external differential data or pydicom
installed: 157 passed, 3 skipped, and 2 strict xfailed tests.

The focused pydicom differential was also run against a fresh temporary build
from the locally cached official 2026b DocBook artifacts:

```bash
uv run --dev dicom-kb build --edition 2026b \
  --db /private/tmp/dicom-kb-2026b-pydicom-check-v2.sqlite
DICOM_KB_CACHE_DIR=/private/tmp/dicom-kb-pydicom-cache \
  uv run --with pydicom --dev pytest \
  tests/integration_requires_dicom_download/test_differential.py::test_ps36_data_elements_match_pydicom_dictionary
```

Observed focused pydicom result: 1 passed. The five accepted pydicom
differences are recorded in
`tests/integration_requires_dicom_download/differential_allowlist.json`.

Observed R3 prompt-case metrics:

- 65 committed cases.
- 10 error/ambiguity cases.
- All nine v1 query tools appear in at least one case's `expected_tools`.
- The deterministic reference runner scores all 65 cases against the local
  real 2026b KB through `tests/integration_requires_dicom_download/`.
- The synthetic fixture runner subset and `dicom-kb eval run` / `eval score`
  CLI path are covered by `tests/agent_regression/`.
- The official MCP Python stdio client smoke test passes against the synthetic
  fixture KB and verifies initialize, tool listing, schemas, and tool calls.

The following integration checks were also run against locally fetched and
built official DICOM edition `2026b`:

```bash
uv run --dev pytest tests/integration_requires_dicom_download
```

Observed integration result with artifacts before the first R7 harness: 37
passing tests and 2 strict xfailed tests. The R7 differential test file was run
directly without `DICOM_KB_INNOLITICS_PATH` and without pydicom installed; all
three external comparisons skipped cleanly.

The no-artifact path was verified with an empty cache:

```bash
DICOM_KB_CACHE_DIR=/private/tmp/dicom-kb-empty-cache \
  uv run --dev pytest tests/integration_requires_dicom_download
```

Observed no-artifact result: 39 skipped tests, exit code 0.

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

Accepted R2 strict-xfail limitations:

- Real PS3.3 module include rows are currently imported as plain attribute rows
  in the real 2026b build, so `expand_macros=true` cannot yet demonstrate
  dual include/macro provenance against official content.
- Enhanced CT functional-group usage rows are not persisted in the real 2026b
  build, so `resolve_attribute_context` cannot yet report a non-empty
  `via_macro` path for an attribute reachable only through a functional group.

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
- DocBook variable-list parsing into term/definition IR with parent section,
  XML id, entry order, and embedded reference preservation; persistence remains
  pending for the later value-constraint slice.
- Fixture-oriented examples for direct Python resolver usage, CLI lookup, MCP
  server launch, deterministic coding-agent harness runs, and local identifier
  validators.
- Minimal-attributed fixture policy directory that starts empty of official
  excerpts and defines attribution/minimization rules for future parser cases.
- Optional Innolitics differential harness for PS3.6 data element fields and CT
  Image module lists, with clean skips when external comparison data is not
  configured.
- Optional pydicom differential harness for PS3.6 data element fields, with a
  clean skip when pydicom is not installed and a passing focused run against a
  fresh 2026b temporary build when pydicom is installed.
- Explicit differential allowlist validation requiring accepted mismatches to
  name the external source, entity, field, classification, and reason.
- DocBook section/table parent and ordinal metadata for persistent structure
  storage.
- Zero-width character removal and normalized text helpers.
- PS3.6 data element parsing with tag normalization, explicit/empty-header
  retired marker columns, `RET` retired markers, malformed row warnings, and
  range-tag detection.
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
- Offline MCP protocol smoke coverage using the official Python MCP stdio
  client against the synthetic fixture KB, verifying initialize,
  `tools/list`, all nine v1 input schemas, and tool-call response envelopes.
- `dicom-kb mcp serve` now checks the configured SQLite KB path before starting
  stdio and reports actionable fetch/build or fixture-build commands when it is
  missing.
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
- Deterministic reference-agent runner for committed prompt cases, using the
  public query resolvers to record compact `AgentRun` transcripts with tool
  arguments, response status, edition, and source-reference counts.
- `dicom-kb eval run` command for selected or all committed cases via repeated
  `--case`/`--cases`, writing transcripts scoreable by `dicom-kb eval score`
  without requiring LLM API keys.
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
- Optional real-LLM external-agent runner configuration remains pending. The
  committed R4 runner is the deterministic reference agent; real-KB transcripts
  remain uncommitted build outputs by design.
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

Continue with R6 repository layout reconciliation: split existing query and MCP
internals into the spec layout modules, then add `docbook/variablelists.py`,
`examples/`, and `tests/fixtures_minimal_attributed/`.
