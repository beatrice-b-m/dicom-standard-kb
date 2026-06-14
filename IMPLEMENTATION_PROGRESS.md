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
| Phase 2 - PS3.5 VR and transfer syntax semantics | In progress | `vr_definition` and `transfer_syntax_detail` import paths plus Python resolver functions are in place; CLI/MCP public surfaces remain pending. |
| Phase 3 - PS3.10 file meta and media foundation | Not started | Prepares shared media-type model. |
| Phase 4 - PS3.18 DICOMweb transactions | Not started | Satisfies v2 acceptance criterion 2. |
| Phase 5 - PS3.16 SR templates, CIDs, and codes | Not started | Satisfies v2 acceptance criterion 3. |
| Phase 6 - Contextual enumerated values and defined terms | Not started | Satisfies v2 acceptance criterion 4. |
| Phase 7 - Selected PS3.7/PS3.8 semantics | Not started | Completes selected networking/messaging scope and text fallback. |
| Phase 8 - Evaluation harness expansion | Not started | Satisfies v2 acceptance criterion 6. |
| Phase 9 - V2 release hardening | Not started | Final docs, integration goldens, metrics, and release gates. |

## Acceptance Criteria Tracker

| # | V2 acceptance criterion | Status | Evidence |
|---|---|---|---|
| 1 | Transfer syntax UID lookups return UID metadata plus encoding refs. | Not started | Pending Phase 2. |
| 2 | DICOMweb transaction lookups return route, method, resource type, request/response constraints, and standard references. | Not started | Pending Phase 4. |
| 3 | TID and CID lookups return structured rows and extensibility metadata. | Not started | Pending Phase 5. |
| 4 | Enumerated values and defined terms link to their attribute context. | Not started | Pending Phase 6. |
| 5 | Fallback text retrieval covers prose-only rules. | Not started | Pending Phases 4, 5, and 7 audit against v2 parts. |
| 6 | At least 100 coding-task regression prompts pass through deterministic tool calls before answer synthesis. | Not started | Pending Phase 8. |

## Active Work

| Field | Value |
|---|---|
| Current phase | Phase 2 - PS3.5 VR and Transfer Syntax Semantics |
| Current owner/agent | Codex |
| Branch | main |
| Last completed commit | 094ab61 |
| Last verification | `uv run --dev pytest tests/unit/test_query_resolver.py` passed with 41 passed; sandboxed `make lint` and `make typecheck` failed because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` initially found import-order and line-length issues and passed after the fix; escalated `make typecheck` passed; escalated `make test` passed with 242 passed and 4 skipped. |
| Current blocker | None |
| Commit-ready summary | Added Python resolver functions for `lookup_vr`, `lookup_transfer_syntax`, and `explain_encoding_rule`, backed by imported `vr_definition` and `transfer_syntax_detail` rows plus cited PS3.5 text fallback. |
| Next recommended action | Continue Phase 2 with CLI commands for `dicom-kb lookup vr <vr>`, `dicom-kb lookup transfer-syntax <uid-or-keyword>`, and `dicom-kb explain encoding <topic>`, using the new Python resolvers and focused snapshot tests. |

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

Status: `In progress`

Scope:

- Parse VR definitions and transfer syntax encoding details.
- Implement `lookup_vr`, `lookup_transfer_syntax`, and
  `explain_encoding_rule`.
- Expose Python, CLI, and MCP surfaces.

Completion checklist:

- [x] `vr_definition` import path exists.
- [x] `transfer_syntax_detail` import path exists.
- [x] Python resolver functions exist and are tested.
- [ ] CLI commands exist and have snapshot tests.
- [ ] MCP tools exist and have schema tests.
- [ ] Official-edition integration goldens cover representative transfer syntaxes.
- [ ] V2 acceptance criterion 1 is marked complete.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| fc1d732 | Added PS3.5 VR definition records, row parsing, SQLite import/build wiring, and synthetic fixture coverage for PN, OB, SQ, and UN. | `uv run --dev pytest tests/unit/test_part05_parser.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| 094ab61 | Added `transfer_syntax_detail` records derived from PS3.6 transfer syntax UID rows, SQLite import/build wiring, and synthetic coverage for explicit, implicit, deflated, retired big-endian, and encapsulated JPEG transfer syntaxes. | `uv run --dev pytest tests/unit/test_part05_parser.py tests/unit/test_part06_parser.py tests/unit/test_build.py`; `uv run --dev pytest tests/unit/test_part05_parser.py tests/unit/test_part06_parser.py tests/unit/test_db_importers.py tests/unit/test_build.py`; `make lint`; `make typecheck`; `make test` |
| Pending current commit | Added Python resolver functions for `lookup_vr`, `lookup_transfer_syntax`, and `explain_encoding_rule`, backed by imported PS3.5 VR rows, PS3.6 transfer syntax UID rows, and cited PS3.5 text fallback. | `uv run --dev pytest tests/unit/test_query_resolver.py`; `make lint`; `make typecheck`; `make test` |

Notes:

- Retired status continues to come from PS3.6 UID registry rows.
- The transfer syntax detail slice imported transfer syntax details only.
- The current slice adds Python resolver functions only. CLI commands, MCP
  tools, and official-edition goldens remain pending.

## Phase 3 - PS3.10 File Meta and Media Foundation

Status: `Not started`

Scope:

- Parse file meta information requirements.
- Establish media-type rows that PS3.18 can reuse.
- Implement the PS3.10 baseline for `lookup_media_type`.

Completion checklist:

- [ ] File meta requirements are imported with type designations and refs.
- [ ] Media-type model has PS3.10 coverage.
- [ ] Python lookup path exists.
- [ ] CLI command exists.
- [ ] MCP tool exists.
- [ ] Prose-only file format rules fall back to text retrieval.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| None | Not started. | None. |

Notes:

- Keep PS3.10 file meta lookup separate from full dataset validation.

## Phase 4 - PS3.18 DICOMweb Transactions

Status: `Not started`

Scope:

- Parse DICOMweb transactions, routes, methods, resources, constraints,
  status codes, and media types.
- Complete `lookup_dicomweb_transaction` and `lookup_media_type`.
- Expose Python, CLI, and MCP surfaces.

Completion checklist:

- [ ] DICOMweb transaction rows import from synthetic fixture.
- [ ] Route-template matching is deterministic and tested.
- [ ] Request and response constraints include source refs.
- [ ] Media type lookup includes PS3.18 contexts.
- [ ] Python resolver functions exist and are tested.
- [ ] CLI commands exist and have snapshot tests.
- [ ] MCP tools exist and have schema tests.
- [ ] V2 acceptance criterion 2 is marked complete.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| None | Not started. | None. |

Notes:

- Ambiguous routes must return candidates, not guessed transactions.

## Phase 5 - PS3.16 SR Templates, Context Groups, and Codes

Status: `Not started`

Scope:

- Parse TIDs, CIDs, template rows, context-group rows, and coded concepts.
- Implement `lookup_sr_template`, `lookup_context_group`, and
  `lookup_code_meaning`.
- Preserve PS3.16 terminology distribution limits.

Completion checklist:

- [ ] TID metadata imports with extensibility.
- [ ] TID rows import with relationship/value/cardinality fields.
- [ ] CID metadata imports with extensibility.
- [ ] CID rows import with code value, scheme, and meaning.
- [ ] Code lookup handles ambiguous code values.
- [ ] Python resolver functions exist and are tested.
- [ ] CLI commands exist and have snapshot tests.
- [ ] MCP tools exist and have schema tests.
- [ ] Legal/distribution docs are updated if needed.
- [ ] V2 acceptance criterion 3 is marked complete.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| None | Not started. | None. |

Notes:

- Do not add bulk terminology export endpoints or generated terminology
  dumps.

## Phase 6 - Contextual Enumerated Values and Defined Terms

Status: `Not started`

Scope:

- Audit and extend value-term parsing.
- Link enumerated values and defined terms to applicable context.
- Keep existing v2-forward tools consistent across all surfaces.

Completion checklist:

- [ ] Existing value-term coverage is documented.
- [ ] Context resolver supports deterministic IOD/SOP/module/macro context.
- [ ] Ambiguous contexts return candidates or warnings.
- [ ] Python, CLI, and MCP tests cover contextual lookups.
- [ ] V2 acceptance criterion 4 is marked complete.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| None | Not started. | None. |

Notes:

- Do not silently convert defined terms into enumerated values.

## Phase 7 - Selected PS3.7 and PS3.8 Semantics

Status: `Not started`

Scope:

- Parse selected messaging/networking topics that are useful for coding
  agents.
- Route prose-only rules through cited text retrieval.
- Add agent regression coverage for selected service/networking questions.

Completion checklist:

- [ ] PS3.7 selected topic fixture and parser coverage exists.
- [ ] PS3.8 selected topic fixture and parser coverage exists.
- [ ] Query path returns structured facts where deterministic.
- [ ] Query path returns cited text for prose-only topics.
- [ ] V2 acceptance criterion 5 is marked complete after audit.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| None | Not started. | None. |

Notes:

- This phase should not claim full PS3.7 or PS3.8 coverage.

## Phase 8 - Evaluation Harness Expansion

Status: `Not started`

Scope:

- Grow agent regression prompts to at least 100.
- Ensure every v2 tool has deterministic expected tool traces.
- Separate v1 and v2 scorecard reporting if needed.

Completion checklist:

- [ ] At least 100 prompt cases exist.
- [ ] Every v2 public tool appears in expected traces.
- [ ] Unsupported normative claim checks cover v2 topics.
- [ ] `tests/agent_regression/` passes.
- [ ] V2 acceptance criterion 6 is marked complete.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| None | Not started. | None. |

Notes:

- Keep prompt cases edition-pinned.

## Phase 9 - V2 Release Hardening

Status: `Not started`

Scope:

- Update user docs.
- Add official-edition integration goldens.
- Confirm packaging and distribution policy.
- Run final release gates.

Completion checklist:

- [ ] README documents v2 build and query commands.
- [ ] `docs/agent_tools.md` documents all v2 tools.
- [ ] `docs/architecture.md` documents v2 entities.
- [ ] `docs/release_checklist.md` includes v2 gates.
- [ ] Official-edition integration tests cover representative v2 queries.
- [ ] Build metrics report v2 parser warning counts by part.
- [ ] No official artifacts, generated databases, or terminology dumps are committed.
- [ ] `make lint` passes.
- [ ] `make typecheck` passes.
- [ ] `make test` passes.
- [ ] `make test-dicom-integration` passes or skipped prerequisite is recorded.
- [ ] `make test-dicom-current` passes or skipped prerequisite is recorded.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| None | Not started. | None. |

Notes:

- This phase is complete only when every v2 acceptance criterion above is
  complete.

## Decision Log

| Date | Decision | Rationale | Commit |
|---|---|---|---|
| 2026-06-14 | Start v2 from documented complete v1 baseline. | `IMPLEMENTATION_REVIEW.md` records all active v1 review findings as resolved. | Initial planning docs commit. |
| 2026-06-14 | Use canonical v2 table names from `IMPLEMENTATION_PLAN.md`: `vr_definition`, `transfer_syntax_detail`, `file_meta_requirement`, `dicom_media_type`, `dicomweb_transaction`, `sr_template`, `sr_template_row`, `context_group`, `context_group_row`, and `coded_concept`. | Parser phases need stable storage targets before new part ingestion begins; JSON-array fields are stored as text for SQLite/PostgreSQL portability until importers add domain models. | 0bbb0fe. |

## Open Questions

| Question | Owner | Status | Resolution |
|---|---|---|---|
| Should PS3.7 and PS3.8 selected scope get dedicated public tools, or feed only cited explanatory lookups? | Future v2 implementer | Open | Decide during Phase 0 contract baseline. |
| Should `lookup_media_type` return a merged PS3.10/PS3.18 view or context-specific rows only? | Future v2 implementer | Open | Decide during Phase 0 schema design. |
| Which official edition is the first v2 integration baseline? | Future v2 implementer | Open | Pick the locally available concrete edition at Phase 1 start. |
