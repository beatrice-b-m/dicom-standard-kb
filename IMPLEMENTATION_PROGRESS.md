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
| Phase 1 - New part acquisition/parser foundation | In progress | Default official DocBook fetch and synthetic build-fixture loading now cover PS3.5, PS3.7, PS3.8, PS3.10, PS3.16, and PS3.18; parser modules still need to be added. |
| Phase 2 - PS3.5 VR and transfer syntax semantics | Not started | Satisfies v2 acceptance criterion 1. |
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
| Current phase | Phase 1 - New Part Acquisition and Parser Foundation |
| Current owner/agent | Codex |
| Branch | main |
| Last completed commit | 0bbb0fe |
| Last verification | `uv run --dev pytest tests/unit/test_sources.py tests/unit/test_build.py tests/unit/test_cli_lookup.py` passed with 43 passed; `make lint` passed; `make typecheck` passed with no issues in 51 source files; `make test` passed with 219 passed, 4 skipped. |
| Current blocker | None |
| Commit-ready summary | Extended the default official DocBook acquisition set and offline build fixture registration to include PS3.5, PS3.7, PS3.8, PS3.10, PS3.16, and PS3.18 without advertising v2 public tools. |
| Next recommended action | Add the PS3.5 parser module scaffold with synthetic fixture coverage for document nodes, source refs, raw table IR, and unsupported-table warnings, without exposing PS3.5 query tools yet. |

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

Status: `In progress`

Scope:

- Extend acquisition/build paths for PS3.5, PS3.7, PS3.8, PS3.10, PS3.16,
  and PS3.18.
- Add parser modules and synthetic fixtures.
- Store raw table IR and source refs for new part fixtures.

Completion checklist:

- [x] Official artifact configuration supports all v2 parts.
- [ ] Parser module for PS3.5 exists and has fixture coverage.
- [ ] Parser module for PS3.7 exists and has fixture coverage.
- [ ] Parser module for PS3.8 exists and has fixture coverage.
- [ ] Parser module for PS3.10 exists and has fixture coverage.
- [ ] Parser module for PS3.16 exists and has fixture coverage.
- [ ] Parser module for PS3.18 exists and has fixture coverage.
- [x] Build-fixture can include at least one v2 part.
- [ ] Import metrics include warnings for v2 parser gaps.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| Pending current commit | Default DocBook acquisition and fixture builds include all v2 parts while preserving source refs and raw table IR through the generic DocBook importer. | `uv run --dev pytest tests/unit/test_sources.py tests/unit/test_build.py tests/unit/test_cli_lookup.py`; `make lint`; `make typecheck`; `make test` |

Notes:

- This phase should not mark any v2 public tool complete.
- The current slice added tiny synthetic DocBook fixtures for the new v2 parts
  only to exercise generic ingestion; dedicated semantic parser modules are
  still pending.

## Phase 2 - PS3.5 VR and Transfer Syntax Semantics

Status: `Not started`

Scope:

- Parse VR definitions and transfer syntax encoding details.
- Implement `lookup_vr`, `lookup_transfer_syntax`, and
  `explain_encoding_rule`.
- Expose Python, CLI, and MCP surfaces.

Completion checklist:

- [ ] `vr_definition` import path exists.
- [ ] `transfer_syntax_detail` import path exists.
- [ ] Python resolver functions exist and are tested.
- [ ] CLI commands exist and have snapshot tests.
- [ ] MCP tools exist and have schema tests.
- [ ] Official-edition integration goldens cover representative transfer syntaxes.
- [ ] V2 acceptance criterion 1 is marked complete.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| None | Not started. | None. |

Notes:

- Retired status should continue to come from PS3.6 UID registry rows.

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
