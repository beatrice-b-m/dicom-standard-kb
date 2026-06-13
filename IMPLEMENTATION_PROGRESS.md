# Implementation Progress

Durable remediation state for `REMEDIATION_PLAN.md`. Update this file after
each remediation slice so a fresh Codex thread can continue from repo state
alone.

## Current Status

- Last updated: 2026-06-13
- Worktree baseline: clean at start of remediation continuation.
- Latest observed commit: `40cc4f8 feat(cli): add context attribute alias`
- Remediation plan status:
  - Official URL remediation is already excluded from the active plan and
    recorded as complete in `REMEDIATION_PLAN.md`.
  - Phase 1, Surface Parity, is complete.
    - `dicom-kb verify --edition <edition>` is implemented and tested.
    - `dicom-kb context attribute ...` is implemented and tested.
    - `make test-dicom-integration` and opt-in `make test-dicom-current`
      are implemented and tested by dry-run smoke coverage.
  - Phase 2, Response Classification and Parse Confidence, is the next
    incomplete remediation phase.
  - Phases 3-6 remain incomplete.

## Completed Work

- Created this durable progress ledger before the first implementation slice
  in this remediation run.
- Added `src/dicom_kb/sources/verify.py` for manifest checksum validation,
  artifact SHA-256 checks, and optional SQLite build metadata verification.
- Added `dicom-kb verify --edition <edition>` with structured JSON output
  and nonzero exit behavior when verification fails.
- Added focused tests for a fresh fixture build, checksum mismatch, missing
  artifact, missing DB warning, DB metadata mismatch, CLI success output, and
  CLI failure output.
- Added `dicom-kb context attribute <attribute> --iod <iod>` as a documented
  alias for `dicom-kb resolve attribute-context`.
- Added a CLI regression proving the alias emits the same stable response
  payload as `resolve attribute-context`.
- Added `make test-dicom-integration` as an alias for `make test-integration`.
- Added opt-in `make test-dicom-current`, which runs only tests marked
  `dicom_current` and sets `DICOM_KB_RUN_CURRENT=1`.
- Added a current-edition live integration test that is skipped unless the
  opt-in Makefile target enables it.
- Added a Makefile dry-run smoke test proving the DICOM integration aliases
  are wired and the default `test` target does not include the current-edition
  network marker.
- Marked Phase 1 complete in `REMEDIATION_PLAN.md`.

## Verification Results

- 2026-06-13: Read `AGENTS.md`, `SYSTEM_SPECS.md`,
  `IMPLEMENTATION_REVIEW.md`, and `REMEDIATION_PLAN.md`.
- 2026-06-13: Confirmed `IMPLEMENTATION_PROGRESS.md` was absent and needed
  to be created before implementation work.
- 2026-06-13: `git status --short` showed no tracked or untracked changes
  before creating this file.
- 2026-06-13: `uv run pytest tests/unit/test_sources_verify.py` passed
  (`7 passed`).
- 2026-06-13: `uv run pytest tests/unit/test_sources_verify.py
  tests/unit/test_sources.py tests/unit/test_build.py
  tests/unit/test_cli_lookup.py` passed (`45 passed`).
- 2026-06-13: `uv run ruff check src/dicom_kb/sources/verify.py
  src/dicom_kb/cli/main.py tests/unit/test_sources_verify.py` passed.
- 2026-06-13: `uv run mypy src/dicom_kb/sources/verify.py` passed.
- 2026-06-13: `uv run pytest tests/unit/test_cli_lookup.py` passed
  (`21 passed`).
- 2026-06-13: `uv run ruff check src/dicom_kb/cli/main.py
  tests/unit/test_cli_lookup.py` passed.
- 2026-06-13: `uv run mypy src/dicom_kb/cli/main.py` passed.
- 2026-06-13: `uv run pytest tests/unit/test_makefile.py
  tests/integration_requires_dicom_download/test_current_resolution.py` passed
  (`1 passed, 1 skipped`).
- 2026-06-13: `uv run ruff check tests/unit/test_makefile.py
  tests/integration_requires_dicom_download/test_current_resolution.py` passed.

## Blockers

- None.

## Open Decisions

- Phase 4 configuration profiles should be implemented as specified unless
  later remediation discovers a spec conflict.
- Phase 5 effective-type override handling should remain conservative and
  should not broaden into full condition parsing.

## Next Recommended Task

Begin Phase 2 response classification and parse confidence:

1. Add `ResponseClassification` and `ParseConfidence` models to
   `query/answer_contracts.py`.
2. Add required `classification` and `parse_confidence` fields to
   `ToolResponse` with deterministic defaults per tool/status.
3. Update schema and representative query/CLI/MCP tests so all public
   response surfaces emit the new metadata.
