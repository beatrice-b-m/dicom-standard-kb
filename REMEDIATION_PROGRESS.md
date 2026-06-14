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
| Phase R2 - Repair official-shape PS3.16 ingestion | In progress | Official-shape parser support now handles TID/CID metadata from section or table titles, official SR template row headers, CID code rows, and CID include xrefs; import/build/resolver coverage against the official-shape fixture remains pending. |
| Phase R3 - Pin strict official goldens | Not started | Strict official positive tests must cover PN, application/dicom, RetrieveStudy, TID 1500, CID 29, and CT/DCM. |
| Phase R4 - Harden agent regression scoring | Not started | Positive v2 prompt cases must require `ok` tool results with required-part citations. |
| Phase R5 - Reconcile completion state and final gates | Not started | Final docs and progress must reflect the repaired release evidence and final verification. |

## Active Work

| Field | Value |
|---|---|
| Current phase | Phase R2 - Repair official-shape PS3.16 ingestion |
| Current owner/agent | Codex |
| Branch | main |
| Last completed remediation commit | Pending current commit. Previous completed R1 target commit: 87cd1be. |
| Last verification | `uv run --dev pytest tests/unit/test_part16_parser.py -q` passed with 6 passed; `uv run --dev pytest tests/unit/test_build.py tests/unit/test_query_resolver.py -k 'part16 or sr_template or context_group or code_meaning' -q` passed with 9 passed; `uv run --dev pytest tests/unit/test_part16_parser.py tests/unit/test_build.py tests/unit/test_query_resolver.py -k 'part16 or sr_template or context_group or code_meaning' -q` passed with 15 passed; `uv run --dev ruff check src/dicom_kb/parsers/part16_content_mapping.py tests/unit/test_part16_parser.py tests/fixtures_synthetic/__init__.py` passed; sandboxed `make lint` failed before running because `uv` could not read `/Users/beatrice/.cache/uv/sdists-v9/.git`; escalated `make lint` passed; sandboxed `make typecheck` failed before running for the same uv cache permission reason and escalated `make typecheck` was rejected by the environment approval policy, so mypy did not run. |
| Current blocker | None. |
| Commit-ready summary | Added official-shape PS3.16 fixture coverage and parser support for TID/CID metadata in titles, official SR template row headers, CID code rows, CID include xrefs, and derived CT/DCM coded concepts while preserving synthetic PS3.16 parsing. |
| Next recommended action | Continue Phase R2 with the import/build/resolver fixture slice: persist the official-shape PS3.16 fixture rows, then prove `lookup_sr_template("1500")`, `lookup_context_group("29")`, and `lookup_code_meaning("CT", scheme="DCM")` return `ok` against that fixture data. |

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

Status: `In progress`

Scope:

- Add official-shape PS3.16 fixtures.
- Parse TID/CID metadata from official section or table metadata.
- Parse official SR template, context group, include, and coded-concept rows.
- Keep existing synthetic coverage working.

Completion checklist:

- [x] Official-shape TID 1500 fixture parses.
- [x] Official-shape CID 29 fixture parses.
- [x] Official-shape CT/DCM code row parses.
- [ ] Import/build tests persist PS3.16 rows with citations.
- [ ] Resolver tests return `ok` for TID 1500, CID 29, and CT/DCM fixture data.
- [x] Existing synthetic PS3.16 tests still pass.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| Pending current commit | Added official-shape PS3.16 parser support for TID/CID metadata in section or table titles, official SR template row headers, CID code rows, and CID include xrefs. | `uv run --dev pytest tests/unit/test_part16_parser.py -q`; `uv run --dev pytest tests/unit/test_build.py tests/unit/test_query_resolver.py -k 'part16 or sr_template or context_group or code_meaning' -q`; `uv run --dev pytest tests/unit/test_part16_parser.py tests/unit/test_build.py tests/unit/test_query_resolver.py -k 'part16 or sr_template or context_group or code_meaning' -q`; `uv run --dev ruff check src/dicom_kb/parsers/part16_content_mapping.py tests/unit/test_part16_parser.py tests/fixtures_synthetic/__init__.py`; `make lint`; `make typecheck` could not run because sandboxed uv cache access failed and escalated `make typecheck` was rejected. |

## Phase R3 - Pin Strict Official Goldens

Status: `Not started`

Scope:

- Add exact official positive tests for named v2 examples.
- Remove fallback-to-any-row behavior from release-golden helpers.
- Fail on `not_found`, missing result fields, or missing required-part refs.

Completion checklist:

- [ ] Strict PN VR official golden requires PS3.5 citation.
- [ ] Strict application/dicom official golden requires PS3.10 or PS3.18 citation.
- [ ] Strict RetrieveStudy official golden requires PS3.18 citation.
- [ ] Strict TID 1500 official golden requires PS3.16 citation and rows.
- [ ] Strict CID 29 official golden requires PS3.16 citation and rows.
- [ ] Strict CT/DCM official golden requires PS3.16 citation.
- [ ] Flexible discovery tests are clearly smoke-only.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| Pending | No Phase R3 commit yet. | Pending |

## Phase R4 - Harden Agent Regression Scoring

Status: `Not started`

Scope:

- Require positive expected v2 semantic tools to return `ok`.
- Require citations from the expected standard part.
- Prevent unrelated fallback calls from satisfying v2 semantic evidence.
- Build required answer content from actual tool payloads.

Completion checklist:

- [ ] Expected trace metadata can declare required status and required parts.
- [ ] Scoring fails positive v2 cases with `not_found` expected tool results.
- [ ] Scoring fails positive v2 cases with wrong-part citations.
- [ ] Runner no longer injects fixture-only required terms for missing facts.
- [ ] Generic source-reference fallback cannot satisfy positive v2 semantic cases.
- [ ] Unsupported/negative cases still assert their expected non-`ok` behavior.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| Pending | No Phase R4 commit yet. | Pending |

## Phase R5 - Reconcile Completion State and Final Gates

Status: `Not started`

Scope:

- Reconcile `IMPLEMENTATION_PROGRESS.md` with repaired release evidence.
- Update release documentation for strict gate commands.
- Run and record final verification.
- Confirm distribution constraints.

Completion checklist:

- [ ] `IMPLEMENTATION_PROGRESS.md` reflects repaired evidence or explicit blockers.
- [ ] Release docs name the strict official gate.
- [ ] `make lint` recorded.
- [ ] `make typecheck` recorded.
- [ ] `make test` recorded.
- [ ] `make test-dicom-current` recorded.
- [ ] Strict official release gate recorded.
- [ ] Distribution audit confirms no forbidden generated/official artifacts are tracked.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| Pending | No Phase R5 commit yet. | Pending |

## Blockers and Open Decisions

- None recorded yet.

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
