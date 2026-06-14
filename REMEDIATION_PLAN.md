# Remediation Plan

Date: 2026-06-14

Source: `IMPLEMENTATION_PLAN_REVIEW.md`

## Goal

Make the v2 completion claim evidence-backed. The current v2 implementation
has public surfaces and synthetic coverage, but the review found that release
and agent-regression gates can pass when the official-edition KB lacks required
PS3.5, PS3.10, PS3.16, and PS3.18 semantic facts.

This remediation plan converts those findings into scoped phases. A phase is
complete only when its focused tests pass and `REMEDIATION_PROGRESS.md`
records the commit, verification commands, blockers, and next action.

## Scope

In scope:

- Release-gate tests that reject incomplete official KBs.
- Strict official-edition goldens for the named v2 acceptance examples.
- Agent regression scoring that requires successful cited tool results for
  positive v2 claims.
- Official-shape PS3.16 parsing for TID, CID, and coded-concept content.
- Durable progress reconciliation after each remediation slice.

Out of scope:

- New v3 roadmap work or broad validation features not promised by
  `IMPLEMENTATION_PLAN.md`.
- Committing official DICOM artifacts, generated databases, vector indexes, or
  standalone terminology exports.
- Rewriting working v2 surfaces unless required to make official-edition
  evidence truthful.

## Remediation Invariants

- A reduced PS3.3/PS3.4/PS3.6 official KB must not satisfy any v2 release
  gate.
- Smoke tests may skip or tolerate reduced caches, but release gates must fail
  with clear prerequisites when required v2 official data is absent.
- Positive official goldens must assert concrete examples, not any available
  row.
- Positive agent-regression cases must require each expected semantic tool to
  return `ok` with citations from the required standard part.
- Answer text for positive regression cases must be derived from successful
  tool payload fields, not copied from prompt fixtures.
- Generic source-reference fallback calls must not satisfy positive v2
  semantic cases.
- All parsed facts remain edition-pinned and citation-preserving.

## Phase R0 - Reproduce and Inventory the Gap

Goal: establish the current false-positive behavior as a durable baseline
before changing gates.

Deliverables:

- Record the current local official edition, manifest parts, and row counts
  for these tables:
  `vr_definition`, `transfer_syntax_detail`, `file_meta_requirement`,
  `dicom_media_type`, `dicomweb_transaction`, `sr_template`,
  `sr_template_row`, `context_group`, `context_group_row`,
  `coded_concept`, and `attribute_value_term`.
- Record CLI spot-check results for:
  `lookup vr PN`, `lookup media-type application/dicom`,
  `lookup dicomweb RetrieveStudy`, `lookup sr-template 1500`,
  `lookup context-group 29`, and `lookup code CT --scheme DCM`.
- Record current integration and agent-regression gate behavior, including
  skipped official goldens.
- Update `REMEDIATION_PROGRESS.md` with the observed evidence and the next
  selected code slice.

Verification:

- Run the narrow commands needed to gather the evidence.
- Run the current integration golden command with skip reporting:
  `uv run --dev pytest tests/integration_requires_dicom_download/test_real_kb_goldens.py -rs`.
- Run the current agent regression command:
  `uv run --dev pytest tests/agent_regression`.

Exit criteria:

- The durable progress file identifies exactly which missing official facts
  still pass existing gates.
- No production behavior changes are required in this phase.

## Phase R1 - Separate Smoke Tests from Release Gates

Goal: make release-gate prerequisites explicit while preserving developer
smoke coverage for partial local caches.

Deliverables:

- Add a shared official-KB requirement helper for strict release tests.
- Require this official part set for release gates:
  `PS3.3`, `PS3.4`, `PS3.5`, `PS3.6`, `PS3.7`, `PS3.8`, `PS3.10`,
  `PS3.16`, and `PS3.18`.
- Require nonzero semantic row counts for:
  `vr_definition`, `transfer_syntax_detail`, `file_meta_requirement`,
  `dicom_media_type`, `dicomweb_transaction`, `sr_template`,
  `sr_template_row`, `context_group`, `context_group_row`,
  `coded_concept`, and `attribute_value_term`.
- Require raw DocBook structure for all v2 parts by checking `doc_node`,
  `raw_table_ir`, or another existing citation-preserving structure for each
  part.
- Keep reduced-cache smoke tests separate from strict release tests. Smoke
  tests may skip when optional semantic rows are absent; release tests must
  fail with an actionable message.
- Add or update a Makefile target for the strict release gate. The release
  checklist must use the strict target, not only the smoke target.

Tests:

- Unit tests for the requirement helper covering complete, missing-part, and
  missing-row scenarios.
- Integration tests showing that a PS3.3/PS3.4/PS3.6-only KB is rejected by
  the strict gate.
- Makefile coverage confirming the documented release target runs the strict
  gate.

Exit criteria:

- A partial official KB can still be used for smoke tests.
- A partial official KB cannot report the v2 release gate as passed.

## Phase R2 - Repair Official-Shape PS3.16 Ingestion

Goal: make official PS3.16 content produce the TID, CID, and coded-concept
rows required by v2 acceptance criterion 3.

Deliverables:

- Add official-shape PS3.16 fixtures for:
  TID 1500 Measurement Report, CID 29 Acquisition Modality, and CT/DCM.
- Extract TID, CID, names, and extensibility from section or table metadata
  when official rows do not repeat those identifiers.
- Classify SR template tables by official row headers such as relationship
  type, value type, concept name, cardinality, condition, and include targets.
- Classify context-group tables by official code rows such as coding scheme,
  code value, code meaning, version, and include references.
- Preserve include rows and cited source refs for templates, context groups,
  and coded concepts.
- Keep synthetic table-shape coverage intact.

Tests:

- Parser tests for the official-shape TID 1500, CID 29, and CT/DCM fixtures.
- Import/build tests proving `sr_template`, `sr_template_row`,
  `context_group`, `context_group_row`, and `coded_concept` rows persist with
  PS3.16 source refs.
- Resolver tests proving `lookup_sr_template("1500")`,
  `lookup_context_group("29")`, and `lookup_code_meaning("CT", scheme="DCM")`
  return `ok` against official-shape fixture data.

Exit criteria:

- The PS3.16 parser is no longer dependent on synthetic-only `TID`/`CID`
  columns.
- Official-shape fixture data satisfies the PS3.16 public lookup surfaces.

## Phase R3 - Pin Strict Official Goldens

Goal: prove the named v2 acceptance examples work against a full official KB.

Deliverables:

- Add strict official positive tests for:
  `PN`, `application/dicom`, `RetrieveStudy`, `TID 1500`, `CID 29`, and
  `CT` with scheme `DCM`.
- Fail on `not_found`, empty candidate-only responses, missing result fields,
  or missing required-part citations.
- Keep flexible discovery tests only as smoke coverage; they must not satisfy
  release-gate completion.
- Ensure official golden helpers prefer exact acceptance examples and do not
  silently fall back to unrelated rows.

Tests:

- `lookup_vr("PN")` returns `ok` with a PS3.5 citation and the Person Name
  meaning.
- `lookup_media_type("application/dicom")` returns `ok` with PS3.10 or
  PS3.18 citations and media constraints.
- `lookup_dicomweb_transaction("RetrieveStudy")` returns `ok` with method,
  route, resource category, request/response constraints, and a PS3.18
  citation.
- `lookup_sr_template("1500")` returns `ok` with structured rows,
  extensibility metadata, and PS3.16 citations.
- `lookup_context_group("29")` returns `ok` with CID metadata, rows, and
  PS3.16 citations.
- `lookup_code_meaning("CT", scheme="DCM")` returns `ok` with Computed
  Tomography and a PS3.16 citation.

Exit criteria:

- The strict release target passes only when the full official KB contains the
  required semantic facts.
- The skipped-case count cannot hide missing v2 acceptance examples.

## Phase R4 - Harden Agent Regression Scoring

Goal: prevent v2 prompt cases from passing with `not_found` tool results or
unrelated citation fallback calls.

Deliverables:

- Extend expected tool traces with required status and required standard-part
  metadata for positive semantic cases.
- Update scoring so positive expected tools must return `ok`.
- Require at least one citation from the required part for each positive
  expected semantic tool result.
- Build required answer text from successful tool payload fields, not from
  `case.must_include` fixtures.
- Disable or scope the generic `lookup_data_element(Modality)` source
  fallback so it cannot satisfy positive v2 semantic cases.
- Keep unsupported/negative cases able to assert `not_found`,
  validation-error, or candidate behavior explicitly.

Tests:

- Scoring unit tests where a positive expected v2 tool returns `not_found` and
  the case fails.
- Scoring unit tests where a positive expected v2 tool returns `ok` but cites
  the wrong part and the case fails.
- Runner tests proving positive v2 answers omit fixture-only terms when the
  supporting tool result is missing.
- Existing `tests/agent_regression/` remains deterministic and offline.

Exit criteria:

- Agent regression pass/fail status reflects successful cited tool evidence
  for each positive v2 semantic claim.

## Phase R5 - Reconcile Completion State and Final Gates

Goal: close remediation by updating durable documentation and proving all
relevant gates.

Deliverables:

- Update `IMPLEMENTATION_PROGRESS.md` only where remediation changes the
  truth of v2 completion evidence.
- Update release documentation if target names or release-gate commands
  changed.
- Update `REMEDIATION_PROGRESS.md` with final status, commit hashes, exact
  verification commands, skipped checks, and remaining external prerequisites.
- Confirm distribution constraints still hold: no official artifacts,
  generated databases, vector indexes, or standalone terminology dumps are
  tracked.

Required final verification:

```bash
make lint
make typecheck
make test
make test-dicom-current
make test-dicom-release
```

If the repository keeps `make test-dicom-integration` as the release target
instead of adding `make test-dicom-release`, the final verification must use
that strict target and `REMEDIATION_PROGRESS.md` must say which Makefile
contract was chosen.

Exit criteria:

- `REMEDIATION_PROGRESS.md` marks all remediation phases complete.
- Strict official release gates pass against a full official v2 KB.
- Agent regression gates fail when required positive v2 tool evidence is
  replaced by `not_found`.
- The original findings in `IMPLEMENTATION_PLAN_REVIEW.md` are either fixed
  or recorded as explicit external blockers.

## Suggested Commit Boundaries

- One commit for baseline evidence/progress updates.
- One commit for release-gate prerequisite helpers and Makefile wiring.
- One commit for official-shape PS3.16 parser changes.
- One commit for official PS3.16 import/build/resolver fixture coverage if it
  is too large for the parser commit.
- One commit for strict official golden tests.
- One commit for agent-regression scorer and runner hardening.
- One commit for final documentation and progress reconciliation.

Do not batch unrelated parser, release-gate, scorer, CLI, MCP, or docs work
unless the files are required for the same coherent remediation slice.
