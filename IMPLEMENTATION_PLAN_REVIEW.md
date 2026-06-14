# Implementation Plan Review

Date: 2026-06-14

Scope: review the current source tree, local official 2026b cache, and test
gates against `IMPLEMENTATION_PLAN.md`. This review did not perform a fresh
network fetch of official DICOM artifacts.

## Findings

### High: v2 release gates can pass with a PS3.3/4/6-only official KB

`IMPLEMENTATION_PLAN.md` Phase 9 requires representative official-edition
goldens for PS3.5, PS3.10, PS3.16, PS3.18, contextual value-term behavior, and
all final release gates. `IMPLEMENTATION_PROGRESS.md` marks Phase 9 and all v2
acceptance criteria complete.

The current release gates do not enforce those prerequisites:

- `Makefile` maps `test-dicom-integration` to the whole integration directory
  and `test-dicom-current` only runs current-edition resolution.
- `tests/integration_requires_dicom_download/conftest.py` selects the newest
  local SQLite DB with any manifest, not one containing all v2 parts.
- `tests/integration_requires_dicom_download/test_real_kb_smoke.py` accepts any
  manifest with at least three artifacts, which a v1 PS3.3/4/6 cache satisfies.
- `tests/integration_requires_dicom_download/test_real_kb_goldens.py` skips
  positive v2 checks when semantic rows are absent.

Local evidence confirms the gap. The available 2026b manifest contains only
PS3.3, PS3.4, and PS3.6. The local DB has zero rows for `vr_definition`,
`file_meta_requirement`, `dicom_media_type`, `dicomweb_transaction`,
`sr_template`, `context_group`, and `coded_concept`. The official golden run
reported `40 passed, 6 skipped`; the skipped cases are the PS3.5 VR,
PS3.10 media type, PS3.18 DICOMweb, and PS3.16 template/context/code checks.

CLI spot checks show the same behavior:

- `dicom-kb lookup vr PN --edition 2026b` returns `not_found`.
- `dicom-kb lookup dicomweb RetrieveStudy --edition 2026b` returns `not_found`.
- `dicom-kb lookup sr-template 1500 --edition 2026b` returns `not_found`.
- `dicom-kb lookup transfer-syntax 1.2.840.10008.1.2.1 --edition 2026b`
  returns `ok`, because transfer syntax details are derived from PS3.6.

This means the final gate is currently a false positive for several v2
acceptance criteria. The code has public surfaces for these capabilities, but
the release process does not prove that the official KB contains or resolves
the planned v2 facts.

Recommended fix: separate smoke tests from release gates. For release gates,
require the manifest to contain the v2 official part set, require nonzero row
counts for all v2 semantic tables, fail instead of skip for positive v2
official goldens, and pin concrete examples such as PN, application/dicom,
RetrieveStudy, TID 1500, CID 29, and CT/DCM.

### High: agent regression scoring can pass v2 cases with `not_found` tool results

`src/dicom_kb/eval/prompt_cases.py` defines positive v2 cases that require
terms such as PN, Person Name, PS3.5, application/dicom, RetrieveStudy, GET,
TID 1500, CID 29, and Computed Tomography.

The reference runner and scorer do not ensure those facts came from successful
tool calls:

- `src/dicom_kb/eval/runner.py` adds a fallback `lookup_data_element(Modality)`
  call whenever no successful cited call exists.
- `_reference_answer` inserts `case.must_include` terms directly into the
  generated answer text, regardless of the corresponding tool response status.
- `src/dicom_kb/eval/scoring.py` checks that expected tools were called and
  that some response metadata exists, but it does not require positive expected
  tools to return `ok`.
- The source-reference requirement is satisfied by any `ok` call with refs for
  the edition, not necessarily the tool call supporting the asserted v2 fact.

The real-KB eval runner passes against the same local DB that returns
`not_found` for PS3.5 VR, PS3.18 DICOMweb, and PS3.16 SR template spot checks.

Recommended fix: for positive cases, require each expected tool to return `ok`
with at least one citation from the expected part. Build required answer content
from actual tool payload fields rather than from the prompt fixture, and disable
the generic source-reference fallback for positive v2 semantic cases.

### Medium: the PS3.16 parser appears shaped around synthetic tables

`src/dicom_kb/parsers/part16_content_mapping.py` identifies SR template tables
only when headers include `tid`, and context group tables only when headers
include `cid`. The row parsers then require every SR template row to contain
TID/name columns and every context-group row to contain CID/name columns.

The synthetic fixture follows exactly that shape, with explicit `TID`/`Name`
and `CID`/`Name` columns, and the unit tests validate that synthetic layout.
The official PS3.16 CHTML instead places identifiers and names in surrounding
section or table titles, while the data rows use template row columns such as
NL/VT/concept-name fields and context-group code columns. See the current
official PS3.16 page:
https://dicom.nema.org/medical/dicom/current/output/chtml/part16/PS3.16.html

This likely prevents official PS3.16 ingestion from producing the planned TID,
CID, and coded-concept rows even after PS3.16 is present in the manifest.

Recommended fix: parse TID/CID and names from section or table metadata, use the
official row headers to classify template and context-group tables, and add
official-shape fixtures for TID 1500, CID 29, and CT/DCM.

### Medium: official goldens are not pinned tightly enough to plan examples

Several official golden helpers select any available unique row, with preferred
examples only used as ordering hints. For example, the DICOMweb helper prefers
transactions containing "retrieve" but will accept a different unique
transaction, while the SR template and context group helpers prefer TID 1500
and CID 29 but fall back to any table with rows.

That pattern is useful for compatibility across changing editions, but it is
too weak for the Phase 9 release objective. A release gate should prove that the
specific acceptance examples work, or fail with a clear message explaining which
official fact is missing.

Recommended fix: keep flexible discovery tests for smoke coverage, and add
strict positive release tests for the named acceptance examples.

## Positive Confirmations

- The default official fetch part set now includes the v2 DocBook parts
  PS3.5, PS3.7, PS3.8, PS3.10, PS3.16, and PS3.18.
- The build pipeline conditionally imports v2 parts when they are present in a
  manifest.
- Python resolver methods, CLI commands, and MCP tool registrations exist for
  the planned v2 lookup surfaces.
- Offline quality checks are currently clean.

## Verification Performed

- `uv run --dev ruff check .`: passed.
- `uv run --dev mypy`: passed with 57 source files checked.
- `uv run --dev pytest tests/unit tests/agent_regression`: 268 passed.
- `uv run --dev pytest tests/integration_requires_dicom_download/test_real_kb_goldens.py -rs`:
  40 passed, 6 skipped.
- `uv run --dev pytest tests/integration_requires_dicom_download/test_eval_runner.py -q`:
  passed.
- CLI spot checks against local edition 2026b confirmed `not_found` for PN VR,
  RetrieveStudy, and TID 1500, with transfer syntax lookup succeeding from
  PS3.6-derived data.
