# Remediation Plan

This plan resolves the remaining near-term spec gaps identified after the
v1 implementation review. The official URL gap is excluded because it has
already been remediated in `fix(query): emit official URLs in refs`.

Each phase should land as one or more granular commits, with tests passing
for the affected surface before moving to the next phase.

## Current Remaining Gaps

| Gap | Source | Current state | Target state |
|---|---|---|---|
| Response classification and parse confidence | `SYSTEM_SPECS.md` Section 11 and Section 12 | Tool responses expose refs and warnings but no explicit classification or parse-confidence field. | Every public query response exposes deterministic classification and confidence metadata. |
| Build metrics and quality gates | `SYSTEM_SPECS.md` Section 16 | Build output includes broad import counts and parser warnings, but lacks specific unresolved counters and gate failures. | Build output and build metadata include aggregate metrics; configurable gates fail builds when thresholds are exceeded. |
| CLI and Makefile surface parity | Work order I and Section 5 examples | `doctor` exists, but `verify`, `context attribute`, and `test-dicom-current` do not. | Documented command examples work or have explicit aliases. |
| Configuration profiles | `SYSTEM_SPECS.md` Section 17 | Configuration is CLI-flag driven. | YAML config profiles can provide defaults for fetch, build, query, MCP, and eval commands. |
| Effective-type override caveat | `SYSTEM_SPECS.md` effective type rule | Resolver applies lowest-type rule and warns that description overrides are not checked. | Resolver either applies known explicit overrides or returns a bounded, classified warning when override detection is not machine-decidable. |

## Phase 1: Surface Parity

Status: Complete. The documented `verify` command, `context attribute`
alias, `test-dicom-integration` alias, and opt-in `test-dicom-current`
target have been implemented with focused tests.

Goal: make documented command examples runnable without changing response
contracts or ingestion semantics.

Scope:

- Add `dicom-kb verify --edition <edition>`.
- Add `dicom-kb context attribute <attribute> --iod <iod>` as an alias for
  `dicom-kb resolve attribute-context`.
- Add `make test-dicom-integration` as an alias for `make test-integration`.
- Add `make test-dicom-current` as an opt-in networked target.

Implementation details:

- Implement verification in a small reusable module, for example
  `src/dicom_kb/sources/verify.py`.
- `verify` should read the edition manifest, recompute cached artifact
  SHA-256 values, confirm all manifest paths exist, open the SQLite DB if
  present, and compare DB build metadata to the manifest edition and
  manifest SHA-256.
- `verify` should return a JSON object with `status`, `edition`,
  `manifest_sha256`, `artifact_checks`, `db_checks`, and `warnings`.
- The `context attribute` command should call the existing resolver path so
  the alias cannot drift from `resolve attribute-context`.
- `test-dicom-current` should run only tests marked for live current-edition
  resolution. It must not run as part of the default offline test target.

Tests:

- Unit tests for checksum pass, checksum mismatch, missing artifact, missing
  DB, and DB metadata mismatch.
- CLI tests for `verify` JSON output and non-zero failure behavior.
- CLI tests showing `context attribute` and `resolve attribute-context`
  produce equivalent payloads for fixture data.
- Makefile smoke check by running the alias targets that do not require
  network access.

Acceptance criteria:

- `dicom-kb verify --edition 2026b --cache-dir <fixture-cache>` succeeds on
  a freshly built fixture.
- A corrupted cached artifact makes `verify` fail with a structured error.
- Existing CLI, MCP, and query tests continue to pass.

## Phase 2: Response Classification and Parse Confidence

Status: Complete. Public `ToolResponse` envelopes now require
`classification` and `parse_confidence`, schema validation requires both
fields, and Python, CLI, and MCP tests cover representative metadata.

Goal: make the public response envelope fully express the Section 11 safety
classification and the Section 12 parse-confidence requirement.

Scope:

- Add a required `classification` object to `ToolResponse`.
- Add a required `parse_confidence` object to `ToolResponse`.
- Update JSON schema, CLI serialization, MCP schema behavior, examples, and
  agent regression expectations.

Implementation details:

- Add Pydantic models in `query/answer_contracts.py`:
  `ResponseClassification` with `normativity`, `evidence_level`, and
  `machine_decidability`; and `ParseConfidence` with `level`,
  `source`, and optional `notes`.
- Use deterministic defaults per tool:
  - Registry and graph lookups: `normative`, `parsed_registry` or
    `parsed_table`, `decidable`.
  - Effective context resolution: `normative`, `parsed_cross_reference`,
    `partially_decidable`.
  - Text retrieval and text search: `explanatory`, `retrieved_text`,
    `not_applicable`.
  - Not-found and validation responses: `unsupported`, evidence matching the
    attempted route, `not_applicable`.
- Represent parse confidence as conservative metadata, not a probability.
  Suggested levels: `high`, `medium`, `low`, `unknown`.
- Set high confidence for exact parsed registry/table facts without parser
  warnings; medium confidence for query-time graph traversals with warnings
  or unresolved include/xref context; low confidence for raw text retrieval;
  unknown for validation failures before lookup.
- Keep this as an additive response-envelope change, but treat the fields as
  required once introduced so future tools cannot omit them.

Tests:

- Unit tests for model validation and JSON schema required fields.
- Resolver tests for representative response classes from every v1 tool.
- CLI snapshot/schema tests for serialized output.
- MCP protocol tests confirming the new fields are emitted unchanged.
- Agent regression fixture updates where cases require classification or
  parse confidence.

Acceptance criteria:

- Every `ToolResponse` emitted by Python API, CLI, and MCP includes
  `classification` and `parse_confidence`.
- Unsupported answers remain explicit and do not receive normative
  classification.
- `schemas/tool_response.schema.json` rejects envelopes missing either new
  field.

## Phase 3: Build Metrics and Quality Gates

Goal: make ingestion quality observable and fail-fast when configured
thresholds are exceeded.

Scope:

- Extend build metrics with Section 16 counters.
- Add quality-gate evaluation to `build` and `build-fixture`.
- Persist metrics with build metadata.

Implementation details:

- Add a `BuildMetrics` model that aggregates per-import summaries plus
  parser warnings into one JSON object.
- Extend `ImportSummary` or add a separate metrics collector for:
  `include_rows_resolved`, `include_rows_unresolved`, `xrefs_total`,
  `xrefs_unresolved`, `parse_warnings`, and `source_refs`.
- Count unresolved include rows from `attribute_use` rows where
  `include_target_text` is present and no `included_macro_id` was resolved.
- Count unresolved xrefs from the imported xref records where `resolved` is
  false.
- Add quality-gate settings:
  `--max-unresolved-xref-rate`,
  `--max-unresolved-include-rate`,
  `--max-parse-warnings`, and
  `--allow-gate-failures`.
- Default thresholds should be conservative for fixture builds and explicit
  for real builds. If a default threshold would block known current real
  builds, start with warning-only defaults and document stricter CI values.
- Store the emitted metrics JSON in `build_metadata.metadata_json` under a
  stable `metrics` key. Add a migration only if a separate table becomes
  necessary.

Tests:

- Unit tests for metrics aggregation from synthetic summaries.
- Database/importer tests for unresolved xref and unresolved include counts.
- CLI tests proving quality-gate failures produce non-zero exits.
- CLI tests proving `--allow-gate-failures` emits warnings but exits zero.
- Fixture build test asserting the metrics object contains every Section 16
  key.

Acceptance criteria:

- `dicom-kb build-fixture` emits `metrics` with all Section 16 counters.
- Configured gate failures fail the build before the command reports
  success.
- Metrics are persisted in build metadata and can be inspected after the DB
  is created.

## Phase 4: YAML Configuration Profiles

Goal: let local and CI workflows provide stable command defaults without
duplicating long CLI flag lists.

Scope:

- Add YAML profile loading for the Section 17 `dicom_kb` shape.
- Support config defaults for fetch, build, query, MCP, and eval commands.
- Preserve CLI flags as the highest-precedence source.

Implementation details:

- Add `PyYAML` as a runtime dependency and load profiles with
  `yaml.safe_load`.
- Add `src/dicom_kb/config.py` with a typed Pydantic model:
  `edition`, `artifact_dir`, `database_url`, `allow_text_retrieval`,
  `max_text_excerpt_chars`, `require_citations`, `require_edition_pin`,
  `allow_network_fetch`, `use_synthetic_fixtures_only`,
  `require_dicom_download_for_integration`, and `publish_generated_db`.
- Add a global `--config <path>` option at the root Typer callback.
- Define precedence as: CLI flag, environment variable, config file,
  built-in default.
- Support only `sqlite:///` database URLs in v1. Reject other schemes with
  a structured validation error.
- Do not let a config file disable legal notices or citation requirements
  for public query responses.

Tests:

- Unit tests for valid profile loading, unknown-key rejection, invalid YAML,
  invalid database URL scheme, and precedence ordering.
- CLI tests proving `--config` supplies edition/cache/db defaults.
- Tests proving explicit CLI flags override profile values.

Acceptance criteria:

- The two Section 17 example profiles can be parsed after path values are
  pointed at temporary test directories.
- Commands still work without a config file.
- Config loading does not change default offline test behavior.

## Phase 5: Effective-Type Override Handling

Goal: remove the open-ended caveat around "lowest type unless the attribute
description explicitly states otherwise" without overclaiming automated
reasoning.

Scope:

- Audit real PS3.3 attribute-use descriptions for override language.
- Add an explicit resolver path for detected override language.
- Keep non-machine-decidable cases visible in response classification and
  warnings.

Implementation details:

- Add a small detector in `query/conditions.py` for phrases that explicitly
  state a type override, such as "shall be Type 1", "shall be Type 2", or
  "is Type 3 in this module".
- The detector should operate only on matched attribute-use description
  text and condition text already stored in the KB; it must not perform
  broad prose search.
- When exactly one override is detected, return that type with an
  explanation and cite the source ref containing the override text.
- When conflicting or ambiguous override language is detected, keep the
  lowest-type result out of the primary result field and return
  `partially_decidable` classification with a warning and the candidate
  source refs.
- If no override language is detected, keep the existing lowest-type rule
  but remove the blanket warning for cases where all matched descriptions
  were inspected.

Tests:

- Synthetic fixture tests for no override, one explicit override,
  conflicting overrides, and ambiguous prose.
- Resolver tests asserting classification and warnings for each case.
- Real-KB golden tests for at least one common attribute that still follows
  the lowest-type rule.

Acceptance criteria:

- Effective type responses distinguish computed lowest-type results from
  explicit override results.
- Ambiguous override text is surfaced as partially decidable rather than
  silently resolved.
- Existing macro expansion provenance remains intact.

## Phase 6: Documentation and Release Gate

Goal: make the remediated behavior visible to users and lock it into the
release process.

Scope:

- Update `README.md`, `docs/agent_tools.md`, `docs/quickstart.md`, and
  `docs/build_local_kb.md` where command examples or response examples
  change.
- Update `IMPLEMENTATION_REVIEW.md` or add an implementation progress note
  recording each gap as resolved.
- Add release checklist items for response classification, build metrics,
  config profile compatibility, and `verify`.

Tests:

- Run the default offline verification set:
  `make lint`, `make typecheck`, and `make test`.
- Run integration tests against a locally downloaded official edition before
  marking the remediation set complete.

Acceptance criteria:

- Documentation examples match implemented command names and response
  envelopes.
- Offline tests pass.
- Integration tests pass or any skipped checks are documented with the
  missing local prerequisite.

## Suggested Commit Order

1. `feat(cli): add verification and context alias`
2. `test(cli): cover verification and alias behavior`
3. `feat(query): add response classification metadata`
4. `test(query): require classification in response envelopes`
5. `feat(build): emit ingestion quality metrics`
6. `feat(build): enforce configurable quality gates`
7. `feat(config): load YAML profiles`
8. `feat(query): inspect effective type override text`
9. `docs(remediation): document completed spec gap fixes`

The documentation-only commit that introduces this file should remain
separate from implementation commits.
