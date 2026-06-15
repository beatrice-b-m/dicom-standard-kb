# Remediation Progress

This file is the durable handoff point for agents resolving
`IMPLEMENTATION_PLAN_REVIEW.md`. Update it after every completed remediation
slice and before handing work to another agent.

## Handoff Rules

- Read `AGENTS.md`, `REMEDIATION_PLAN.md`, `REMEDIATION_PROGRESS.md`, and
  `IMPLEMENTATION_PLAN_REVIEW.md` before selecting work.
- Use `REMEDIATION_PROGRESS.md` as durable memory. Do not rely on chat
  history.
- Keep the newest status accurate. Do not leave a phase marked `In progress`
  when no actionable work remains in the current commit.
- Add the commit hash for every completed remediation unit after running
  `git log --oneline -3`.
- Record exact verification commands and results. If a check was skipped,
  state the missing prerequisite.
- Record blockers as concrete next actions, not general uncertainty.
- Do not mark a remediation phase complete while its release-gate or scoring
  invariant can still be satisfied by the false-positive behavior described in
  `IMPLEMENTATION_PLAN_REVIEW.md`.
- Respect the repository distribution invariant: do not commit official DICOM
  artifacts, generated full databases, vector indexes, or standalone
  terminology dumps.

Status values:

- `Not started`
- `In progress`
- `Blocked`
- `Complete`

## Current Summary

| Area | Status | Notes |
|---|---|---|
| Planning scaffold | Complete | `REMEDIATION_PLAN.md` and this progress tracker exist. |
| Phase R0 - Reproduce and inventory the gap | Complete | Local 2026b official cache contains only PS3.3/PS3.4/PS3.6; named v2 semantic lookups return `not_found`, while current official goldens pass with skips and agent regression passes. |
| Phase R1 - Separate smoke tests from release gates | Complete | Strict release requirement helper checks required DocBook parts, semantic rows, and citation-preserving DocBook structure; `make test-dicom-release` now runs the strict opt-in gate and rejects the current PS3.3/PS3.4/PS3.6-only local official KB while smoke integration remains separate. |
| Phase R2 - Repair official-shape PS3.16 ingestion | Complete | Official-shape parser, build/import, and resolver coverage now proves TID 1500, CID 29, and CT/DCM fixture rows persist with PS3.16 citations and return `ok`. |
| Phase R3 - Pin strict official goldens | Complete | Strict release-only positive tests now pin PN, application/dicom, RetrieveStudy, TID 1500, CID 29, and CT/DCM and fail on `not_found`, missing fields, or missing required-part citations. |
| Phase R4 - Harden agent regression scoring | Complete | Positive v2 expected traces now require `ok` status and required-part citations; reference answers derive terms from observed tool responses instead of prompt fixtures, and positive v2 semantic cases no longer receive generic fallback citations. |
| Phase R5 - Reconcile completion state and final gates | Complete | Historical reconciliation completed in `44eb4df`, but post-completion review found narrower release-gate coverage and remaining official-data quality gaps. Treat R6-R10 as the active remediation tranche before marking the overall effort complete again. |
| Phase R6 - Capture post-completion review findings | In progress | This documentation update records the 2026-06-15 review findings and reopens remediation with concrete next phases. |
| Phase R7 - Repair official PS3.18 DICOMweb and media ingestion | Not started | `StoreInstances`, `WADO-RS response`, and `STOW-RS request` return `not_found`; `RetrieveStudy` resolves but includes unrelated response text. |
| Phase R8 - Align real-KB eval and release gates with promised workflows | Not started | Real-KB eval excludes positive DICOMweb/media workflow cases, and strict release goldens do not cover the missing workflow examples. |
| Phase R9 - Repair PS3.16 SR template concept names | Not started | Official TID 1500 rows expose compact `D`, `B`, or `null` concept names when xref-backed target labels are available. |
| Phase R10 - Final post-review reconciliation | Not started | Must run only after R7-R9 are fixed and verified. |

## Active Work

| Field | Value |
|---|---|
| Current phase | Phase R6 - Capture post-completion review findings |
| Current owner/agent | Codex |
| Branch | main |
| Last completed remediation commit | `44eb4df` added official-shape PS3.16 parsing/importing, route-template placeholder canonicalization, and final R5 release evidence. |
| Last verification | Post-completion review on 2026-06-15 reran focused parser/resolver tests and the strict release target. Focused tests passed, and escalated `make test-dicom-release` passed with 7 passed. Direct official-KB spot checks then exposed remaining gaps: `StoreInstances`, `WADO-RS response`, and `STOW-RS request` return `not_found`; `RetrieveStudy` returns `ok` but includes unrelated response prose; TID 1500 rows expose compact concept names such as `D`, `B`, and `null`. |
| Current blocker | Remediation is reopened. R7 must repair PS3.18 official DICOMweb/media parsing, R8 must align real-KB eval and release gates with promised workflows, and R9 must repair PS3.16 concept-name payload quality. |
| Commit-ready summary | Documents the post-completion review findings in `REMEDIATION_PLAN.md` and `REMEDIATION_PROGRESS.md` so agents can resolve R7-R10. |
| Next recommended action | Start Phase R7 by fixing official PS3.18 transaction overview/resource matching and adding failing goldens for `StoreInstances`, `WADO-RS response`, and `STOW-RS request`. |

## Post-Completion Review Findings

Review date: 2026-06-15.

The strict release gate now passes, but that result is narrower than the v2
workflow surface still described by the eval cases. These findings reopen
remediation through phases R6-R10 in `REMEDIATION_PLAN.md`.

- PS3.18 transaction/resource matching is too broad. `RetrieveStudy` returns
  `ok`, but the official 2026b payload includes response text unrelated to
  RetrieveStudy, including Modality Performed Procedure Step prose. Next agents
  should inspect overview/resource matching in `part18_web_services.py` and add
  tests that assert semantically relevant RetrieveStudy payloads, not merely
  nonempty constraints.
- Promised DICOMweb/media workflow examples remain unresolved against the
  rebuilt official 2026b KB:
  - `uv run --dev dicom-kb lookup dicomweb StoreInstances --edition 2026b`
    returned `status: not_found`.
  - `uv run --dev dicom-kb lookup media-type "WADO-RS response" --edition 2026b`
    returned `status: not_found`.
  - `uv run --dev dicom-kb lookup media-type "STOW-RS request" --edition 2026b`
    returned `status: not_found`.
- Real-KB eval currently excludes positive workflow cases
  `agent.v2.media_type.dicom_file`,
  `agent.v2.workflow.dicomweb_retrieve_media_type`, and
  `agent.v2.workflow.dicomweb_store_media_type`. These exclusions must be
  removed after data support lands, or converted into explicit product-scope
  decisions with tests enforcing that boundary.
- The strict release gate covers PN, application/dicom, RetrieveStudy, TID
  1500, CID 29, and CT/DCM, but it does not cover `StoreInstances`,
  `WADO-RS response`, or `STOW-RS request`. R8 should expand release goldens or
  release workflow checks so these examples cannot regress silently.
- PS3.16 TID 1500 rows resolve, but public `concept_name` values still include
  compact official display markers such as `D`, `B`, and `null` when xref-backed
  target labels are available. R9 should preserve include targets while
  resolving xrefs into useful concept-name payload text.

## Phase R5 Unblock Evidence

Verification date: 2026-06-15.

- Local cache selected by the integration fixtures: edition `2026b` from
  `/Users/beatrice/.cache/dicom-standard-kb`, resolved from `current`.
- `uv run --dev dicom-kb verify --edition 2026b`: passed with `status: ok`
  for the manifest and database.
- Manifest and build metadata now cover DocBook XML artifacts for:
  `PS3.3`, `PS3.4`, `PS3.5`, `PS3.6`, `PS3.7`, `PS3.8`, `PS3.10`,
  `PS3.16`, and `PS3.18`.
- Citation-preserving structure exists for every required part:
  `doc_node` rows are present for each part, and `raw_table_ir` rows are
  present for each part.
- Required semantic row counts in the rebuilt official DB after the PS3.16
  official-shape slice:
  - `vr_definition`: 34
  - `transfer_syntax_detail`: 63
  - `file_meta_requirement`: 15
  - `dicom_media_type`: 1
  - `dicomweb_transaction`: 42
  - `sr_template`: 405
  - `sr_template_row`: 4295
  - `context_group`: 1436
  - `context_group_row`: 17211
  - `coded_concept`: 14177
  - `attribute_value_term`: 4644
- Stored build metrics loaded all required parts and recorded parser warnings
  by part including `PS3.16`: 397 and `PS3.18`: 190 after the final rebuild.
- `make test-dicom-release` passes the strict prerequisite test and all six
  pinned v2 release goldens: PN, application/dicom, RetrieveStudy, TID 1500,
  CID 29, and CT/DCM. Post-completion review found that these six goldens are
  not sufficient to prove all promised DICOMweb/media workflow examples.

## Phase R0 - Reproduce and Inventory the Gap

Status: `Complete`

Scope:

- Capture the current false-positive release-gate evidence.
- Record local official edition and manifest coverage.
- Record required v2 semantic table row counts.
- Record named CLI spot checks and current integration skip behavior.

Completion checklist:

- [x] Manifest part inventory recorded.
- [x] Required semantic table row counts recorded.
- [x] CLI spot checks recorded for PN, application/dicom, RetrieveStudy,
      TID 1500, CID 29, and CT/DCM.
- [x] Current official golden skip/pass behavior recorded.
- [x] Current agent regression behavior recorded.
- [x] Next code slice selected.

Evidence:

- Local cache selected by the integration fixtures: edition `2026b` from
  `/Users/beatrice/.cache/dicom-standard-kb`, resolved from `current`.
- Manifest part inventory:
  - `PS3.3`: `docbook_xml`
  - `PS3.4`: `docbook_xml`
  - `PS3.6`: `docbook_xml`
  - Missing required v2 release parts: `PS3.5`, `PS3.7`, `PS3.8`,
    `PS3.10`, `PS3.16`, and `PS3.18`.
- Required semantic row counts in
  `/Users/beatrice/.cache/dicom-standard-kb/db/2026b.sqlite`:
  - `vr_definition`: 0
  - `transfer_syntax_detail`: 63
  - `file_meta_requirement`: 0
  - `dicom_media_type`: 0
  - `dicomweb_transaction`: 0
  - `sr_template`: 0
  - `sr_template_row`: 0
  - `context_group`: 0
  - `context_group_row`: 0
  - `coded_concept`: 0
  - `attribute_value_term`: 4644
- CLI spot checks against edition `2026b`:
  - `uv run --dev dicom-kb lookup vr PN --edition 2026b`: `not_found`
    with message `No PS3.5 VR definition matched the input.`
  - `uv run --dev dicom-kb lookup media-type application/dicom --edition 2026b`:
    `not_found` with message `No DICOM media type matched the input.`
  - `uv run --dev dicom-kb lookup dicomweb RetrieveStudy --edition 2026b`:
    `not_found` with message `No DICOMweb transaction matched the input.`
  - `uv run --dev dicom-kb lookup sr-template 1500 --edition 2026b`:
    `not_found` with message `No PS3.16 SR template matched the input.`
  - `uv run --dev dicom-kb lookup context-group 29 --edition 2026b`:
    `not_found` with message `No PS3.16 context group matched the input.`
  - `uv run --dev dicom-kb lookup code CT --scheme DCM --edition 2026b`:
    `not_found` with message `No PS3.16 coded concept matched the input.`
- Current gate behavior:
  - `uv run --dev pytest tests/integration_requires_dicom_download/test_real_kb_goldens.py -rs`:
    passed with 40 passed and 6 skipped. The skipped prerequisites were
    missing `vr_definition`, missing PS3.10 `dicom_media_type`, missing
    PS3.18 `dicomweb_transaction`, missing PS3.16 `sr_template`, missing
    PS3.16 `context_group`, and missing PS3.16 `coded_concept` rows.
  - `uv run --dev pytest tests/agent_regression`: passed with 21 passed.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| bd87e30 | Recorded manifest, row-count, CLI spot-check, official-golden skip, and agent-regression baseline evidence. | `uv run --dev pytest tests/integration_requires_dicom_download/test_real_kb_goldens.py -rs`; `uv run --dev pytest tests/agent_regression` |

Notes:

- This phase did not change production behavior.

## Phase R1 - Separate Smoke Tests from Release Gates

Status: `Complete`

Scope:

- Add strict official-KB prerequisite checks.
- Separate reduced-cache smoke tests from release gates.
- Ensure release documentation and Makefile targets call the strict gate.

Completion checklist:

- [x] Strict helper requires the full v2 official part set.
- [x] Strict helper requires nonzero rows for all required v2 semantic tables.
- [x] Strict helper checks citation-preserving DocBook structure for v2 parts.
- [x] Reduced-cache smoke tests remain available.
- [x] Release gate target rejects PS3.3/PS3.4/PS3.6-only official KBs.
- [x] Release checklist names the strict gate.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| 5aff662 | Added the strict release requirement helper and focused unit tests. | `uv run --dev pytest tests/unit/test_release_requirements.py`; `make lint`; `make typecheck` |
| 87cd1be | Added the opt-in strict release-gate target and integration test while keeping smoke integration separate. | `uv run --dev pytest tests/unit/test_makefile.py tests/unit/test_metadata.py tests/unit/test_release_requirements.py tests/integration_requires_dicom_download/test_release_gate.py -rs`; `make test-dicom-release`; `make lint`; `make typecheck`; `make test`; `make test-dicom-integration` |

## Phase R2 - Repair Official-Shape PS3.16 Ingestion

Status: `Complete`

Scope:

- Add official-shape PS3.16 fixtures.
- Parse TID/CID metadata from official section or table metadata.
- Parse official SR template, context group, include, and coded-concept rows.
- Keep existing synthetic coverage working.

Completion checklist:

- [x] Official-shape TID 1500 fixture parses.
- [x] Official-shape CID 29 fixture parses.
- [x] Official-shape CT/DCM code row parses.
- [x] Import/build tests persist PS3.16 rows with citations.
- [x] Resolver tests return `ok` for TID 1500, CID 29, and CT/DCM fixture data.
- [x] Existing synthetic PS3.16 tests still pass.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| 507d1cd | Added official-shape PS3.16 parser support for TID/CID metadata in section or table titles, official SR template row headers, CID code rows, and CID include xrefs. | `uv run --dev pytest tests/unit/test_part16_parser.py -q`; `uv run --dev pytest tests/unit/test_build.py tests/unit/test_query_resolver.py -k 'part16 or sr_template or context_group or code_meaning' -q`; `uv run --dev pytest tests/unit/test_part16_parser.py tests/unit/test_build.py tests/unit/test_query_resolver.py -k 'part16 or sr_template or context_group or code_meaning' -q`; `uv run --dev ruff check src/dicom_kb/parsers/part16_content_mapping.py tests/unit/test_part16_parser.py tests/fixtures_synthetic/__init__.py`; `make lint`; `make typecheck` could not run because sandboxed uv cache access failed and escalated `make typecheck` was rejected. |
| 0571440 | Added official-shape PS3.16 build/import coverage and resolver coverage proving TID 1500, CID 29, and CT/DCM rows persist with PS3.16 citations and return `ok`. | `uv run --dev pytest tests/unit/test_build.py tests/unit/test_query_resolver.py -k 'official_shape or part16 or sr_template or context_group or code_meaning' -q`; `uv run --dev pytest tests/unit/test_part16_parser.py tests/unit/test_build.py tests/unit/test_query_resolver.py -k 'official_shape or part16 or sr_template or context_group or code_meaning' -q`; `make lint`; `make typecheck` |

## Phase R3 - Pin Strict Official Goldens

Status: `Complete`

Scope:

- Add exact official positive tests for named v2 examples.
- Remove fallback-to-any-row behavior from release-golden helpers.
- Fail on `not_found`, missing result fields, or missing required-part refs.

Completion checklist:

- [x] Strict PN VR official golden requires PS3.5 citation.
- [x] Strict application/dicom official golden requires PS3.10 or PS3.18 citation.
- [x] Strict RetrieveStudy official golden requires PS3.18 citation.
- [x] Strict TID 1500 official golden requires PS3.16 citation and rows.
- [x] Strict CID 29 official golden requires PS3.16 citation and rows.
- [x] Strict CT/DCM official golden requires PS3.16 citation.
- [x] Flexible discovery tests are clearly smoke-only.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| bc8075f | Added release-only strict positive official goldens for PN, application/dicom, RetrieveStudy, TID 1500, CID 29, and CT/DCM, and wired them into `make test-dicom-release` while keeping flexible discovery goldens as smoke coverage. | `uv run --dev pytest tests/unit/test_makefile.py tests/unit/test_metadata.py tests/integration_requires_dicom_download/test_release_gate.py tests/integration_requires_dicom_download/test_release_goldens.py -rs`; `uv run --dev ruff check tests/integration_requires_dicom_download/test_release_goldens.py tests/unit/test_makefile.py tests/unit/test_metadata.py`; `make test`; `make test-dicom-release`; `make lint` |

## Phase R4 - Harden Agent Regression Scoring

Status: `Complete`

Scope:

- Require positive expected v2 semantic tools to return `ok`.
- Require citations from the expected standard part.
- Prevent unrelated fallback calls from satisfying v2 semantic evidence.
- Build required answer content from actual tool payloads.

Completion checklist:

- [x] Expected trace metadata can declare required status and required parts.
- [x] Scoring fails positive v2 cases with `not_found` expected tool results.
- [x] Scoring fails positive v2 cases with wrong-part citations.
- [x] Runner no longer injects fixture-only required terms for missing facts.
- [x] Generic source-reference fallback cannot satisfy positive v2 semantic cases.
- [x] Unsupported/negative cases still assert their expected non-`ok` behavior.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| 0930013 | Added positive v2 expected-call response requirements, response citation parts in reference transcripts, scorer failures for `not_found` and wrong-part citations, and a release-ready prerequisite skip for the real-KB eval smoke integration. | `uv run --dev pytest tests/agent_regression tests/integration_requires_dicom_download/test_eval_runner.py -rs`; `uv run --dev ruff check src/dicom_kb/eval/expected_tool_traces.py src/dicom_kb/eval/scoring.py src/dicom_kb/eval/runner.py src/dicom_kb/eval/prompt_cases.py tests/agent_regression/test_scoring.py tests/integration_requires_dicom_download/test_eval_runner.py`; `make lint`; `make typecheck`; `make test` |
| 0e572a4 | Derived reference-answer content from observed response terms, omitted fixture-only v2 facts when supporting tools returned `not_found`, scoped generic fallback citations away from positive v2 semantic cases, and updated synthetic fixtures so workflow prompts have payload-backed evidence. | `uv run --dev pytest tests/agent_regression -q`; `uv run --dev pytest tests/integration_requires_dicom_download/test_eval_runner.py -rs`; `uv run --dev pytest tests/agent_regression tests/unit/test_db_importers.py tests/unit/test_part07_parser.py tests/unit/test_part08_parser.py tests/unit/test_query_resolver.py -q`; `uv run --dev ruff check src/dicom_kb/eval/runner.py src/dicom_kb/eval/scoring.py tests/agent_regression/test_runner.py tests/unit/test_db_importers.py tests/unit/test_part07_parser.py tests/unit/test_part08_parser.py tests/unit/test_query_resolver.py`; `make lint`; `make typecheck`; `make test` |

## Phase R5 - Reconcile Completion State and Final Gates

Status: `Complete`

Scope:

- Reconcile `IMPLEMENTATION_PROGRESS.md` with repaired release evidence.
- Update release documentation for strict gate commands.
- Run and record final verification.
- Confirm distribution constraints.

Completion checklist:

- [x] `IMPLEMENTATION_PROGRESS.md` reflects repaired evidence or explicit blockers.
- [x] Release docs name the strict official gate.
- [x] `make lint` recorded.
- [x] `make typecheck` recorded.
- [x] `make test` recorded.
- [x] `make test-dicom-current` recorded.
- [x] Strict official release gate recorded.
- [x] Distribution audit confirms no forbidden generated/official artifacts are tracked.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| 44eb4df | Added official-shape PS3.16 parsing/import evidence, fixed coded-concept ID collisions, aligned release-ready real-KB eval behavior, and recorded final R5 gates. | `uv run --dev pytest tests/unit/test_part16_parser.py tests/unit/test_build.py tests/unit/test_query_resolver.py tests/agent_regression tests/integration_requires_dicom_download/test_eval_runner.py -k 'official_shape or part16 or sr_template or context_group or code_meaning or dicomweb_transaction or media_type or prompt_cases or reference_agent or scoring' -rs`; `uv run --dev ruff check ...`; `uv run --dev dicom-kb build --edition 2026b --force`; `make lint`; `make typecheck`; `make test`; `make test-dicom-current`; `make test-dicom-release` |

## Phase R6 - Capture Post-Completion Review Findings

Status: `In progress`

Scope:

- Record post-completion review evidence from 2026-06-15.
- Reopen remediation around concrete R7-R10 follow-up phases.
- Preserve R0-R5 historical completion while making clear that overall
  remediation is not complete again until the post-review findings are fixed.

Completion checklist:

- [x] `REMEDIATION_PLAN.md` includes R6-R10 post-review phases.
- [x] `REMEDIATION_PROGRESS.md` records direct official-KB lookup failures.
- [x] `REMEDIATION_PROGRESS.md` records the real-KB eval exclusions that hide
      positive workflow cases.
- [x] Historical R5 `Pending current commit` marker is replaced with `44eb4df`.
- [ ] Current documentation update is committed and verified with
      `git log --oneline -3`.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| Pending current commit | Documents post-completion review findings and reopens remediation with R7-R10. | `uv run --dev pytest tests/unit/test_metadata.py -q`; `git log --oneline -3` |

## Phase R7 - Repair Official PS3.18 DICOMweb and Media Ingestion

Status: `Not started`

Scope:

- Fix official PS3.18 transaction overview/resource matching.
- Add exact parser/resolver coverage for `RetrieveStudy`, `StoreInstances`,
  `WADO-RS response`, and `STOW-RS request`.
- Strengthen release checks so these examples cannot be missing while release
  evidence is marked complete.

Completion checklist:

- [ ] `RetrieveStudy` response constraints no longer contain unrelated
      transaction prose.
- [ ] `lookup_dicomweb_transaction("StoreInstances")` returns `ok` against the
      rebuilt official KB.
- [ ] `lookup_media_type("WADO-RS response")` returns `ok` against the rebuilt
      official KB.
- [ ] `lookup_media_type("STOW-RS request")` returns `ok` against the rebuilt
      official KB.
- [ ] Strict release or release-workflow tests fail when any of the above
      examples is missing.

## Phase R8 - Align Real-KB Eval and Release Gates With Promised Workflows

Status: `Not started`

Scope:

- Remove temporary real-KB eval exclusions for positive DICOMweb/media workflow
  cases once R7 data exists.
- Decide and document whether `agent.v2.media_type.dicom_file` is release scope
  or an explicit product limitation.
- Make release requirements depend on exact promised workflow examples, not
  only nonzero semantic row counts.

Completion checklist:

- [ ] `agent.v2.workflow.dicomweb_retrieve_media_type` runs against the
      release-ready official KB.
- [ ] `agent.v2.workflow.dicomweb_store_media_type` runs against the
      release-ready official KB.
- [ ] `agent.v2.media_type.dicom_file` is either supported in real-KB eval or
      documented as out of scope with tests enforcing that boundary.
- [ ] Release tests fail if exact positive DICOMweb/media workflow examples are
      absent.

## Phase R9 - Repair PS3.16 SR Template Concept Names

Status: `Not started`

Scope:

- Resolve official compact concept-cell markers such as `D` and `B` through
  their DocBook xrefs when target labels are available.
- Keep include target extraction intact.
- Define test-backed behavior for genuinely blank official concept names.

Completion checklist:

- [ ] Official-shape parser tests assert useful TID 1500 concept-name text for
      xref-backed cells.
- [ ] Resolver tests prove `lookup_sr_template("1500")` does not expose only
      `D`, `B`, or `null` when an xref label is available.
- [ ] Context-group and coded-concept resolver tests continue to pass.

## Phase R10 - Final Post-Review Reconciliation

Status: `Not started`

Scope:

- Record R7-R9 completed commits and final verification.
- Update `IMPLEMENTATION_PROGRESS.md` only after post-review findings are fixed
  or explicitly scoped out.
- Confirm no stale `Pending current commit` markers remain.
- Confirm distribution constraints still hold.

Completion checklist:

- [ ] `make lint` recorded.
- [ ] `make typecheck` recorded.
- [ ] `make test` recorded.
- [ ] `make test-dicom-current` recorded.
- [ ] `make test-dicom-release` recorded.
- [ ] Overall remediation marked complete only after open findings are closed or
      explicitly scoped out.

## Blockers and Open Decisions

- PS3.18 parser correctness is an active blocker for completion: direct
  official-KB lookups show `StoreInstances`, `WADO-RS response`, and
  `STOW-RS request` return `not_found`, while `RetrieveStudy` has unrelated
  response prose.
- Real-KB eval excludes positive DICOMweb/media workflow cases. This is a test
  coverage blocker until R8 removes the exclusions or records an explicit
  product-scope decision.
- PS3.16 SR template concept-name quality remains open for official rows that
  use compact xref markers.

## Verification Log

| Date | Command | Result | Notes |
|---|---|---|---|
| 2026-06-14 | `bash -n scripts/run_codex_remediation.sh` | Passed | Validated the ignored remediation runner syntax. |
| 2026-06-14 | `/usr/bin/perl -e 'alarm 5; exec @ARGV' scripts/run_codex_remediation.sh --dry-run --output-dir /tmp/dicom-kb-remediation-dry-run2` | Passed | Bounded dry run printed the generated remediation prompt. |
| 2026-06-14 | `jq -r '.edition as $edition \| .resolved_from as $resolved \| "edition=\\($edition) resolved_from=\\($resolved)", (.artifacts \| group_by(.part)[] \| "\\(.[0].part): " + (map(.format) \| unique \| join(",")))' /Users/beatrice/.cache/dicom-standard-kb/artifacts/2026b/manifest.json` | Passed | Reported edition `2026b`, resolved from `current`, with only PS3.3, PS3.4, and PS3.6 DocBook XML artifacts. |
| 2026-06-14 | `sqlite3 /Users/beatrice/.cache/dicom-standard-kb/db/2026b.sqlite "SELECT 'vr_definition', COUNT(*) FROM vr_definition UNION ALL ..."` | Passed | Recorded required v2 semantic table row counts in Phase R0 evidence. |
| 2026-06-14 | `uv run --dev dicom-kb lookup vr PN --edition 2026b` | Passed command; returned `not_found` | Missing PS3.5 VR definition. |
| 2026-06-14 | `uv run --dev dicom-kb lookup media-type application/dicom --edition 2026b` | Passed command; returned `not_found` | Missing PS3.10/PS3.18 media-type rows. |
| 2026-06-14 | `uv run --dev dicom-kb lookup dicomweb RetrieveStudy --edition 2026b` | Passed command; returned `not_found` | Missing PS3.18 DICOMweb transaction rows. |
| 2026-06-14 | `uv run --dev dicom-kb lookup sr-template 1500 --edition 2026b` | Passed command; returned `not_found` | Missing PS3.16 SR template rows. |
| 2026-06-14 | `uv run --dev dicom-kb lookup context-group 29 --edition 2026b` | Passed command; returned `not_found` | Missing PS3.16 context group rows. |
| 2026-06-14 | `uv run --dev dicom-kb lookup code CT --scheme DCM --edition 2026b` | Passed command; returned `not_found` | Missing PS3.16 coded concept rows. |
| 2026-06-14 | `uv run --dev pytest tests/integration_requires_dicom_download/test_real_kb_goldens.py -rs` | Passed | 40 passed, 6 skipped; skipped v2 goldens for missing VR, media-type, DICOMweb, SR template, context group, and coded-concept rows. |
| 2026-06-14 | `uv run --dev pytest tests/agent_regression` | Passed | 21 passed, confirming current agent regression still passes against the reduced official KB. |
| 2026-06-14 | `uv run --dev pytest tests/unit/test_release_requirements.py` | Passed | 4 passed; covers complete, missing DocBook part, missing semantic rows, and missing DocBook structure scenarios for the strict release requirement helper. |
| 2026-06-14 | `make lint` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev ruff check .` with all checks passed. |
| 2026-06-14 | `make typecheck` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev mypy` with no issues in 57 source files. |
| 2026-06-14 | `uv run --dev pytest tests/unit/test_makefile.py tests/unit/test_metadata.py tests/integration_requires_dicom_download/test_release_gate.py tests/integration_requires_dicom_download/test_release_goldens.py -rs` | Passed | 8 passed and 7 skipped; release-gate tests are opt-in without `DICOM_KB_RUN_RELEASE=1`. |
| 2026-06-14 | `uv run --dev ruff check tests/integration_requires_dicom_download/test_release_goldens.py tests/unit/test_makefile.py tests/unit/test_metadata.py` | Passed | Focused lint for the new release-golden tests and target/docs assertions. |
| 2026-06-14 | `make test` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun passed with 321 passed and 17 skipped. |
| 2026-06-14 | `make test-dicom-release` | Failed in sandbox; failed as expected escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun executed the strict gate and failed against the reduced local 2026b KB with 7 failures: the prerequisite test rejected missing v2 DocBook parts, semantic rows, and DocBook structure, and the six pinned v2 examples returned `not_found`. |
| 2026-06-14 | `make lint` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev ruff check .` with all checks passed. |
| 2026-06-14 | `uv run --dev pytest tests/unit/test_makefile.py tests/unit/test_metadata.py tests/unit/test_release_requirements.py tests/integration_requires_dicom_download/test_release_gate.py -rs` | Passed | 12 passed, 1 skipped; the strict release gate is skipped unless `DICOM_KB_RUN_RELEASE=1` is set. |
| 2026-06-14 | `make test-dicom-release` | Failed as expected | Escalated rerun executed the strict release gate and rejected the reduced local 2026b KB: missing DocBook artifacts for PS3.10, PS3.16, PS3.18, PS3.5, PS3.7, and PS3.8; missing v2 semantic rows; missing DocBook structure rows for the same v2 parts. |
| 2026-06-14 | `make lint` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev ruff check .` with all checks passed. |
| 2026-06-14 | `make typecheck` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev mypy` with no issues in 57 source files. |
| 2026-06-14 | `make test` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun passed with 318 passed and 11 skipped. |
| 2026-06-14 | `make test-dicom-integration` | Passed escalated | Existing smoke integration remains separate from the strict release gate; 46 passed and 11 skipped. |
| 2026-06-14 | `uv run --dev pytest tests/unit/test_metadata.py` | Passed | 7 passed after tracker reconciliation. |
| 2026-06-14 | `uv run --dev ruff check tests/integration_requires_dicom_download/test_release_gate.py tests/unit/test_makefile.py tests/unit/test_metadata.py` | Passed | Focused lint pass after the final test/import edits. |
| 2026-06-14 | `uv run --dev pytest tests/unit/test_part16_parser.py -q` | Passed | 6 passed; covers the new official-shape TID 1500/CID 29/CT parser fixture plus existing synthetic PS3.16 parser/import tests. |
| 2026-06-14 | `uv run --dev pytest tests/unit/test_build.py tests/unit/test_query_resolver.py -k 'part16 or sr_template or context_group or code_meaning' -q` | Passed | 9 passed; adjacent synthetic build and resolver coverage still passes after the parser changes. |
| 2026-06-14 | `uv run --dev ruff check src/dicom_kb/parsers/part16_content_mapping.py tests/unit/test_part16_parser.py tests/fixtures_synthetic/__init__.py` | Passed | Focused lint for the changed parser, fixture export, and parser tests. |
| 2026-06-14 | `uv run --dev pytest tests/unit/test_part16_parser.py tests/unit/test_build.py tests/unit/test_query_resolver.py -k 'part16 or sr_template or context_group or code_meaning' -q` | Passed | 15 passed; combined focused parser/build/resolver check after final include-target handling. |
| 2026-06-14 | `make lint` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev ruff check .` with all checks passed. |
| 2026-06-14 | `make typecheck` | Could not run | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun was rejected by the environment approval policy, so `uv run --dev mypy` did not execute. |
| 2026-06-14 | `uv run --dev pytest tests/unit/test_build.py tests/unit/test_query_resolver.py -k 'official_shape or part16 or sr_template or context_group or code_meaning' -q` | Passed | 11 passed after adding official-shape PS3.16 build/import and resolver coverage. |
| 2026-06-14 | `uv run --dev pytest tests/unit/test_part16_parser.py tests/unit/test_build.py tests/unit/test_query_resolver.py -k 'official_shape or part16 or sr_template or context_group or code_meaning' -q` | Passed | 17 passed; combined parser/build/resolver verification for the completed Phase R2 path. |
| 2026-06-14 | `make lint` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev ruff check .` with all checks passed. |
| 2026-06-14 | `make typecheck` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev mypy` with no issues in 57 source files. |
| 2026-06-14 | `uv run --dev pytest tests/agent_regression -q` | Passed | 23 passed after positive v2 expected traces began requiring `ok` status and required-part citations. |
| 2026-06-14 | `make test` | Failed in sandbox; initially failed escalated; passed after smoke-test boundary fix | Sandboxed command failed before pytest because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; first escalated run failed with 1 real-KB eval integration failure against the reduced local 2026b KB; after the eval smoke integration was gated on release-ready official data, escalated `make test` passed with 322 passed and 18 skipped. |
| 2026-06-14 | `uv run --dev pytest tests/agent_regression tests/integration_requires_dicom_download/test_eval_runner.py -rs` | Passed | 23 passed and 1 skipped; the real-KB eval smoke test skips the reduced local 2026b KB with the strict release-prerequisite failure message. |
| 2026-06-14 | `uv run --dev ruff check src/dicom_kb/eval/expected_tool_traces.py src/dicom_kb/eval/scoring.py src/dicom_kb/eval/runner.py src/dicom_kb/eval/prompt_cases.py tests/agent_regression/test_scoring.py tests/integration_requires_dicom_download/test_eval_runner.py` | Passed | Focused lint for the R4 scorer, reference-runner, prompt-route, and integration-test boundary changes. |
| 2026-06-14 | `make lint` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev ruff check .` with all checks passed. |
| 2026-06-14 | `make typecheck` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev mypy` with no issues in 57 source files. |
| 2026-06-14 | `uv run --dev pytest tests/agent_regression -q` | Passed | 26 passed after reference answers began deriving required terms from observed tool responses instead of `case.must_include`. |
| 2026-06-14 | `make lint` | Failed in sandbox; passed escalated | Phase R5 final verification. Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev ruff check .` with all checks passed. |
| 2026-06-14 | `make typecheck` | Failed in sandbox; passed escalated | Phase R5 final verification. Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev mypy` with no issues in 57 source files. |
| 2026-06-14 | `make test` | Failed in sandbox; passed escalated | Phase R5 final verification. Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun passed with 325 passed and 18 skipped. |
| 2026-06-14 | `make test-dicom-current` | Failed in sandbox; passed escalated | Phase R5 final verification. Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun passed with 1 passed. |
| 2026-06-14 | `make test-dicom-release` | Failed in sandbox; failed as expected escalated | Phase R5 final verification. Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun executed the strict gate and failed with 7 failures against the reduced local 2026b KB: missing required v2 DocBook artifacts, missing semantic rows, missing DocBook structure rows, and `not_found` for PN, application/dicom, RetrieveStudy, TID 1500, CID 29, and CT/DCM. |
| 2026-06-14 | `uv run --dev pytest tests/unit/test_metadata.py tests/unit/test_distribution_audit.py -q` | Passed | 9 passed after Phase R5 progress reconciliation edits; this also rechecked the tracked-file distribution audit. |
| 2026-06-14 | `uv run --dev pytest tests/integration_requires_dicom_download/test_eval_runner.py -rs` | Skipped as expected | 1 skipped because the selected local 2026b official KB is not release-ready; the skip message listed missing v2 DocBook parts, semantic rows, and DocBook structure rows. |
| 2026-06-14 | `uv run --dev pytest tests/agent_regression tests/unit/test_db_importers.py tests/unit/test_part07_parser.py tests/unit/test_part08_parser.py tests/unit/test_query_resolver.py -q` | Passed | Focused regression suite for the R4 runner/scoring changes and synthetic fixture updates passed. |
| 2026-06-14 | `uv run --dev ruff check src/dicom_kb/eval/runner.py src/dicom_kb/eval/scoring.py tests/agent_regression/test_runner.py tests/unit/test_db_importers.py tests/unit/test_part07_parser.py tests/unit/test_part08_parser.py tests/unit/test_query_resolver.py` | Passed | Focused lint for the changed eval runner/scoring model and fixture-coupled tests. |
| 2026-06-14 | `make lint` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev ruff check .` with all checks passed. |
| 2026-06-14 | `make typecheck` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev mypy` with no issues in 57 source files. |
| 2026-06-14 | `make test` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; an initial escalated run exposed fixture-coupled assertions after adding Pixel Data and more descriptive synthetic titles; after updating those assertions, escalated `make test` passed with 325 passed and 18 skipped. |
| 2026-06-15 | `uv run --dev pytest tests/unit/test_part05_parser.py tests/unit/test_build.py -k 'part05 or vr_table' -q` | Passed | 7 passed; covers official-shape PS3.5 VR table parsing plus build/import/query coverage for PN. |
| 2026-06-15 | `uv run --dev ruff check src/dicom_kb/parsers/part05_encoding.py tests/unit/test_part05_parser.py tests/unit/test_build.py tests/fixtures_synthetic/__init__.py` | Passed | Focused lint for the PS3.5 parser, fixture export, and tests. |
| 2026-06-15 | `make lint` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev ruff check .` with all checks passed. |
| 2026-06-15 | `make typecheck` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev mypy` with no issues in 57 source files. |
| 2026-06-15 | `uv run --dev dicom-kb build --edition 2026b --force` | Passed escalated | Rebuilt the local official 2026b KB and imported 34 `vr_definition` rows from official PS3.5. Generated DB remains outside the repo. |
| 2026-06-15 | `env DICOM_KB_RUN_RELEASE=1 uv run --dev pytest tests/integration_requires_dicom_download/test_release_goldens.py -k pn_vr -q` | Passed escalated | 1 passed; the strict PN VR release golden now succeeds against the rebuilt official KB. |
| 2026-06-15 | `make test-dicom-release` | Failed as expected escalated | Strict release gate now reports 1 passed and 6 failed. Remaining failures are missing `dicom_media_type`, `dicomweb_transaction`, `sr_template`, `sr_template_row`, `context_group`, `context_group_row`, and `coded_concept` rows plus their pinned examples. |
| 2026-06-15 | `uv run --dev pytest tests/unit/test_part18_parser.py tests/unit/test_query_resolver.py -k 'part18 or media_type or dicomweb_transaction' -q` | Passed | 17 passed; covers official-shape PS3.18 application/dicom media parsing plus RetrieveStudy parser/import/query behavior. |
| 2026-06-15 | `uv run --dev ruff check src/dicom_kb/parsers/part18_web_services.py tests/unit/test_part18_parser.py tests/unit/test_query_resolver.py tests/fixtures_synthetic/__init__.py` | Passed | Focused lint for the PS3.18 parser, fixture export, and tests. |
| 2026-06-15 | `make lint` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun completed `uv run --dev ruff check .` with all checks passed. |
| 2026-06-15 | `make typecheck` | Failed in sandbox; passed escalated after annotation fix | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; first escalated run found tuple inference errors in `part18_web_services.py`; after adding tuple annotations, escalated rerun completed `uv run --dev mypy` with no issues in 57 source files. |
| 2026-06-15 | `uv run --dev dicom-kb build --edition 2026b --force` | Passed | Rebuilt the local official 2026b KB and imported 1 `dicom_media_type` row and 42 `dicomweb_transaction` rows from official PS3.18. Generated DB remains outside the repo. |
| 2026-06-15 | `env DICOM_KB_RUN_RELEASE=1 uv run --dev pytest tests/integration_requires_dicom_download/test_release_goldens.py -k 'application_dicom_media_type or retrieve_study_transaction' -q` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun passed 2 strict release goldens. |
| 2026-06-15 | `make test-dicom-release` | Failed in sandbox; failed as expected escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated strict release gate now reports 3 passed and 4 failed. Remaining failures are missing PS3.16 `sr_template`, `sr_template_row`, `context_group`, `context_group_row`, and `coded_concept` rows plus the pinned TID 1500, CID 29, and CT/DCM examples. |
| 2026-06-15 | `make test` | Failed in sandbox; passed escalated | Sandboxed command failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated rerun passed with 332 passed and 16 skipped. |
| 2026-06-15 | `uv run --dev pytest tests/unit/test_metadata.py -q` | Passed | 7 passed after updating the durable progress trackers. |
| 2026-06-15 | `uv run --dev pytest tests/unit/test_metadata.py -q` | Passed | 7 passed after documenting the post-completion review findings and reopening remediation phases R6-R10. |
