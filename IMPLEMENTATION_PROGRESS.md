# Implementation Progress

Durable remediation state for `REMEDIATION_PLAN.md`. Update this file after
each remediation slice so a fresh Codex thread can continue from repo state
alone.

## Current Status

- Last updated: 2026-06-13
- Worktree baseline: clean at start of remediation continuation.
- Latest observed commit: `df4403b feat(config): load YAML profiles`
- Remediation plan status:
  - Official URL remediation is already excluded from the active plan and
    recorded as complete in `REMEDIATION_PLAN.md`.
  - Phase 1, Surface Parity, is complete.
    - `dicom-kb verify --edition <edition>` is implemented and tested.
    - `dicom-kb context attribute ...` is implemented and tested.
    - `make test-dicom-integration` and opt-in `make test-dicom-current`
      are implemented and tested by dry-run smoke coverage.
  - Phase 2, Response Classification and Parse Confidence, is complete.
    - `ToolResponse` requires `classification` and `parse_confidence`.
    - JSON schema requires both new fields.
    - Python resolver, CLI, and MCP tests cover representative metadata.
  - Phase 3, Build Metrics and Quality Gates, is complete.
    - Build metrics aggregation and metadata persistence are implemented and
      tested.
    - Configurable quality gates are implemented and tested for failing and
      allowed-warning behavior.
  - Phase 4, YAML Configuration Profiles, is complete.
    - `PyYAML` runtime dependency and `types-PyYAML` dev stubs are added.
    - Typed config profile loading and precedence helpers are implemented and
      tested.
    - Root `--config` CLI wiring and command default application are
      implemented and tested.
  - Phase 5, Effective-Type Override Handling, is the next incomplete
    remediation phase.
  - Phase 6 remains incomplete.

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
- Added `ResponseClassification` and `ParseConfidence` models to the public
  query response contract.
- Added required `classification` and `parse_confidence` fields to
  `ToolResponse`, populated through a `tool_response` factory with
  deterministic defaults per tool and response status.
- Routed resolver and graph helper response construction through the metadata
  factory.
- Updated `schemas/tool_response.schema.json` to require classification and
  parse-confidence metadata.
- Added model/schema tests, v1 resolver metadata coverage, CLI serialization
  assertions, and MCP protocol assertions for the new fields.
- Marked Phase 2 complete in `REMEDIATION_PLAN.md`.
- Added `BuildMetrics` aggregation for the Section 16 ingestion counters.
- Extended `ImportSummary` with unresolved xref and include-row counters.
- Added metrics to `BuildSummary.as_jsonable()` and persisted them under
  `build_metadata.metadata_json["metrics"]`.
- Added tests for metrics aggregation, fixture build metrics content,
  metadata persistence, unresolved xref counts, and unresolved include counts.
- Added `QualityGateSettings`, quality-gate evaluation, and
  `BuildQualityGateError`.
- Added `build` and `build-fixture` flags for unresolved xref rate,
  unresolved include-row rate, parse warning count, and
  `--allow-gate-failures`.
- Added CLI tests proving gate failures exit nonzero and
  `--allow-gate-failures` emits warning output with exit zero.
- Marked Phase 3 complete in `REMEDIATION_PLAN.md`.
- Added `PyYAML` as a runtime dependency and `types-PyYAML` for strict mypy.
- Added `src/dicom_kb/config.py` with strict Section 17 `dicom_kb` profile
  loading, SQLite URL validation, citation-safety validation, environment
  parsing helpers, and CLI > environment > config > default precedence helper.
- Added config unit tests for valid profile loading, unknown-key rejection,
  invalid YAML, invalid database URL scheme, disabled citation rejection,
  precedence ordering, SQLite URL path conversion, and environment parsing.
- Added root `--config <path>` support to the CLI.
- Applied config/environment defaults to fetch, build, verify, query, MCP,
  and eval command paths while preserving explicit CLI flag precedence.
- Added CLI tests proving config supplies build/query defaults and CLI flags
  override profile values.
- Added a config unit test for the public-CI Section 17 profile shape.
- Marked Phase 4 complete in `REMEDIATION_PLAN.md`.

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
- 2026-06-13: `uv run pytest tests/unit/test_query_resolver.py
  tests/unit/test_json_schemas.py tests/unit/test_cli_lookup.py
  tests/unit/test_mcp_protocol.py` passed (`59 passed`).
- 2026-06-13: `uv run pytest` passed (`186 passed, 4 skipped`).
- 2026-06-13: `uv run ruff check src/dicom_kb/query/answer_contracts.py
  src/dicom_kb/query/resolver.py src/dicom_kb/query/graph.py
  tests/unit/test_json_schemas.py tests/unit/test_query_resolver.py
  tests/unit/test_cli_lookup.py tests/unit/test_mcp_protocol.py` passed.
- 2026-06-13: `uv run mypy src/dicom_kb/query/answer_contracts.py
  src/dicom_kb/query/resolver.py src/dicom_kb/query/graph.py` passed.
- 2026-06-13: `uv run pytest tests/unit/test_build.py
  tests/unit/test_db_importers.py` passed (`15 passed`).
- 2026-06-13: `uv run ruff check src/dicom_kb/build.py
  src/dicom_kb/db/importers.py tests/unit/test_build.py
  tests/unit/test_db_importers.py` passed.
- 2026-06-13: `uv run mypy src/dicom_kb/build.py
  src/dicom_kb/db/importers.py` passed.
- 2026-06-13: `uv run pytest tests/unit/test_build.py
  tests/unit/test_db_importers.py tests/unit/test_cli_lookup.py
  tests/unit/test_sources_verify.py` passed (`43 passed`).
- 2026-06-13: `uv run pytest` passed (`189 passed, 4 skipped`).
- 2026-06-13: `uv run pytest tests/unit/test_build.py
  tests/unit/test_cli_build.py tests/unit/test_cli_lookup.py` passed
  (`27 passed`).
- 2026-06-13: `uv run ruff check src/dicom_kb/build.py
  src/dicom_kb/cli/main.py tests/unit/test_build.py
  tests/unit/test_cli_build.py` passed.
- 2026-06-13: `uv run mypy src/dicom_kb/build.py
  src/dicom_kb/cli/main.py` passed.
- 2026-06-13: `uv run pytest` passed (`192 passed, 4 skipped`).
- 2026-06-13: `uv run pytest tests/unit/test_config.py` passed
  (`8 passed`).
- 2026-06-13: `uv run ruff check src/dicom_kb/config.py
  tests/unit/test_config.py` passed.
- 2026-06-13: `uv run mypy src/dicom_kb/config.py` passed.
- 2026-06-13: `uv run pytest tests/unit/test_cli_config.py
  tests/unit/test_cli_build.py tests/unit/test_cli_lookup.py
  tests/unit/test_config.py` passed (`34 passed`).
- 2026-06-13: `uv run ruff check src/dicom_kb/cli/main.py
  src/dicom_kb/config.py tests/unit/test_cli_config.py
  tests/unit/test_config.py` passed.
- 2026-06-13: `uv run mypy src/dicom_kb/cli/main.py
  src/dicom_kb/config.py` passed.
- 2026-06-13: `uv run pytest` passed (`204 passed, 4 skipped`).

## Blockers

- None.

## Open Decisions

- Phase 4 configuration profiles should be implemented as specified unless
  later remediation discovers a spec conflict.
- Phase 5 effective-type override handling should remain conservative and
  should not broaden into full condition parsing.

## Next Recommended Task

Begin Phase 5 effective-type override handling:

1. Add a bounded detector in `query/conditions.py` for explicit type
   override phrases in matched attribute-use descriptions/condition text.
2. Return explicit override results when exactly one override is detected,
   and surface conflicting/ambiguous override text as partially decidable.
3. Add synthetic resolver tests for no override, one override, conflicting
   overrides, and ambiguous prose.
