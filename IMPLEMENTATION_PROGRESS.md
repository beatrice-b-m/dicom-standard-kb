# V2 Implementation Progress

This file is the durable handoff point for coding agents implementing the
v2 roadmap. Update it after every completed logical unit and before handing
work to another agent.

## Handoff Rules

- Keep the newest status accurate. Do not leave a phase marked `In progress`
  if no actionable work remains in the current commit.
- Add the commit hash for every completed unit after running
  `git log --oneline -3`.
- Record the exact verification command and result. If a check was skipped,
  state the prerequisite that was missing.
- Record blockers as concrete next actions, not general uncertainty.
- Do not mark a v2 acceptance criterion complete until the capability exists
  across Python, CLI, and MCP, with tests.

Status values:

- `Not started`
- `In progress`
- `Blocked`
- `Complete`

## Current Summary

| Area | Status | Notes |
|---|---|---|
| V1 baseline | Complete | See `IMPLEMENTATION_REVIEW.md`; v1 acceptance criteria are documented as met. |
| Phase 0 - V2 contract baseline | Complete | V2 result payload builders, JSON schema coverage, canonical migration table names, and empty-database migration smoke coverage are in place. |
| Phase 1 - New part acquisition/parser foundation | Complete | Default official DocBook fetch, synthetic build-fixture loading, parser scaffolds, raw table IR, source refs, and unsupported-table warning aggregation now cover PS3.5, PS3.7, PS3.8, PS3.10, PS3.16, and PS3.18. |
| Phase 2 - PS3.5 VR and transfer syntax semantics | Complete | `vr_definition` and `transfer_syntax_detail` import paths plus Python resolver functions, CLI commands, MCP tools, and official-edition golden test coverage are in place. The local 2026b official KB was rebuilt with Phase 2 rows and the transfer-syntax goldens execute and pass. |
| Phase 3 - PS3.10 file meta and media foundation | Complete | `file_meta_requirement` and PS3.10-derived `dicom_media_type` parser/import/build wiring are in place for synthetic PS3.10 rows. The Python resolver, CLI command, and MCP tool cover the PS3.10 `lookup_media_type` baseline, including bounded cited text fallback for prose-only PS3.10 file format rules. |
| Phase 4 - PS3.18 DICOMweb transactions | Complete | Synthetic PS3.18 DICOMweb transaction rows parse into `dicomweb_transaction` with route template, method, resource category, constraints, status codes, media-type refs, source refs, and build/import smoke coverage. Python, CLI, and MCP transaction lookup behavior are in place, and PS3.18 media-type rows now expand the existing `lookup_media_type` surface with DICOMweb request/response contexts. |
| Phase 5 - PS3.16 SR templates, CIDs, and codes | Complete | SR template, context group, and coded concept parsing/import/build wiring are in place for synthetic PS3.16 fixtures. Python resolver functions, CLI commands, and MCP tools cover code meaning, context group, and SR template lookups. Legal and distribution docs now explicitly preserve the no-standalone-terminology-dump invariant for PS3.16 content. |
| Phase 6 - Contextual enumerated values and defined terms | Complete | Existing `attribute_value_term` coverage is documented; deterministic IOD/SOP/module/macro context resolution works through the shared PS3.3/PS3.4 graph, and ambiguous contextual value-term matches now return candidates instead of a merged answer. |
| Phase 7 - Selected PS3.7/PS3.8 semantics | Complete | Selected PS3.7 DIMSE service-behavior and PS3.8 association-PDU parser slices are in place for synthetic fixtures, with cited PS3.7/PS3.8 retrieval fallback coverage and agent regression traces through `retrieve_standard_text`. |
| Phase 8 - Evaluation harness expansion | Complete | The final v2 workflow prompt batch raises the suite to 101 prompt cases; every implemented v2 public tool appears in deterministic expected traces, unsupported normative-claim checks cover the major v2 domains, and the full agent regression suite passes. |
| Phase 9 - V2 release hardening | In progress | README, agent-tool docs, architecture docs, and the release checklist now cover v2 build defaults, CLI commands, MCP tool names, v2 storage entities, contextual value-term resolution, v2 release gates, official-edition golden expectations, per-part metrics expectations, distribution audits, and representative official-edition v2/query goldens. Build metrics now report parser warning counts by part, and a tracked-file distribution audit now guards against committed official artifacts, generated databases, vector indexes, and standalone terminology dumps. Final integration/current gates remain. |

## Acceptance Criteria Tracker

| # | V2 acceptance criterion | Status | Evidence |
|---|---|---|---|
| 1 | Transfer syntax UID lookups return UID metadata plus encoding refs. | Complete | Python, CLI, and MCP surfaces exist with synthetic coverage; representative official-edition transfer-syntax goldens execute against the rebuilt local 2026b official KB and pass. |
| 2 | DICOMweb transaction lookups return route, method, resource type, request/response constraints, and standard references. | Complete | Python resolver, CLI command, and MCP tool return parsed PS3.18 transaction rows by exact name or route template with ambiguous route candidates. |
| 3 | TID and CID lookups return structured rows and extensibility metadata. | Complete | Python resolvers return structured TID and CID rows with extensibility metadata; CLI and MCP exposure exists for TID, CID, and code lookup; legal/distribution docs explicitly forbid standalone PS3.16 terminology dumps and bulk context-group/code exports. |
| 4 | Enumerated values and defined terms link to their attribute context. | Complete | Existing import and lookup coverage is documented; exact module, macro, IOD, and SOP Class contexts resolve to applicable attribute-use contexts, and ambiguous contextual matches return candidates instead of silently choosing one. |
| 5 | Fallback text retrieval covers prose-only rules. | Complete | PS3.10 media/file-format fallback returns bounded cited text when no parsed media-type row matches, and PS3.7 selected service-behavior plus PS3.8 selected networking prose are covered by cited `retrieve_standard_text` fallback and agent regression traces. |
| 6 | At least 100 coding-task regression prompts pass through deterministic tool calls before answer synthesis. | Complete | 101 prompt cases exist after the final Phase 8 v2 workflow batch; `tests/agent_regression/` passes with deterministic expected traces for every v2 public tool and final-batch workflow route. |

## Active Work

| Field | Value |
|---|---|
| Current phase | Phase 9 - V2 Release Hardening |
| Current owner/agent | Codex |
| Branch | main |
| Last completed commit | Pending current commit. Previous completed Phase 9 commit: 2c24e49. |
| Last verification | `uv run --dev pytest tests/unit/test_distribution_audit.py tests/unit/test_metadata.py` passed with 9 passed; `uv run --dev ruff check tests/unit/test_distribution_audit.py tests/unit/test_metadata.py` passed; sandboxed `make lint` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` was rejected by the environment approval policy; escalated `make typecheck` passed with no issues in 57 source files. |
| Current blocker | None |
| Commit-ready summary | Added a focused tracked-file distribution audit test that confirms repository releases remain code-only: no official artifact paths, generated databases, vector indexes, bulk generated text/JSON paths, official `partNN.xml` files, or standalone terminology dump artifacts are tracked. The test also verifies wheel and Docker release inputs remain limited to source code and metadata. |
| Next recommended action | Continue Phase 9 by running the remaining local official-edition release gates: `make test-dicom-integration` and `make test-dicom-current`, recording pass results or exact skipped prerequisites. |

## Phase 0 - V2 Contract Baseline

Status: `Complete`

Scope:

- Define v2 result payload contracts.
- Add schema tests for v2 envelopes.
- Design migration table names and relationships.
- Preserve v1 response compatibility.

Completion checklist:

- [x] V2 result payload builders exist.
- [x] JSON schema tests cover representative v2 responses.
- [x] Empty-database migration smoke test passes.
- [x] v1 response contract tests still pass.
- [x] `make lint` passes.
- [x] `make typecheck` passes.
- [x] `make test` passes.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| d831ea9 | Added Pydantic-backed v2 result payload builders and classification defaults for planned v2 tools. | `uv run --dev pytest tests/unit/test_json_schemas.py`; `make lint`; `make typecheck`; `make test` |
| 3fc8149 | Added explicit JSON schema coverage for v2 result payloads and representative payload contract tests. | `uv run --dev pytest tests/unit/test_json_schemas.py`; `make lint`; `make typecheck`; `make test` |
| 0bbb0fe | Added canonical v2 migration table names and empty-database migration smoke coverage. | `uv run --dev pytest tests/unit/test_db_migrations.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |

Notes:

- Keep this phase free of placeholder public tools unless tests assert they
  are intentionally unavailable.
- Current slice added only response payload builders in
  `src/dicom_kb/query/answer_contracts.py`; no CLI, MCP, resolver, parser, or
  database behavior is advertised as complete.
- Current schema slice added only contract schemas and tests; no v2 CLI, MCP,
  resolver, parser, or database behavior is advertised as complete.
- Current migration slice added only canonical empty tables and smoke tests;
  no v2 CLI, MCP, resolver, parser, importer, or query behavior is advertised
  as complete.

## Phase 1 - New Part Acquisition and Parser Foundation

Status: `Complete`

Scope:

- Extend acquisition/build paths for PS3.5, PS3.7, PS3.8, PS3.10, PS3.16,
  and PS3.18.
- Add parser modules and synthetic fixtures.
- Store raw table IR and source refs for new part fixtures.

Completion checklist:

- [x] Official artifact configuration supports all v2 parts.
- [x] Parser module for PS3.5 exists and has fixture coverage.
- [x] Parser module for PS3.7 exists and has fixture coverage.
- [x] Parser module for PS3.8 exists and has fixture coverage.
- [x] Parser module for PS3.10 exists and has fixture coverage.
- [x] Parser module for PS3.16 exists and has fixture coverage.
- [x] Parser module for PS3.18 exists and has fixture coverage.
- [x] Build-fixture can include at least one v2 part.
- [x] Import metrics include warnings for v2 parser gaps.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| 3c88a26 | Added the PS3.5 parser scaffold and fixture coverage for recognized VR tables, unsupported-table warnings, source refs, document nodes, and raw table IR. | `uv run --dev pytest tests/unit/test_part05_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| 4672cd0 | Added the PS3.7 parser scaffold and fixture coverage for recognized DIMSE service tables, unsupported-table warnings, source refs, document nodes, and raw table IR. | `uv run --dev pytest tests/unit/test_part07_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| eacda2e | Added the PS3.8 parser scaffold and fixture coverage for recognized association PDU tables, unsupported-table warnings, source refs, document nodes, and raw table IR. | `uv run --dev pytest tests/unit/test_part08_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| 5549b36 | Added the PS3.10 parser scaffold and fixture coverage for recognized file meta information tables, unsupported-table warnings, source refs, document nodes, and raw table IR. | `uv run --dev pytest tests/unit/test_part10_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| d277dd3 | Added the PS3.16 parser scaffold and fixture coverage for recognized SR template tables, unsupported-table warnings, source refs, document nodes, and raw table IR. | `uv run --dev pytest tests/unit/test_part16_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| f7b0ce4 | Added the PS3.18 parser scaffold and fixture coverage for recognized DICOMweb transaction tables, unsupported-table warnings, source refs, document nodes, raw table IR, and build warning aggregation. | `uv run --dev pytest tests/unit/test_part18_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |

Notes:

- This phase should not mark any v2 public tool complete.
- The current slice added tiny synthetic DocBook fixtures for the new v2 parts
  only to exercise generic ingestion; dedicated semantic parser modules are
  still pending.
- The PS3.5 parser scaffold classifies VR behavior tables and reports
  unsupported PS3.5 table shapes as parser warnings. It intentionally does
  not import `vr_definition` or expose encoding query behavior; that remains
  Phase 2 work.
- The PS3.7 parser scaffold classifies DIMSE service tables and reports
  unsupported PS3.7 table shapes as parser warnings. It intentionally does
  not expose messaging query behavior; selected PS3.7 semantics remain Phase
  7 work.
- The PS3.8 parser scaffold classifies association PDU tables and reports
  unsupported PS3.8 table shapes as parser warnings. It intentionally does
  not expose networking query behavior; selected PS3.8 semantics remain Phase
  7 work.
- The PS3.10 parser scaffold classifies file meta information tables and
  reports unsupported PS3.10 table shapes as parser warnings. It intentionally
  does not expose media storage or media type query behavior; PS3.10 file meta
  semantics remain Phase 3 work.
- The PS3.16 parser scaffold classifies SR template summary tables and
  reports unsupported PS3.16 table shapes as parser warnings. It intentionally
  does not expose SR template, context group, or code lookup behavior; PS3.16
  content mapping semantics remain Phase 5 work.
- The PS3.18 parser scaffold classifies DICOMweb transaction summary tables
  and reports unsupported PS3.18 table shapes as parser warnings. It
  intentionally does not expose DICOMweb transaction or media-type lookup
  behavior; PS3.18 web-service semantics remain Phase 4 work.

## Phase 2 - PS3.5 VR and Transfer Syntax Semantics

Status: `Complete`

Scope:

- Parse VR definitions and transfer syntax encoding details.
- Implement `lookup_vr`, `lookup_transfer_syntax`, and
  `explain_encoding_rule`.
- Expose Python, CLI, and MCP surfaces.

Completion checklist:

- [x] `vr_definition` import path exists.
- [x] `transfer_syntax_detail` import path exists.
- [x] Python resolver functions exist and are tested.
- [x] CLI commands exist and have snapshot tests.
- [x] MCP tools exist and have schema tests.
- [x] Official-edition integration goldens cover representative transfer syntaxes.
- [x] V2 acceptance criterion 1 is marked complete.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| fc1d732 | Added PS3.5 VR definition records, row parsing, SQLite import/build wiring, and synthetic fixture coverage for PN, OB, SQ, and UN. | `uv run --dev pytest tests/unit/test_part05_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| 094ab61 | Added `transfer_syntax_detail` records derived from PS3.6 transfer syntax UID rows, SQLite import/build wiring, and synthetic coverage for explicit, implicit, deflated, retired big-endian, and encapsulated JPEG transfer syntaxes. | `uv run --dev pytest tests/unit/test_part05_parser.py tests/unit/test_part06_parser.py tests/unit/test_build.py`; `uv run --dev pytest tests/unit/test_part05_parser.py tests/unit/test_part06_parser.py tests/unit/test_db_importers.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| 56e2592 | Added Python resolver functions for `lookup_vr`, `lookup_transfer_syntax`, and `explain_encoding_rule`, backed by imported PS3.5 VR rows, PS3.6 transfer syntax UID rows, and cited PS3.5 text fallback. | `uv run --dev pytest tests/unit/test_query_resolver.py`; `make lint`; `make typecheck`; `make test` |
| 17124b4 | Added CLI commands for `lookup vr`, `lookup transfer-syntax`, and `explain encoding`, wired to the existing PS3.5 resolver functions with focused CLI coverage. | `uv run --dev pytest tests/unit/test_cli_lookup.py`; `make lint`; `make typecheck`; `make test` |
| 6669d99 | Added MCP tools for `dicom_lookup_vr`, `dicom_lookup_transfer_syntax`, and `dicom_explain_encoding_rule`, wired to the existing PS3.5 resolver functions with focused MCP server and protocol coverage. | `uv run --dev pytest tests/unit/test_mcp_server.py tests/unit/test_mcp_protocol.py tests/agent_regression/test_prompt_cases.py`; `uv run --dev pytest tests/unit/test_mcp_server.py tests/unit/test_mcp_protocol.py tests/agent_regression/test_prompt_cases.py tests/integration_requires_dicom_download/test_eval_runner.py`; `make lint`; `make typecheck`; `make test` |
| 97f40ce | Added representative official-edition integration goldens for `lookup_transfer_syntax` covering implicit, explicit, deflated, and encapsulated transfer syntaxes, with an explicit skip prerequisite for local official KBs that predate Phase 2 rows. | `uv run --dev pytest tests/integration_requires_dicom_download/test_real_kb_goldens.py`; `uv run --dev pytest tests/unit/test_query_resolver.py -k 'lookup_transfer_syntax or explain_encoding_rule_uses_transfer_syntax_details'`; `make lint`; `make typecheck` |
| 899c73c | Derived transfer syntax details during PS3.6 build import so rebuilt official KBs with legacy PS3.3/4/6 manifests still populate Phase 2 rows; corrected the official JPEG Baseline transfer-syntax golden name after the rebuilt KB exercised the test. | `uv run --dev pytest tests/unit/test_build.py`; `uv run --dev dicom-kb build --edition 2026b --force`; `uv run --dev pytest tests/integration_requires_dicom_download/test_real_kb_goldens.py -rs`; `make test-dicom-integration`; `make lint`; `make typecheck`; `make test` |

Notes:

- Retired status continues to come from PS3.6 UID registry rows.
- The transfer syntax detail slice imported transfer syntax details only.
- The resolver slice added Python resolver functions only.
- The CLI slice added CLI commands only.
- The transfer syntax detail import now runs immediately after PS3.6 UID
  registry import, not only when PS3.5 is present, because the detail rows are
  derived from UID registry entries. This lets legacy official caches rebuild
  into the Phase 2 schema and execute the transfer-syntax goldens.
- The local 2026b official KB was rebuilt after this fix and the Phase 2
  official transfer-syntax goldens now execute instead of skipping.

## Phase 3 - PS3.10 File Meta and Media Foundation

Status: `Complete`

Scope:

- Parse file meta information requirements.
- Establish media-type rows that PS3.18 can reuse.
- Implement the PS3.10 baseline for `lookup_media_type`.

Completion checklist:

- [x] File meta requirements are imported with type designations and refs.
- [x] Media-type model has PS3.10 coverage.
- [x] Python lookup path exists.
- [x] CLI command exists.
- [x] MCP tool exists.
- [x] Prose-only file format rules fall back to text retrieval.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| 83a20d3 | Added PS3.10 file meta requirement parsing, SQLite import/build wiring, and synthetic fixture coverage for required and optional file meta rows. | `uv run --dev pytest tests/unit/test_part10_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| ecf2047 | Added PS3.10-derived media type parsing, SQLite import/build wiring, and synthetic fixture coverage for `dicom_media_type` rows. | `uv run --dev pytest tests/unit/test_part10_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| 8109941 | Added the Python `lookup_media_type` resolver for PS3.10-derived media-type rows, including exact media-type lookup, context lookup, not-found/validation responses, and candidate reporting for ambiguous media-type contexts. | `uv run --dev pytest tests/unit/test_query_resolver.py -k media_type`; `uv run --dev pytest tests/unit/test_query_resolver.py`; `make lint`; `make typecheck`; `make test` |
| d2f0b74 | Added the CLI `lookup media-type` command for the existing PS3.10 media-type resolver, returning the same structured tool envelope as the Python API. | `uv run --dev pytest tests/unit/test_cli_lookup.py -k media_type`; `uv run --dev pytest tests/unit/test_cli_lookup.py`; `make lint`; `make typecheck`; `make test` |
| e76cf3a | Added the MCP `dicom_lookup_media_type` tool for the existing PS3.10 media-type resolver, returning the same structured tool envelope as the Python API and CLI. | `uv run --dev pytest tests/unit/test_mcp_server.py tests/unit/test_mcp_protocol.py`; `make lint`; `make typecheck`; `make test` |
| d109214 | Added bounded cited PS3.10 text fallback to `lookup_media_type` for prose-only file-format topics when no parsed media-type row matches. | `uv run --dev pytest tests/unit/test_query_resolver.py -k media_type`; `uv run --dev pytest tests/unit/test_query_resolver.py`; `make lint`; `make typecheck`; `make test` |

Notes:

- Keep PS3.10 file meta lookup separate from full dataset validation.
- The file meta requirement slice imports table rows only. It intentionally
  does not add the `lookup_media_type` resolver, CLI command, or MCP tool.
- The PS3.10 media-type slice imports table rows only. It intentionally does
  not add the `lookup_media_type` resolver, CLI command, or MCP tool.
- The Python media-type resolver slice reads imported `dicom_media_type` rows
  only. It intentionally does not add the CLI command, MCP tool, PS3.18 media
  contexts, or prose-only file format fallback.
- The CLI media-type slice exposes only the existing PS3.10 resolver through
  `dicom-kb lookup media-type`; it intentionally does not add the MCP tool,
  PS3.18 media contexts, or prose-only file format fallback.
- The MCP media-type slice exposes only the existing PS3.10 resolver through
  `dicom_lookup_media_type`; it intentionally does not add PS3.18 media
  contexts or prose-only file format fallback.
- The prose fallback slice keeps parsed PS3.10 media-type rows as the primary
  `lookup_media_type` behavior and returns bounded PS3.10 retrieved text only
  when no parsed row matches a prose-only file-format topic.

## Phase 4 - PS3.18 DICOMweb Transactions

Status: `Complete`

Scope:

- Parse DICOMweb transactions, routes, methods, resources, constraints,
  status codes, and media types.
- Complete `lookup_dicomweb_transaction` and `lookup_media_type`.
- Expose Python, CLI, and MCP surfaces.

Completion checklist:

- [x] DICOMweb transaction rows import from synthetic fixture.
- [x] Route-template matching is deterministic and tested.
- [x] Request and response constraints include source refs.
- [x] Media type lookup includes PS3.18 contexts.
- [x] Python resolver functions exist and are tested.
- [x] CLI commands exist and have snapshot tests.
- [x] MCP tools exist and have schema tests.
- [x] V2 acceptance criterion 2 is marked complete.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| c0f7942 | Added internal PS3.18 DICOMweb transaction parsing, SQLite import/build wiring, and synthetic fixture coverage for route templates, methods, resource categories, request/response constraints, status codes, media-type refs, and source refs. | `uv run --dev pytest tests/unit/test_part18_parser.py tests/unit/test_build.py`; `uv run --dev ruff check src/dicom_kb/parsers/part18_web_services.py src/dicom_kb/db/importers.py src/dicom_kb/build.py src/dicom_kb/ir/models.py tests/unit/test_part18_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| c0f6b87 | Added deterministic Python lookup for imported PS3.18 DICOMweb transaction rows by exact transaction name or route template, returning candidates for ambiguous shared routes instead of guessing. | `uv run --dev pytest tests/unit/test_query_resolver.py -k dicomweb_transaction`; `uv run --dev pytest tests/unit/test_query_resolver.py`; `uv run --dev ruff check src/dicom_kb/db/repositories.py src/dicom_kb/query/resolver.py tests/unit/test_query_resolver.py`; `uv run --dev ruff check .`; `make typecheck`; `uv run --dev pytest` |
| edb457e | Added the CLI `dicom-kb lookup dicomweb <name-or-route>` command for the existing PS3.18 DICOMweb transaction resolver. | `uv run --dev pytest tests/unit/test_cli_lookup.py -k dicomweb`; `uv run --dev pytest tests/unit/test_cli_lookup.py`; `make lint`; `make typecheck`; `make test` |
| 322f2f7 | Added the MCP `dicom_lookup_dicomweb_transaction` tool for the existing PS3.18 DICOMweb transaction resolver. | `uv run --dev pytest tests/unit/test_mcp_server.py tests/unit/test_mcp_protocol.py`; `make lint`; `make typecheck`; `make test` |
| 22ce14e | Added PS3.18 DICOMweb media-type parsing into existing `dicom_media_type` rows, build/import wiring, and lookup coverage across Python, CLI, and MCP surfaces. | `uv run --dev pytest tests/unit/test_part18_parser.py tests/unit/test_build.py tests/unit/test_query_resolver.py -k 'media_type or dicomweb_transaction or build_sqlite_database_imports_manifest_docbook_and_metadata' tests/unit/test_cli_lookup.py -k 'media_type' tests/unit/test_mcp_server.py -k 'media_type' tests/unit/test_mcp_protocol.py`; `make lint`; `make typecheck`; `make test` |

Notes:

- Ambiguous routes must return candidates, not guessed transactions.
- The parser/import slice intentionally did not expose
  `lookup_dicomweb_transaction` through Python, CLI, or MCP. It only imported
  deterministic PS3.18 transaction rows so later slices could add lookup
  behavior against stable table data.
- The Python resolver slice exposes `lookup_dicomweb_transaction` from the
  Python query layer only. It intentionally does not add CLI/MCP behavior or
  PS3.18 media-type expansion.
- The CLI slice exposes only the existing PS3.18 transaction resolver through
  `dicom-kb lookup dicomweb <name-or-route>`. It intentionally does not add
  the MCP tool or PS3.18 media-type expansion.
- The MCP slice exposes only the existing PS3.18 transaction resolver through
  `dicom_lookup_dicomweb_transaction`. It intentionally does not add PS3.18
  media-type expansion.
- The media-type expansion slice parses PS3.18 request/response media-type
  contexts into the existing `dicom_media_type` table and reuses the existing
  `lookup_media_type` Python, CLI, and MCP surfaces.

## Phase 5 - PS3.16 SR Templates, Context Groups, and Codes

Status: `Complete`

Scope:

- Parse TIDs, CIDs, template rows, context-group rows, and coded concepts.
- Implement `lookup_sr_template`, `lookup_context_group`, and
  `lookup_code_meaning`.
- Preserve PS3.16 terminology distribution limits.

Completion checklist:

- [x] TID metadata imports with extensibility.
- [x] TID rows import with relationship/value/cardinality fields.
- [x] CID metadata imports with extensibility.
- [x] CID rows import with code value, scheme, and meaning.
- [x] Code lookup handles ambiguous code values.
- [x] Python resolver functions exist and are tested.
- [x] CLI commands exist and have snapshot tests.
- [x] MCP tools exist and have schema tests.
- [x] Legal/distribution docs are updated if needed.
- [x] V2 acceptance criterion 3 is marked complete.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| 453ab0f | Added PS3.16 SR template metadata and row parsing/import/build wiring from the synthetic fixture. | `uv run --dev pytest tests/unit/test_part16_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| 00fc28e | Added PS3.16 context group metadata and row parsing/import/build wiring from the synthetic fixture. | `uv run --dev pytest tests/unit/test_part16_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| 6d7c53f | Derived PS3.16 coded concepts from parsed context group coded rows, with SQLite import/build wiring and focused coverage. | `uv run --dev pytest tests/unit/test_part16_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| 2deb80c | Added the Python `lookup_code_meaning` resolver for imported PS3.16 coded concepts, with optional scheme filtering and ambiguous code-value candidates. | `uv run --dev pytest tests/unit/test_query_resolver.py -k code_meaning`; `uv run --dev pytest tests/unit/test_query_resolver.py`; `make lint`; `make typecheck`; `make test` |
| e8768e9 | Added the Python `lookup_context_group` resolver for imported PS3.16 context groups, with ordered coded/include rows and ambiguous-name candidates. | `uv run --dev pytest tests/unit/test_query_resolver.py -k context_group`; `uv run --dev pytest tests/unit/test_query_resolver.py`; `make lint`; `make typecheck`; `make test` |
| fa256c6 | Added the Python `lookup_sr_template` resolver for imported PS3.16 SR templates, with ordered content/include rows and ambiguous-name candidates. | `uv run --dev pytest tests/unit/test_query_resolver.py -k sr_template`; `uv run --dev pytest tests/unit/test_query_resolver.py`; `make lint`; `make typecheck`; `make test` |
| 190ab6b | Added the CLI `lookup sr-template` command for the existing Python resolver, with focused CLI coverage against the synthetic PS3.16 fixture. | `uv run --dev pytest tests/unit/test_cli_lookup.py -k sr_template`; `uv run --dev pytest tests/unit/test_cli_lookup.py`; `make lint`; `make typecheck`; `make test` |
| cba86d9 | Added the CLI `lookup context-group` command for the existing Python resolver, with focused CLI coverage against the synthetic PS3.16 fixture. | `uv run --dev pytest tests/unit/test_cli_lookup.py -k context_group`; `uv run --dev pytest tests/unit/test_cli_lookup.py`; `make lint`; `make typecheck`; `make test` |
| ad773ce | Added the CLI `lookup code` command for the existing Python resolver, with focused CLI coverage against the synthetic PS3.16 fixture. | `uv run --dev pytest tests/unit/test_cli_lookup.py -k code`; `uv run --dev pytest tests/unit/test_cli_lookup.py`; `make lint`; `make typecheck`; `make test` |
| 334edf4 | Added the MCP `dicom_lookup_sr_template` tool for the existing Python resolver, with focused MCP server and protocol coverage against the synthetic PS3.16 fixture. | `uv run --dev pytest tests/unit/test_mcp_server.py tests/unit/test_mcp_protocol.py`; sandboxed `make lint`, `make typecheck`, and `make test` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint`; escalated `make typecheck`; escalated `make test` |
| 8cea1ee | Added the MCP `dicom_lookup_context_group` tool for the existing Python resolver, with focused MCP server and protocol coverage against the synthetic PS3.16 fixture. | `uv run --dev pytest tests/unit/test_mcp_server.py tests/unit/test_mcp_protocol.py`; sandboxed `make lint` and `make typecheck` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint`; escalated `make typecheck`; escalated `make test` |
| a9d2574 | Added the MCP `dicom_lookup_code_meaning` tool for the existing Python resolver, with focused MCP server and protocol coverage against the synthetic PS3.16 fixture. | `uv run --dev pytest tests/unit/test_mcp_server.py tests/unit/test_mcp_protocol.py`; sandboxed `make lint`, `make typecheck`, and `make test` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint`; escalated `make typecheck`; escalated `make test` |
| a63a71e | Completed the legal/distribution documentation audit for locally built PS3.16 terminology and added regression coverage that the policy remains documented. | `uv run --dev pytest tests/unit/test_metadata.py`; sandboxed `make lint` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` was rejected by the environment approval policy; `uv run --dev ruff check tests/unit/test_metadata.py`; sandboxed `make typecheck` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make typecheck` |

Notes:

- Do not add bulk terminology export endpoints or generated terminology
  dumps.
- The SR template parser/import slice intentionally did not add
  `lookup_sr_template`, CLI commands, MCP tools, context group parsing, or
  coded concept parsing. It only populated `sr_template` and
  `sr_template_row` rows with source references so later Phase 5 slices could
  build lookup behavior against stable table data.
- The context group parser/import slice intentionally does not add
  `lookup_context_group`, CLI commands, MCP tools, or coded concept parsing.
  It only populates `context_group` and `context_group_row` rows with source
  references so later Phase 5 slices can build lookup behavior against stable
  table data.
- The coded concept parser/import slice intentionally does not add
  `lookup_code_meaning`, CLI commands, or MCP tools. It derives unique
  `coded_concept` rows only from complete context group coded rows and skips
  CID include rows so later lookup slices can handle code-value ambiguity
  against stable table data.
- The code-meaning resolver slice exposes `lookup_code_meaning` from the
  Python query layer only. It intentionally does not add CLI/MCP behavior or
  the TID/CID lookup resolvers. Ambiguous code values return candidates rather
  than a guessed meaning, and exact scheme filtering can select a single
  coded concept.
- The context-group resolver slice exposes `lookup_context_group` from the
  Python query layer only. It intentionally does not add CLI/MCP behavior or
  the SR template lookup resolver. Ambiguous context-group names return
  candidates rather than a guessed group, and include rows are preserved as
  `include_cid` rows in lookup results.
- The SR-template resolver slice exposes `lookup_sr_template` from the Python
  query layer only. It intentionally does not add CLI/MCP behavior or the
  remaining public exposure for Phase 5. Ambiguous template names return
  candidates rather than a guessed template, and include rows are preserved as
  `include_tid` rows in lookup results.
- The SR-template CLI slice exposes only the existing Python resolver through
  `dicom-kb lookup sr-template <tid-or-name>`. It intentionally does not add
  the context-group/code CLI commands or any MCP tools.
- The context-group CLI slice exposes only the existing Python resolver
  through `dicom-kb lookup context-group <cid-or-name>`. It intentionally
  does not add the code CLI command or any MCP tools.
- The code CLI slice exposes only the existing Python resolver through
  `dicom-kb lookup code <code-value> [--scheme <scheme>]`. It intentionally
  does not add any MCP tools or legal/docs updates.
- The SR-template MCP slice exposes only the existing Python resolver through
  `dicom_lookup_sr_template`. It intentionally does not add the
  context-group/code MCP tools or legal/docs updates.
- The context-group MCP slice exposes only the existing Python resolver
  through `dicom_lookup_context_group`. It intentionally does not add the
  code MCP tool or legal/docs updates.
- The code-meaning MCP slice exposes only the existing Python resolver
  through `dicom_lookup_code_meaning`, including optional scheme filtering.
  It intentionally does not add legal/docs updates.

## Phase 6 - Contextual Enumerated Values and Defined Terms

Status: `Complete`

Scope:

- Audit and extend value-term parsing.
- Link enumerated values and defined terms to applicable context.
- Keep existing v2-forward tools consistent across all surfaces.

Completion checklist:

- [x] Existing value-term coverage is documented.
- [x] Context resolver supports deterministic IOD/SOP/module/macro context.
- [x] Ambiguous contexts return candidates or warnings.
- [x] Python, CLI, and MCP tests cover contextual lookups.
- [x] V2 acceptance criterion 4 is marked complete.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| 5c9a5df | Documented the current `attribute_value_term` import and lookup coverage, including deterministic context links already supported and Phase 6 context gaps. | Initial `uv run --dev pytest tests/unit/test_metadata.py` failed on a line-wrapped documentation assertion and was fixed; final `uv run --dev pytest tests/unit/test_metadata.py` passed with 3 passed; `uv run --dev ruff check tests/unit/test_metadata.py` passed; sandboxed `make lint` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; sandboxed `make typecheck` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make typecheck` passed. |
| c13b8f8 | Extended value-term context resolution for exact PS3.3 IOD and PS3.4 SOP Class inputs by resolving them to applicable attribute-use ids through the existing context graph before falling back to text/module/macro matching. | `uv run --dev pytest tests/unit/test_query_resolver.py -k 'value_terms or defined_terms'`; `uv run --dev pytest tests/unit/test_cli_lookup.py -k defined_terms`; `uv run --dev pytest tests/unit/test_mcp_server.py -k defined_terms`; `uv run --dev pytest tests/unit/test_db_importers.py -k attribute_value_terms`; sandboxed `make lint`, `make typecheck`, and `make test` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint`; escalated `make typecheck`; escalated `make test` |
| dbda78e | Added ambiguity handling for contextual value-term lookups so a context that maps to multiple value-term contexts returns candidates instead of a merged answer. | `uv run --dev pytest tests/unit/test_query_resolver.py -k 'value_terms or defined_terms'` passed with 4 passed; `uv run --dev pytest tests/unit/test_cli_lookup.py -k defined_terms` passed with 1 passed; `uv run --dev pytest tests/unit/test_mcp_server.py -k defined_terms` passed with 1 passed; sandboxed `make lint`, `make typecheck`, and `make test` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; escalated `make typecheck` passed; escalated `make test` passed with 295 passed and 4 skipped. |

Notes:

- Do not silently convert defined terms into enumerated values.
- Current value-term lookup supports exact PS3.3 module and macro names in the
  optional text context, resolves exact PS3.3 IOD or PS3.4 SOP Class context
  inputs to their applicable module/macro attribute uses before falling back to
  text context matching, and returns candidate term contexts when a supplied
  context remains ambiguous.

## Phase 7 - Selected PS3.7 and PS3.8 Semantics

Status: `Complete`

Scope:

- Parse selected messaging/networking topics that are useful for coding
  agents.
- Route prose-only rules through cited text retrieval.
- Add agent regression coverage for selected service/networking questions.

Completion checklist:

- [x] PS3.7 selected topic fixture and parser coverage exists.
- [x] PS3.8 selected topic fixture and parser coverage exists.
- [x] Selected deterministic rows remain parser IR; no dedicated public structured query path is advertised for the initial Phase 7 scope.
- [x] Query path returns cited text for prose-only topics.
- [x] V2 acceptance criterion 5 is marked complete after audit.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| 9f24999 | Added selected PS3.7 DIMSE service-behavior parsing for the synthetic C-ECHO fixture and cited PS3.7 `retrieve_standard_text` fallback coverage. | `uv run --dev pytest tests/unit/test_part07_parser.py` passed with 2 passed; `uv run --dev pytest tests/unit/test_query_resolver.py -k 'retrieve_standard_text'` passed with 4 passed and 59 deselected; `uv run --dev pytest tests/unit/test_build.py -k build_sqlite_database_imports_manifest_docbook_and_metadata` passed with 1 passed and 4 deselected; sandboxed `make lint` and `make typecheck` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; escalated `make typecheck` passed. |
| bf6e55a | Added selected PS3.8 association-PDU behavior parsing for the synthetic networking fixture and cited PS3.8 `retrieve_standard_text` fallback coverage. | `uv run --dev pytest tests/unit/test_part08_parser.py` passed with 2 passed; `uv run --dev pytest tests/unit/test_query_resolver.py -k 'retrieve_standard_text'` passed with 5 passed and 59 deselected; `uv run --dev pytest tests/unit/test_build.py -k build_sqlite_database_imports_manifest_docbook_and_metadata` passed with 1 passed and 4 deselected; sandboxed `make lint` and `make typecheck` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; escalated `make typecheck` passed. |
| c9fd4d8 | Added focused agent regression cases and expected tool traces for selected PS3.7/PS3.8 prose retrieval through `retrieve_standard_text`. | `uv run --dev pytest tests/agent_regression/test_prompt_cases.py tests/agent_regression/test_runner.py -k 'prompt_cases or phase7'` passed with 5 passed and 4 deselected; `uv run --dev pytest tests/agent_regression/test_scoring.py -k 'expected_argument_mismatch or required_tools'` passed with 2 passed and 3 deselected; `uv run --dev pytest tests/agent_regression` passed with 14 passed; sandboxed `make lint` and `make typecheck` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; escalated `make typecheck` passed. |
| Pending current commit | Audited PS3.10, PS3.7, and PS3.8 fallback retrieval evidence, marked Phase 7 and acceptance criterion 5 complete, and added a metadata guard for the durable tracker state. | `uv run --dev pytest tests/unit/test_metadata.py tests/agent_regression/test_prompt_cases.py tests/agent_regression/test_runner.py -k 'metadata or phase7 or prompt_cases'` passed with 9 passed and 4 deselected; sandboxed `make lint` and `make typecheck` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; escalated `make typecheck` passed. |

Notes:

- This phase should not claim full PS3.7 or PS3.8 coverage.
- The first PS3.7 slice intentionally keeps selected service behavior as
  parser IR plus generic cited retrieval coverage only; it does not add a new
  public Python, CLI, or MCP tool.
- The first PS3.8 slice intentionally keeps selected association-PDU behavior
  as parser IR plus generic cited retrieval coverage only; it does not add a
  new public Python, CLI, or MCP tool.
- The agent-regression slice intentionally adds only prompt cases and exact
  expected `retrieve_standard_text` traces for selected PS3.7/PS3.8 prose
  questions; it does not add a dedicated messaging or networking lookup tool.
- The Phase 7 audit found the existing PS3.10 `lookup_media_type` prose
  fallback, PS3.7/PS3.8 `retrieve_standard_text` fallback tests, and
  committed agent regression traces sufficient for v2 acceptance criterion 5.

## Phase 8 - Evaluation Harness Expansion

Status: `Complete`

Scope:

- Grow agent regression prompts to at least 100.
- Ensure every v2 tool has deterministic expected tool traces.
- Separate v1 and v2 scorecard reporting if needed.

Completion checklist:

- [x] At least 100 prompt cases exist.
- [x] Every v2 public tool appears in expected traces.
- [x] Unsupported normative claim checks cover v2 topics.
- [x] `tests/agent_regression/` passes.
- [x] V2 acceptance criterion 6 is marked complete.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| d1615de | Added the first focused v2 public-tool prompt batch with deterministic expected traces and reference-agent routing for `lookup_vr`, `lookup_transfer_syntax`, `explain_encoding_rule`, `lookup_media_type`, `lookup_dicomweb_transaction`, `lookup_sr_template`, `lookup_context_group`, and `lookup_code_meaning`. | `uv run --dev pytest tests/unit/test_metadata.py tests/agent_regression/test_prompt_cases.py tests/agent_regression/test_runner.py -k 'metadata or phase8 or prompt_cases or v2_public_tool_batch'` passed with 10 passed and 5 deselected; `uv run --dev pytest tests/agent_regression` passed with 16 passed; sandboxed `make lint` and `make typecheck` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; escalated `make typecheck` passed. |
| b5ee0e2 | Added the second focused v2 prompt batch for unsupported normative-claim checks across transfer syntax, DICOMweb, media type, TID, CID, and code lookup topics, with deterministic traces, reference-runner routes, and focused scoring coverage. | `uv run --dev pytest tests/agent_regression/test_prompt_cases.py tests/agent_regression/test_runner.py tests/agent_regression/test_scoring.py -k 'prompt_cases or v2_unsupported or unsupported_normative'` passed with 8 passed and 11 deselected; `uv run --dev ruff check src/dicom_kb/eval/prompt_cases.py src/dicom_kb/eval/expected_tool_traces.py src/dicom_kb/eval/runner.py tests/agent_regression/test_prompt_cases.py tests/agent_regression/test_runner.py tests/agent_regression/test_scoring.py` passed; `uv run --dev pytest tests/agent_regression` passed with 19 passed; sandboxed `make lint` and `make typecheck` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; escalated `make typecheck` passed. |
| d13365e | Added the final Phase 8 v2 workflow prompt batch with composed public-tool scenarios, deterministic expected traces, focused reference-runner coverage, and metadata/tracker updates. | `uv run --dev pytest tests/agent_regression/test_prompt_cases.py tests/agent_regression/test_runner.py -k 'prompt_cases or v2_workflow'` passed with 8 passed and 7 deselected; `uv run --dev pytest tests/agent_regression` passed with 21 passed; `uv run --dev python - <<'PY' ...` confirmed 101 prompt cases; `uv run --dev pytest tests/unit/test_metadata.py tests/agent_regression/test_prompt_cases.py tests/agent_regression/test_runner.py -k 'phase8 or prompt_cases or v2_workflow'` passed with 9 passed and 10 deselected; `uv run --dev ruff check src/dicom_kb/eval/prompt_cases.py src/dicom_kb/eval/expected_tool_traces.py src/dicom_kb/eval/runner.py tests/agent_regression/test_prompt_cases.py tests/agent_regression/test_runner.py tests/unit/test_metadata.py` passed; sandboxed `make lint` and `make typecheck` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; escalated `make typecheck` passed. |

Notes:

- Keep prompt cases edition-pinned.
- The first Phase 8 slice raised the committed prompt-case count to 77 and
  covers all v2 public tools in expected deterministic traces.
- The second Phase 8 slice raised the prompt-case count to 89 and added
  unsupported normative-claim prompt coverage for transfer syntax, DICOMweb,
  media type, TID, CID, and code lookup topics.
- The final Phase 8 slice raises the prompt-case count to 101 with composed
  v2 workflow cases for VR/value terms, transfer syntax details, DICOMweb
  transactions, media-type constraints, SR templates, context groups, code
  lookup, ambiguous route candidates, and PS3.10 fallback text. This completes
  V2 acceptance criterion 6.

## Phase 9 - V2 Release Hardening

Status: `In progress`

Scope:

- Update user docs.
- Add official-edition integration goldens.
- Confirm packaging and distribution policy.
- Run final release gates.

Completion checklist:

- [x] README documents v2 build and query commands.
- [x] `docs/agent_tools.md` documents all v2 tools.
- [x] `docs/architecture.md` documents v2 entities.
- [x] `docs/release_checklist.md` includes v2 gates.
- [x] Official-edition integration tests cover representative v2 queries.
- [x] Build metrics report v2 parser warning counts by part.
- [x] No official artifacts, generated databases, or terminology dumps are committed.
- [x] `make lint` passes.
- [x] `make typecheck` passes.
- [x] `make test` passes.
- [ ] `make test-dicom-integration` passes or skipped prerequisite is recorded.
- [ ] `make test-dicom-current` passes or skipped prerequisite is recorded.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| def0980 | Documented the v2 default build parts, CLI query commands, and MCP tool names in README and `docs/agent_tools.md`, with focused metadata coverage. | `uv run --dev pytest tests/unit/test_metadata.py` passed with 5 passed after refreshing the stale Phase 8 next-action assertion; sandboxed `make lint` and `make typecheck` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; escalated `make typecheck` passed. |
| ba29b44 | Documented the v2 storage entities and current contextual value-term resolution behavior in `docs/architecture.md`, with focused metadata coverage. | `uv run --dev pytest tests/unit/test_metadata.py` initially failed on line-wrapped architecture wording assertions and passed after the wording was made explicit, with 6 passed. Sandboxed `make lint` and `make typecheck` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; escalated `make typecheck` passed. |
| c7d984a | Documented the v2 release checklist gates, including public tool coverage, official-edition golden expectations, per-part metrics expectations, final verification commands, and distribution audit requirements. | `uv run --dev pytest tests/unit/test_metadata.py` passed with 7 passed. Sandboxed `make lint` and `make typecheck` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; escalated `make typecheck` passed. |
| 2d67f0c | Added representative official-edition integration goldens for PS3.5, PS3.10, PS3.16, PS3.18, and contextual value-term query behavior, with explicit skip prerequisites for local official KBs that predate the relevant v2 rows. | `uv run --dev pytest tests/integration_requires_dicom_download/test_real_kb_goldens.py -rs` passed with 40 passed and 6 skipped; `uv run --dev ruff check tests/integration_requires_dicom_download/test_real_kb_goldens.py` passed; `uv run --dev pytest tests/unit/test_metadata.py` passed with 7 passed; sandboxed `make lint`, `make typecheck`, and `make test-dicom-integration` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; escalated `make typecheck` passed; escalated `make test-dicom-integration` passed with 46 passed and 10 skipped. |
| 2c24e49 | Added `parse_warnings_by_part` to build metrics, CLI build output, and persisted build metadata; synthetic build tests assert the per-part counts and docs name the public metric. | `uv run --dev pytest tests/unit/test_build.py` passed with 5 passed; `uv run --dev pytest tests/unit/test_cli_build.py` passed with 2 passed; `uv run --dev pytest tests/unit/test_metadata.py` passed with 7 passed. Sandboxed `make lint`, `make typecheck`, and `make test` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; escalated `make typecheck` passed; escalated `make test` passed with 312 passed and 10 skipped. |
| Pending current commit | Added a repeatable tracked-file distribution audit for release-forbidden official artifacts, generated databases, vector indexes, generated standard text/JSON paths, official `partNN.xml` files, and standalone terminology dump artifacts. The same test confirms wheel and Docker release inputs stay code-only. | `uv run --dev pytest tests/unit/test_distribution_audit.py tests/unit/test_metadata.py` passed with 9 passed; `uv run --dev ruff check tests/unit/test_distribution_audit.py tests/unit/test_metadata.py` passed; sandboxed `make lint` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` was rejected by the environment approval policy; escalated `make typecheck` passed with no issues in 57 source files. |

Notes:

- This phase is complete only when every v2 acceptance criterion above is
  complete.

## Decision Log

| Date | Decision | Rationale | Commit |
|---|---|---|---|
| 2026-06-14 | Start v2 from documented complete v1 baseline. | `IMPLEMENTATION_REVIEW.md` records all active v1 review findings as resolved. | Initial planning docs commit. |
| 2026-06-14 | Use canonical v2 table names from `IMPLEMENTATION_PLAN.md`: `vr_definition`, `transfer_syntax_detail`, `file_meta_requirement`, `dicom_media_type`, `dicomweb_transaction`, `sr_template`, `sr_template_row`, `context_group`, `context_group_row`, and `coded_concept`. | Parser phases need stable storage targets before new part ingestion begins; JSON-array fields are stored as text for SQLite/PostgreSQL portability until importers add domain models. | 0bbb0fe. |
| 2026-06-14 | Keep the initial Phase 7 PS3.7/PS3.8 slices off the public-tool surface. | The v2 plan allows selected PS3.7/PS3.8 content to be available through structured lookup where possible and cited text retrieval otherwise, and no dedicated public contract exists for these topics yet. Parser IR plus bounded retrieval keeps the repo working without broad tool claims. | 9f24999. |

## Open Questions

| Question | Owner | Status | Resolution |
|---|---|---|---|
| Should PS3.7 and PS3.8 selected scope get dedicated public tools, or feed only cited explanatory lookups? | Codex | Resolved for initial Phase 7 slices | Use parser IR plus existing cited text retrieval only; do not add dedicated public tools without a later explicit contract update. |
| Should `lookup_media_type` return a merged PS3.10/PS3.18 view or context-specific rows only? | Future v2 implementer | Open | Decide during Phase 0 schema design. |
| Which official edition is the first v2 integration baseline? | Future v2 implementer | Open | Pick the locally available concrete edition at Phase 1 start. |
