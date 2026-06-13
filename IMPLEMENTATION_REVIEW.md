# Implementation Review — v1 vs SYSTEM_SPECS.md

**Review date:** 2026-06-12
**Reviewed at commit:** `5983e41` (docs(progress): record external agent harness)
**Scope:** full review of the completed v1 implementation against
`SYSTEM_SPECS.md` (§1–§17, Work orders A–J, v1 acceptance criteria).

---

## 0. Post-Review Status

**Updated:** 2026-06-13

Follow-up work has been completed for the active v1 review findings. The
original findings remain below as historical review context; the current
implementation status is:

| Original finding | Status | Resolution |
|---|---|---|
| G1 — refs never include official URLs | Resolved | Source refs now derive official DICOM URLs during import and query serialization. |
| G2 — response classification / parse confidence absent | Resolved | `ToolResponse` now requires `classification` and `parse_confidence`; Python, CLI, MCP, and JSON schema tests cover the fields. |
| G3 — build metrics and quality gates partial | Resolved | Build output and build metadata now include aggregate ingestion metrics; `build` and `build-fixture` support configurable gate flags. |
| G4 — `dicom-kb verify` missing | Resolved | `dicom-kb verify --edition <edition>` validates cached artifacts and database build metadata. |
| G5 — `context attribute` naming deviation | Resolved | `dicom-kb context attribute` is implemented as an alias for `resolve attribute-context`. |
| G6 — DICOM integration Make targets missing | Resolved | `make test-dicom-integration` and opt-in `make test-dicom-current` are available. |
| G7 — YAML config profiles absent | Resolved | Root `--config` loads a strict top-level `dicom_kb` YAML profile with CLI > environment > config > default precedence. |
| G8 — effective-type override caveat | Resolved | Attribute-context resolution now inspects matched row description and condition text for bounded override language and withholds ambiguous/conflicting results. |

Current release-gate documentation lives in `docs/release_checklist.md`.

## 1. Verdict

The v1 implementation is **substantially complete and verified working**.
All eleven v1 acceptance criteria (§12) are met in substance. The original
review findings are preserved below as historical context; the current
post-review status is summarized in §0 and §4.

## 2. Verification basis

Findings are empirical, not read-only:

| Check | Result |
|---|---|
| `make test` (offline unit + agent regression) | 133 passed |
| `make lint` (ruff) | clean |
| `make typecheck` (mypy, 47 source files) | clean |
| `make test-integration` against a real locally built 2026b KB | 41 passed, 3 skipped* |
| Live CLI queries (`lookup tag`, `resolve attribute-context`) against real 2026b KB | correct envelopes, correct facts |
| Fixture build (`dicom-kb build-fixture`) | import summary emitted; concrete-edition validation enforced |

\* Skips are optional differential checks gated on `pydicom` being
installed and `DICOM_KB_INNOLITICS_PATH` being set — consistent with
§4.2 (secondary sources, differential testing only).

## 3. Findings

### 3.1 Confirmed compliant

- **Data model (§7).** All 18 spec tables exist essentially
  column-for-column across `src/dicom_kb/db/migrations/001–007`, with the
  exact uniqueness constraints the spec calls out (`(edition_id, tag)` on
  `data_element`, `(edition_id, uid_value)` on `uid_registry_entry`,
  `(edition_id, name, section)` on `module`, `(edition_id, table_id)` on
  `macro`), `source_ref_id NOT NULL` on every fact table, plus the
  spec-required raw table IR snapshots (`raw_table_ir`, migration 004),
  FTS5 search (migration 005), and embedded build metadata (migration 006).
- **Tool contract (§8).** The common envelope (edition, tool, input,
  status, result, refs, warnings, notice, trace with
  query_id/resolved_at/source_manifest_sha256) is enforced via a frozen
  Pydantic model (`src/dicom_kb/query/answer_contracts.py:59`). All nine
  v1 tools (§8.7) exist on all three surfaces — Python API, CLI, MCP with
  `dicom_` prefixes — satisfying acceptance criterion 10, plus two
  forward v2 tools (enumerated values / defined terms). Unknown,
  ambiguous, and malformed inputs return `not_found` /
  `validation_error` with candidates; never fabricated data.
- **Core semantics.** Include rows are *not* expanded at parse time;
  query-time expansion preserves dual provenance (verified by the
  real-KB golden `test_real_kb_module_macro_include_expands_with_dual_provenance`).
  Effective type uses the lowest-type rule
  (`src/dicom_kb/query/conditions.py:140`). Range tags
  (`(60xx,3000)`-style) match concrete lookups with exact-match
  precedence. Zero-width-space stripping, retired markers, table
  captions, row order, and unresolved-xref warnings (§10.2) are all
  implemented and tested. `current` must resolve to a concrete edition
  label before storage (validation error confirmed live).
- **Legal and distribution (§1, §5).** Exact non-affiliation wording in
  `README.md`, `NOTICE`, CLI (`doctor`), and generated manifests
  (`sources/manifest.py`). Apache-2.0 with the required README scope
  statement. No vendored official artifacts; committed fixtures are
  genuinely synthetic; `.gitignore` covers every required exclusion;
  Dockerfile is code-only with the `/data/dicom-standard-kb` default.
- **Testing (§15, WO-J).** 67 edition-pinned agent regression cases
  (spec requires ≥50). Golden coverage of all six §15.2 IODs, including
  Enhanced CT functional-group traversal. Differential harnesses for
  Innolitics and pydicom exist. CI runs lint/typecheck/tests offline.

### 3.2 Gaps and deviations

| # | Severity | Finding | Evidence |
|---|---|---|---|
| G1 | **High** | Refs never include official URLs. §8 requires "refs (with official URLs where derivable)" and the §8.1 example shows `official_url`. The `StandardRef.official_url` field exists but `source_ref.canonical_url` is populated for **0 of 7,938** rows in the real 2026b build; no URL-derivation logic exists anywhere. URLs *are* derivable from the stored part/anchor pairs. | `query/answer_contracts.py:266`; `SELECT count(*), count(canonical_url) FROM source_ref` → `7938\|0` |
| G2 | Medium | §11 answer classification (`normativity` / `evidence_level` / `machine_decidability`) is absent — zero occurrences in src, tests, or schemas. Relatedly, the §12 v1 deliverables promise "parse confidence" in responses; no such field exists (warnings partially substitute). | repo-wide grep |
| G3 | Medium | §16 metrics partial. Import summaries emit most counts, but `include_rows_resolved` / `include_rows_unresolved`, `xrefs_unresolved`, and `parse_warnings` are missing from the emitted summary, and no configurable quality-gate thresholds exist (unresolved-rate gates, count-drift gates, warning baselines). | `db/importers.py` (`ImportSummary`); fixture build output |
| G4 | Low | `dicom-kb verify --edition <e>` (WO-I example) is not implemented. `doctor` exists. | `cli/main.py` command list |
| G5 | Low | CLI naming deviation: spec example `dicom-kb context attribute Modality --iod "CT Image"` is implemented as `dicom-kb resolve attribute-context` (functionally equivalent). | `cli/main.py:807` |
| G6 | Low | `make test-dicom-current` (§5.3, optional networked current-resolution test) does not exist. Note: the spec is internally inconsistent — §5.3 names `test-dicom-integration` / `test-dicom-current`, while WO-A names `test-integration`; the implementation followed WO-A. | `Makefile` |
| G7 | Low | §17 configuration profiles (YAML) not implemented; configuration is entirely CLI-flag driven. The spec never gates v1 on this. | no config-file loading in `src/` |
| G8 | Info | Effective-type override caveat: the spec's "lowest type unless the attribute description explicitly states otherwise" is handled by always applying lowest-type and emitting a warning that descriptions were not checked for overrides — honest, but not full compliance. | `query/conditions.py:151` |

### 3.3 Intentional deferrals (correctly out of v1 scope)

- HTTP API / `src/dicom_kb/api/` — explicitly optional post-v1 (§12,
  §13 WO-I); `make run-api` stubs this with a message.
- PostgreSQL deployment — post-v1 (§13 WO-A completion note).
- Vector indexes / `indexes/` cache directory — v2+ (§6.1).
- Condition expression parsing — v1 stores raw normative text with
  `machine_status` and `evaluator.available: false`, exactly as §7.7 and
  the v1 exclusions require.

## 4. Follow-Up Status

The v1 follow-up work resolved the active review gaps without changing
`SYSTEM_SPECS.md`. Current user-facing release gates are documented in
`docs/release_checklist.md`.

## 5. v1 acceptance criteria scorecard (§12)

| # | Criterion | Status |
|---|---|---|
| 1 | Fetch/load pinned edition, reproducible manifest, `current` resolves concrete | Met |
| 2 | PS3.6 data elements incl. range rows | Met |
| 3 | PS3.6 UID registry | Met |
| 4 | PS3.3 IOD module tables → graph | Met |
| 5 | Module + macro attribute tables, include rows, functional groups | Met |
| 6 | PS3.4 SOP Class → IOD where deterministic | Met |
| 7 | Every response: edition, result, refs, warnings | Met |
| 8 | Unknown/ambiguous → candidates or structured errors | Met |
| 9 | Golden suite: 6 IODs + transfer syntax UIDs | Met |
| 10 | Same functionality via Python, CLI, MCP | Met |
| 11 | No bulk standard content in repo/PyPI/Docker | Met |
