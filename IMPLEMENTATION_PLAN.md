# V2 Implementation Plan

This plan covers the full v2 roadmap from `SYSTEM_SPECS.md`: PS3.5,
selected PS3.7, selected PS3.8, PS3.10, PS3.16, PS3.18, and the v2 public
tools. It assumes the current v1 baseline described in
`IMPLEMENTATION_REVIEW.md`: local acquisition/build, DocBook parsing,
SQLite import, Python API, CLI, MCP tools, source references,
classification, parse confidence, and the v1 PS3.3/PS3.4/PS3.6 graph are
already working.

## V2 Invariants

- Keep the repository a knowledge-base builder. Do not commit official
  DICOM artifacts, generated full databases, bulk standard exports, vector
  indexes, or standalone terminology dumps.
- Keep all normative facts edition-pinned and citation-preserving.
- Store ambiguous or prose-only rules as structured warnings or retrieved
  text, not inferred facts.
- Prefer parsed DocBook tables and structured lists over text search.
- Preserve raw table IR for every newly parsed table family.
- Expose each completed capability through Python, CLI, and MCP before
  marking the phase complete.
- End every logical unit with tests and a granular commit, following
  `AGENTS.md`.

## Phase 0 - V2 Contract Baseline

Goal: define the v2 public data contracts and migration shape before parsing
new parts.

Deliverables:

- Add v2 JSON schema coverage for the new response payloads where the
  existing generic envelope is too loose.
- Add placeholder-free Pydantic result builders in
  `src/dicom_kb/query/answer_contracts.py` for:
  `lookup_vr`, `lookup_transfer_syntax`, `explain_encoding_rule`,
  `lookup_dicomweb_transaction`, `lookup_media_type`,
  `lookup_sr_template`, `lookup_context_group`, and `lookup_code_meaning`.
- Decide the canonical table names for v2 migrations before writing
  importers.
- Add CLI/MCP command names to tests as expected-failing design fixtures only
  if the repo already has a pattern for such tests. Otherwise keep this phase
  to schema and docs.

Suggested schema additions:

- `vr_definition`: VR keyword, name, value representation class,
  fixed/variable length notes, padding behavior, character repertoire notes,
  binary/text classification, source ref.
- `transfer_syntax_detail`: UID row link, explicit/implicit VR,
  endian behavior, encapsulation/compression family, retired status,
  encoding notes, source refs.
- `file_meta_requirement`: attribute link, type designation, rule context,
  source ref.
- `dicomweb_transaction`: transaction name, resource category, HTTP method,
  route template, request constraints, response constraints, status codes,
  media type refs, source refs.
- `dicom_media_type`: media type, service context, transfer syntax
  constraints, request/response direction, source ref.
- `sr_template`, `sr_template_row`: TID, name, extensibility, order,
  relationship type, value type, concept name, cardinality, condition,
  source refs.
- `context_group`, `context_group_row`: CID, name, extensibility, version,
  coding scheme, code value, code meaning, include references, source refs.
- `coded_concept`: code value, coding scheme designator, coding scheme
  version, code meaning, source refs.

Tests:

- Schema validation tests for representative v2 response envelopes.
- Migration smoke test on an empty database.
- Contract tests asserting v1 response payloads remain backward compatible.

Exit criteria:

- V2 contracts are explicit enough that parser phases can target stable
  entities.
- `make lint`, `make typecheck`, and `make test` pass.

## Phase 1 - Acquisition and Parser Foundation for New Parts

Goal: let the existing fetch/build pipeline ingest the v2 source parts
without changing query behavior yet.

Deliverables:

- Extend official artifact defaults or build options to include PS3.5,
  PS3.7, PS3.8, PS3.10, PS3.16, and PS3.18.
- Add parser modules:
  `src/dicom_kb/parsers/part05_encoding.py`,
  `src/dicom_kb/parsers/part07_messages.py`,
  `src/dicom_kb/parsers/part08_network.py`,
  `src/dicom_kb/parsers/part10_media_storage.py`,
  `src/dicom_kb/parsers/part16_content_mapping.py`, and
  `src/dicom_kb/parsers/part18_web_services.py`.
- Reuse the existing DocBook parser and raw table IR path for all new parts.
- Add synthetic fixtures for each new part under `tests/fixtures_synthetic/`.
- Record unsupported tables and unresolved xrefs as warnings in import
  metrics.

Tests:

- Fetch manifest tests for each new part and for `current` resolution.
- Parser smoke tests that extract document nodes, source refs, raw table IR,
  and warnings from each synthetic part fixture.
- Build-fixture test including at least one v2 part.

Exit criteria:

- New parts can be loaded locally and represented in the database with source
  refs and raw table IR.
- No public v2 tool is advertised as complete yet.

## Phase 2 - PS3.5 VR and Transfer Syntax Semantics

Goal: implement the highest-value encoding lookup capabilities.

Deliverables:

- Parse VR behavior from PS3.5 into `vr_definition`.
- Enrich PS3.6 transfer syntax UID rows with PS3.5 encoding details in
  `transfer_syntax_detail`.
- Implement Python resolver functions for:
  `lookup_vr(vr)`, `lookup_transfer_syntax(uid_or_keyword)`, and
  `explain_encoding_rule(topic)`.
- Add CLI commands:
  `dicom-kb lookup vr <vr>`,
  `dicom-kb lookup transfer-syntax <uid-or-keyword>`, and
  `dicom-kb explain encoding <topic>`.
- Add MCP tools:
  `dicom_lookup_vr`,
  `dicom_lookup_transfer_syntax`, and
  `dicom_explain_encoding_rule`.

Parsing scope:

- VR name and short code.
- Text/binary categorization where deterministic.
- Explicit versus implicit VR applicability.
- Endianness and encapsulation properties for transfer syntaxes.
- Retired transfer syntax status remains sourced from PS3.6.
- Prose-only encoding details are returned as cited retrieved text or
  bounded notes.

Tests:

- Synthetic PS3.5 fixture covering at least `PN`, `OB`, `SQ`, and `UN`.
- Transfer syntax lookup fixtures for Explicit VR Little Endian, Implicit VR
  Little Endian, Deflated Explicit VR Little Endian, and one encapsulated
  transfer syntax.
- Integration golden tests against a locally built official edition, gated
  under `tests/integration_requires_dicom_download/`.
- CLI snapshots and MCP schema validation for all three tools.

Exit criteria:

- V2 acceptance criterion 1 is satisfied.
- Encoding explanations cite PS3.5 or structured transfer syntax refs.

## Phase 3 - PS3.10 File Meta and Media Type Foundation

Goal: support file meta information and reusable media-type semantics needed
by later web-service lookups.

Deliverables:

- Parse PS3.10 file meta information requirements into
  `file_meta_requirement`.
- Parse PS3.10 media storage and file format rules where they can be
  represented deterministically.
- Introduce `dicom_media_type` rows that can later be joined from PS3.18.
- Extend `lookup_media_type(media_type_or_context)` for PS3.10-derived
  media contexts first.

Tests:

- File meta fixture covering required File Meta Information Group Length,
  Media Storage SOP Class UID, Media Storage SOP Instance UID,
  Transfer Syntax UID, Implementation Class UID, and optional fields.
- Query tests for required and optional file meta attributes.
- Text fallback test for prose-only file format rules.

Exit criteria:

- File meta requirements are queryable with type designations and citations.
- `lookup_media_type` has a working baseline before PS3.18 expansion.

## Phase 4 - PS3.18 DICOMweb Transactions

Goal: implement DICOMweb route and media-type lookup from structured PS3.18
tables.

Deliverables:

- Parse DICOMweb transaction tables into `dicomweb_transaction`.
- Parse route templates, HTTP methods, resource categories, request
  constraints, response constraints, status codes, and referenced media
  types.
- Expand `dicom_media_type` with PS3.18 request/response contexts.
- Implement Python resolver functions for
  `lookup_dicomweb_transaction(name_or_route)` and the complete
  `lookup_media_type(media_type_or_context)`.
- Add CLI commands:
  `dicom-kb lookup dicomweb <name-or-route>` and
  `dicom-kb lookup media-type <media-type-or-context>`.
- Add MCP tools:
  `dicom_lookup_dicomweb_transaction` and `dicom_lookup_media_type`.

Tests:

- Synthetic PS3.18 fixture for at least WADO-RS Retrieve, STOW-RS Store,
  QIDO-RS Search, and one rendered media negotiation example.
- Route matching tests for literal route names and route templates.
- Ambiguous route tests return candidates, not guessed transactions.
- Integration goldens for representative official-edition transactions.

Exit criteria:

- V2 acceptance criterion 2 is satisfied.
- Media type lookup returns constraints and references from PS3.18 when
  available, falling back to PS3.10 or text retrieval where appropriate.

## Phase 5 - PS3.16 SR Templates, Context Groups, and Codes

Goal: implement structured Content Mapping Resource lookup without
publishing standalone terminology dumps.

Deliverables:

- Parse SR template metadata and rows into `sr_template` and
  `sr_template_row`.
- Parse context group metadata and rows into `context_group` and
  `context_group_row`.
- Parse coded concepts into `coded_concept` only as needed for local lookup
  and template/context-group joins.
- Preserve include rows and references between templates/context groups.
- Implement Python resolver functions:
  `lookup_sr_template(tid)`, `lookup_context_group(cid)`, and
  `lookup_code_meaning(code_value, scheme?)`.
- Add CLI commands:
  `dicom-kb lookup sr-template <tid>`,
  `dicom-kb lookup context-group <cid>`, and
  `dicom-kb lookup code <code-value> [--scheme <scheme>]`.
- Add MCP tools:
  `dicom_lookup_sr_template`,
  `dicom_lookup_context_group`, and `dicom_lookup_code_meaning`.
- Update legal docs if necessary to restate that PS3.16 terminology is built
  locally and not redistributed as a standalone terminology database.

Tests:

- Synthetic TID fixture with extensibility, relationship type, value type,
  cardinality, condition, and include rows.
- Synthetic CID fixture with baseline/defined/extensible metadata and coded
  rows.
- Code lookup ambiguity tests when the same code value appears under multiple
  schemes.
- Integration goldens for one common TID, one common CID, and one ambiguous
  code lookup.

Exit criteria:

- V2 acceptance criterion 3 is satisfied.
- PS3.16 outputs include explicit source refs and do not expose bulk export
  behavior.

## Phase 6 - Contextual Enumerated Values and Defined Terms

Goal: complete the already-started v2 value-term surface by linking terms
to their applicable attribute context.

Deliverables:

- Audit existing `attribute_value_term` import coverage.
- Extend parsing where enumerated values or defined terms appear in v2 parts
  or prose structures not covered by v1.
- Resolve value terms by attribute plus optional IOD, SOP Class, module,
  macro, TID, CID, or DICOMweb context where deterministic.
- Keep `lookup_enumerated_values(attribute, context?)` and
  `lookup_defined_terms(attribute, context?)` behavior consistent across
  Python, CLI, and MCP.

Tests:

- Context-specific defined term fixture where the same attribute has
  different terms in different modules or IODs.
- Ambiguous context test returns candidates and warnings.
- Integration tests for at least one PS3.3 term and one PS3.18 media or
  web-service term if available.

Exit criteria:

- V2 acceptance criterion 4 is satisfied.
- Existing v1 module and attribute resolution remains unchanged.

## Phase 7 - Selected PS3.7 and PS3.8 Networking Semantics

Goal: cover the selected messaging/networking semantics promised by the v2
scope without expanding into full conformance validation.

Deliverables:

- Parse selected PS3.7 message/service semantics that are needed to explain
  DICOM service behavior.
- Parse selected PS3.8 networking topics that are stable enough for cited
  lookup and explanation.
- Feed deterministic topics into `explain_encoding_rule(topic)` or a shared
  explanatory lookup path only when the result is cited and bounded.
- Store prose-only sections as retrievable text chunks with source refs.

Tests:

- Synthetic fixtures for one PS3.7 selected service behavior and one PS3.8
  selected networking behavior.
- Retrieval fallback tests for prose-only rules.
- Agent regression prompts that verify the tools are called before answer
  synthesis.

Exit criteria:

- Selected PS3.7/PS3.8 content is available through structured lookup where
  possible and cited text retrieval otherwise.
- V2 acceptance criterion 5 is satisfied for v2 parts.

## Phase 8 - Evaluation Harness Expansion

Goal: raise coding-agent regression coverage from the v1 baseline to the
v2 requirement.

Deliverables:

- Add at least 33 new v2 prompt cases, bringing the total to 100 or more.
- Cover every v2 public tool at least once in expected tool traces.
- Include unsupported or ambiguous cases for each major domain:
  transfer syntax, DICOMweb, media type, TID, CID, and code lookup.
- Add scorecard output that reports v1 and v2 prompt groups separately if
  useful for triage.

Tests:

- `tests/agent_regression/` passes offline.
- Prompt cases remain edition-pinned.
- Failure reports identify missing tool calls, missing citations, and
  unsupported normative claims.

Exit criteria:

- V2 acceptance criterion 6 is satisfied.
- The agent harness is a release gate for v2.

## Phase 9 - V2 Release Hardening

Goal: make v2 safe to hand to users without changing the distribution model.

Deliverables:

- Update README, quickstart, agent tools docs, architecture docs, and release
  checklist for v2 commands and build expectations.
- Add official-edition integration goldens for representative PS3.5,
  PS3.10, PS3.16, and PS3.18 queries.
- Add build metrics for v2 parser warning counts and unresolved include/xref
  rates per part.
- Confirm Docker and PyPI packaging remain code-only.
- Confirm no generated official content or terminology dump is committed.

Required final gates:

```bash
make lint
make typecheck
make test
make test-dicom-integration
make test-dicom-current
```

Exit criteria:

- All v2 acceptance criteria in `SYSTEM_SPECS.md` are met.
- `IMPLEMENTATION_PROGRESS.md` has every v2 phase marked complete with
  commit hashes and verification notes.

## Suggested Commit Boundaries

- One commit for each schema/migration family.
- One commit for each parser module plus its synthetic fixtures.
- One commit for each query resolver/tool surface slice.
- One commit for each CLI/MCP exposure slice.
- One commit for each integration golden group.
- One commit for each docs/update phase.

Do not batch unrelated parts. For example, PS3.18 DICOMweb parsing and
PS3.16 context-group parsing should land in separate commits even if they
are developed in the same session.
