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
| Planning scaffold | Complete | `REMEDIATION_PLAN.md`, this progress tracker, and ignored `scripts/run_codex_remediation.sh` are being introduced in the current commit. |
| Phase R0 - Reproduce and inventory the gap | Not started | First remediation slice should record manifest parts, semantic row counts, CLI spot checks, current official-golden skips, and current agent-regression behavior. |
| Phase R1 - Separate smoke tests from release gates | Not started | Strict release gates must reject reduced PS3.3/PS3.4/PS3.6 official KBs while preserving smoke coverage. |
| Phase R2 - Repair official-shape PS3.16 ingestion | Not started | Parser/import/resolver behavior must handle official TID/CID/code table shapes, not only synthetic TID/CID columns. |
| Phase R3 - Pin strict official goldens | Not started | Strict official positive tests must cover PN, application/dicom, RetrieveStudy, TID 1500, CID 29, and CT/DCM. |
| Phase R4 - Harden agent regression scoring | Not started | Positive v2 prompt cases must require `ok` tool results with required-part citations. |
| Phase R5 - Reconcile completion state and final gates | Not started | Final docs and progress must reflect the repaired release evidence and final verification. |

## Active Work

| Field | Value |
|---|---|
| Current phase | Planning scaffold |
| Current owner/agent | Codex |
| Branch | main |
| Last completed remediation commit | Pending current commit. |
| Last verification | `bash -n scripts/run_codex_remediation.sh` passed; bounded `scripts/run_codex_remediation.sh --dry-run --output-dir /tmp/dicom-kb-remediation-dry-run2` printed the generated remediation prompt. |
| Current blocker | None. |
| Commit-ready summary | Created the concrete phased remediation plan and durable progress tracker that convert `IMPLEMENTATION_PLAN_REVIEW.md` findings into scoped follow-up work. |
| Next recommended action | Start Phase R0 by recording the current official manifest parts, required semantic table row counts, named CLI spot checks, current official-golden skip behavior, and current agent-regression behavior. |

## Phase R0 - Reproduce and Inventory the Gap

Status: `Not started`

Scope:

- Capture the current false-positive release-gate evidence.
- Record local official edition and manifest coverage.
- Record required v2 semantic table row counts.
- Record named CLI spot checks and current integration skip behavior.

Completion checklist:

- [ ] Manifest part inventory recorded.
- [ ] Required semantic table row counts recorded.
- [ ] CLI spot checks recorded for PN, application/dicom, RetrieveStudy,
      TID 1500, CID 29, and CT/DCM.
- [ ] Current official golden skip/pass behavior recorded.
- [ ] Current agent regression behavior recorded.
- [ ] Next code slice selected.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| Pending | No Phase R0 commit yet. | Pending |

Notes:

- This phase should not change production behavior unless a tiny diagnostic
  helper is required.

## Phase R1 - Separate Smoke Tests from Release Gates

Status: `Not started`

Scope:

- Add strict official-KB prerequisite checks.
- Separate reduced-cache smoke tests from release gates.
- Ensure release documentation and Makefile targets call the strict gate.

Completion checklist:

- [ ] Strict helper requires the full v2 official part set.
- [ ] Strict helper requires nonzero rows for all required v2 semantic tables.
- [ ] Strict helper checks citation-preserving DocBook structure for v2 parts.
- [ ] Reduced-cache smoke tests remain available.
- [ ] Release gate target rejects PS3.3/PS3.4/PS3.6-only official KBs.
- [ ] Release checklist names the strict gate.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| Pending | No Phase R1 commit yet. | Pending |

## Phase R2 - Repair Official-Shape PS3.16 Ingestion

Status: `Not started`

Scope:

- Add official-shape PS3.16 fixtures.
- Parse TID/CID metadata from official section or table metadata.
- Parse official SR template, context group, include, and coded-concept rows.
- Keep existing synthetic coverage working.

Completion checklist:

- [ ] Official-shape TID 1500 fixture parses.
- [ ] Official-shape CID 29 fixture parses.
- [ ] Official-shape CT/DCM code row parses.
- [ ] Import/build tests persist PS3.16 rows with citations.
- [ ] Resolver tests return `ok` for TID 1500, CID 29, and CT/DCM fixture data.
- [ ] Existing synthetic PS3.16 tests still pass.

Commits:

| Commit | Summary | Verification |
|---|---|---|
| Pending | No Phase R2 commit yet. | Pending |

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
