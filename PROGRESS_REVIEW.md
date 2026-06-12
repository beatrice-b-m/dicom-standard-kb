# Progress Review and Resolution Plan

Review date: 2026-06-12
Reviewed against: `SYSTEM_SPECS.md` (authoritative), `IMPLEMENTATION_PROGRESS.md`
Audience: coding agents resolving the listed work items autonomously.

---

## 1. Verified state at review time

All claims below were re-verified directly against the repository, not taken
from `IMPLEMENTATION_PROGRESS.md`:

- Working tree clean on `main` at `306778d`.
- `uv run --dev ruff check .` — clean.
- `uv run --dev mypy` — clean, 40 source files.
- `uv run --dev pytest` — 101 passed, ~1s, fully offline.
- All 13 core v1 build-sequence steps (SYSTEM_SPECS.md §14, steps 1–13) have
  at least a first slice landed. Source acquisition (WO-B) exceeds the v1
  minimum (archive fetch, multi-format download, CHTML mirroring).
- The nine v1 query tools exist and are exposed through Python API, CLI, and
  MCP (`src/dicom_kb/mcp/server.py`).

### Verified gaps

| ID | Gap | Severity |
|----|-----|----------|
| R1 | No test has ever run against real standard content; `tests/integration_requires_dicom_download/` does not exist; `make test-integration` fails at collection | **Critical** |
| R2 | Golden fixture coverage (§15.2) limited to one synthetic CT-style PS3.3 fixture; MR Image, Enhanced CT, Segmentation, Comprehensive SR, Encapsulated PDF goldens absent | **Critical** |
| R3 | `eval/prompt_cases.py` defines ~3 agent regression cases; spec (WO-J) requires ≥50 for v1 | High |
| R4 | No external-agent runner; no recorded answer transcripts committed; scorecard CLI exists but has nothing real to score | High |
| R5 | No MCP protocol-level smoke test with a real MCP client (only an in-process FastMCP double) | Medium |
| R6 | Repository layout drift from §6.2: missing `query/graph.py`, `query/conditions.py`, `query/citations.py`, `query/search.py`, `docbook/variablelists.py`, `mcp/tools.py`, `mcp/schemas.py`, `tests/fixtures_minimal_attributed/`, `examples/` | Medium |
| R7 | No differential testing against Innolitics dicom-standard or pydicom dicom-validator (§4.2, §15.1) | Medium |

### Headline assessment

The 101 green tests measure **internal consistency, not correctness**: every
parser test consumes synthetic fixtures authored to match parser
expectations. The single highest-value next action is exercising the full
pipeline against a real pinned edition (R1). R2–R4 depend on R1's output and
must follow it. R5–R7 are independent and may be done in any order or in
parallel.

```
R1 → R2 → R3 → R4
R5, R6, R7: independent (R7 benefits from R1's local artifacts)
```

---

## 2. Global rules for all work items

These apply to every item below; a resolution that violates them is invalid
even if its completion conditions pass.

1. **Never commit official artifacts or bulk derived content** (§5.1). No
   downloaded `part*.xml`/`*.pdf`/`*.html`, no generated SQLite databases,
   no bulk parsed JSON. Verify before every commit:
   `git diff --cached --stat` must show only code, docs, synthetic fixtures,
   or tiny attributed excerpts.
2. **Default test suite stays offline.** `make test` must pass on a clean
   checkout with no network and no cached artifacts. Anything requiring
   downloaded artifacts lives under
   `tests/integration_requires_dicom_download/` and is run only via
   `make test-integration`.
3. **Pin editions, never "current".** Resolve `current` to a concrete label
   (e.g. via `dicom-kb fetch --edition current`) before storing or asserting
   anything. Integration tests must discover the pinned edition from the
   local cache or an environment variable (`DICOM_KB_TEST_EDITION`), not
   hardcode one, because the available edition changes over time.
4. **Network availability is not guaranteed.** If an item requires
   downloading official artifacts and the network fetch fails, stop, record
   the blocker in `IMPLEMENTATION_PROGRESS.md`, and move to an independent
   item. Do not substitute fabricated or memory-derived standard content.
5. **Commit policy:** follow `AGENTS.md` exactly — granular
   `type(scope): subject` commits, selective staging, body explaining why.
6. **Update `IMPLEMENTATION_PROGRESS.md`** (stopping point, implemented
   behavior, commit list) in a `docs(progress)` commit after each completed
   item.
7. **Regression gate for every item:** `uv run --dev ruff check .`,
   `uv run --dev mypy`, and `uv run --dev pytest` must all pass before the
   item is considered complete. Test count must not decrease.
8. **Never answer normative DICOM questions from model memory** (§9.2). If
   an expected value is needed (a VR, a module list, a UID), obtain it from
   the locally built KB or the locally downloaded official artifact, and
   record the source ref alongside the expectation.

---

## 3. Work items

### R1 — End-to-end validation against a real pinned edition

**Priority:** Critical. Do this first.

**Problem.** The fetch/build machinery exists but the parsers have only ever
seen synthetic fixtures. Real PS3.3/PS3.4/PS3.6 DocBook contains spans,
footnotes, unusual indentation, and table variants that synthetic fixtures
cannot anticipate (§19 "Parser brittleness"). Additionally,
`tests/integration_requires_dicom_download/` does not exist, so
`make test-integration` fails at pytest collection.

**Resolution strategy.**

1. Run `uv run dicom-kb fetch --edition current` to resolve and download the
   v1 DocBook XML parts (PS3.3, PS3.4, PS3.6) into the local cache. Record
   the resolved concrete edition label. If the network fetch fails, apply
   global rule 4.
2. Run `uv run dicom-kb build --edition <resolved>` and capture the build
   output, including parse warnings and ingestion counts (§16 metrics shape
   if implemented; otherwise whatever the build reports).
3. Create `tests/integration_requires_dicom_download/` with:
   - a `conftest.py` that locates the cache (`~/.cache/dicom-standard-kb/`
     or `DICOM_KB_CACHE_DIR`), discovers the pinned edition (newest local
     edition, overridable via `DICOM_KB_TEST_EDITION`), and **skips the
     whole directory with a clear message** when no built database exists —
     a missing local KB must produce skips, not errors;
   - smoke tests that fetch+build outputs exist and the manifest validates
     against `schemas/source_manifest.schema.json`;
   - sanity-count tests: data elements > 4000, UID entries > 400, IODs > 100,
     modules > 200 (floor assertions, not exact counts, so edition bumps
     don't break them);
   - well-known-entity tests using the public resolvers:
     `lookup_data_element("(0008,0060)")` → Modality/CS/1,
     `lookup_uid("1.2.840.10008.1.2.1")` → Explicit VR Little Endian,
     `lookup_uid("1.2.840.10008.1.2.2")` → retired Explicit VR Big Endian,
     `list_modules_for_iod("CT Image")` includes Patient (M) and
     Contrast/Bolus (C), and a range-tag lookup (e.g. `(6002,3000)`)
     resolves to its `(60xx,3000)` range row with a warning.
4. Triage every parse warning and parser crash the real build surfaces.
   Fix parser bugs in separate `fix(parsers)`/`fix(docbook)` commits, each
   with a minimal synthetic-fixture reproduction added to the offline suite
   so the fix is protected without committing standard content.
5. Document the workflow in `docs/build_local_kb.md` if the real run reveals
   the documented steps are wrong or incomplete.

**Completion conditions.**

- [ ] `make test-integration` passes on a machine with fetched artifacts.
- [ ] `make test-integration` exits zero with skip messages (no collection
      errors) on a machine without artifacts.
- [ ] All well-known-entity assertions above pass against the real KB.
- [ ] Every parser warning class observed in the real build is either fixed
      (with an offline regression test) or documented as accepted in
      `IMPLEMENTATION_PROGRESS.md` with its count.
- [ ] No downloaded or generated artifact is committed (global rule 1).
- [ ] Offline gate passes (global rule 7).

---

### R2 — Golden fixture coverage per §15.2

**Priority:** Critical. Requires R1 (a built real-edition KB).

**Problem.** §15.2 enumerates golden entities (data elements, UIDs, IODs,
modules, macros) that v1 acceptance criterion 9 requires. Only CT Image has
any coverage, and only synthetically.

**Resolution strategy.**

1. In `tests/integration_requires_dicom_download/`, add golden tests for:
   - **IODs:** CT Image, MR Image, Enhanced CT Image, Segmentation,
     Comprehensive SR, Encapsulated PDF — `lookup_iod` resolves each;
     `list_modules_for_iod` returns a non-empty module list containing
     expected anchor modules (e.g. Patient, SOP Common for all six).
   - **Enhanced CT specifically:** functional-group macro resolution
     end-to-end — `iod_functional_group_use` rows exist, and
     `resolve_attribute_context` on an attribute reachable only through a
     functional group macro reports a non-empty `via_macro` path.
   - **Modules:** Patient, General Study, General Series, Image Pixel,
     SOP Common, CT Image, Contrast/Bolus — `list_attributes_for_module`
     returns rows; General Series contains Modality with type `1`.
   - **Macros:** at least one attribute macro included by a v1 module
     resolves through `expand_macros=true` with dual provenance, and one
     functional group macro used by Enhanced CT.
   - **Data elements / UIDs:** the full §15.2 lists (Modality, SOPClassUID,
     SOPInstanceUID, PixelData, TransferSyntaxUID, PatientName,
     StudyInstanceUID, SeriesInstanceUID; Verification SOP Class, CT/MR/
     Segmentation Storage, the four transfer syntaxes including the retired
     big-endian case).
   - **SOP Class → IOD:** CT Image Storage → CT Image IOD and Segmentation
     Storage → Segmentation IOD via `lookup_sop_class`.
2. Derive every expected value from the built KB or the downloaded XML and
   cross-check against the official rendered standard URL recorded in the
   source ref — never from model memory (global rule 8). Where a value is
   verified, note the source ref in a comment.
3. Where the parser cannot yet handle a golden entity (likely: SR and
   Enhanced families), mark the test `xfail(strict=True)` with a reason
   naming the parser limitation, and file the limitation in
   `IMPLEMENTATION_PROGRESS.md` under "Not yet implemented". Strict xfail
   ensures the test flips to a failure (forcing cleanup) once fixed.
4. Fix parser gaps that are tractable within the existing table-IR design;
   each fix follows the R1 pattern (synthetic repro in offline suite).

**Completion conditions.**

- [ ] Every §15.2 golden entity has an integration test that passes or is a
      strict xfail with a documented parser limitation.
- [ ] At least the CT Image, MR Image, and Encapsulated PDF golden sets pass
      outright (these exercise no exotic structures).
- [ ] Enhanced CT functional-group traversal passes end-to-end, or its
      blocking parser limitation is precisely documented (which table, which
      structure, what the parser does instead).
- [ ] Offline gate passes; no standard content committed.

---

### R3 — Agent regression case set: 3 → ≥50

**Priority:** High. Requires R1/R2 (expected traces must pin against real
KB answers, not invented ones).

**Problem.** WO-J completion requires at least 50 v1 prompt cases;
`eval/prompt_cases.py` currently defines about 3.

**Resolution strategy.**

1. Generate cases systematically across the nine v1 tools — roughly:
   per-tool happy paths over the §15.2 golden entities (~30 cases),
   error/ambiguity paths (unknown tag, malformed UID, ambiguous keyword,
   retired entity — ~10 cases), multi-tool workflows mirroring §18
   (SOP Class → IOD → modules → attributes → dictionary — ~10 cases).
2. Every case follows the §15.3 format: id, prompt, `expected_tools`,
   `must_include` (edition, source references), `must_not_include`
   (uncited normative claims, conformance certification).
3. Pin every case to a concrete edition field; where the expected answer
   embeds a fact (a VR, a usage letter), derive it from the R1-built KB and
   record the source ref in the case definition or an adjacent comment.
4. Keep scoring fully offline: cases and expected traces are code/data in
   `src/dicom_kb/eval/`; no network or local KB needed to *score* a
   transcript.
5. Add an offline test asserting the case count is ≥50 and that all case
   ids are unique and edition-pinned, so the floor cannot silently regress.

**Completion conditions.**

- [ ] ≥50 cases registered and retrievable through the existing
      `prompt_cases` API.
- [ ] All nine v1 tools appear in at least one case's `expected_tools`.
- [ ] At least 8 cases cover error/ambiguity responses.
- [ ] Offline test enforces the ≥50 floor, id uniqueness, edition pinning.
- [ ] Offline gate passes.

---

### R4 — External-agent runner and recorded transcripts

**Priority:** High. Requires R3.

**Problem.** WO-J specifies running prompt cases against a configured agent
and recording tool traces. Only the scoring/scorecard half exists; there is
no runner and no committed recorded transcripts, so `dicom-kb eval score`
has nothing real to gate on.

**Resolution strategy.**

1. Implement `eval/runner.py`: drive a configurable agent (an MCP client
   loop or a pluggable callable interface) through each prompt case against
   a built KB, recording tool calls, arguments, responses, and the final
   answer into the existing transcript JSON shape consumed by
   `dicom-kb eval score`.
2. Provide a **deterministic reference agent** for CI: a non-LLM scripted
   executor that follows the §9.1 routing order (exact lookup → traversal →
   text retrieval) for each case. This makes the runner testable offline
   and produces reproducible transcripts without API keys. A real-LLM
   runner config may be added behind an env-var-gated optional path, but
   must not be required by any test target.
3. Add `dicom-kb eval run --cases ... --db ... --out transcripts.json` CLI.
4. Recorded transcripts from a real KB run are **build outputs containing
   standard-derived facts**: do not commit them in bulk. Commit only small
   transcript fixtures over the synthetic fixture KB for offline scoring
   tests; real-KB transcript runs belong in the integration tier.
5. Wire an integration test: run the reference agent over all cases against
   the R1 KB, score the transcripts, assert the scorecard passes.

**Completion conditions.**

- [ ] `dicom-kb eval run` produces transcripts scoreable by
      `dicom-kb eval score` with exit code 0 on the reference agent.
- [ ] Offline test runs the reference agent against the synthetic fixture
      KB for a subset of cases and scores them.
- [ ] Integration test runs all ≥50 cases against the real KB via the
      reference agent and the scorecard passes (or failures are triaged to
      parser/query bugs and fixed).
- [ ] No bulk real-KB transcript committed.
- [ ] Offline gate passes.

---

### R5 — MCP protocol smoke test with a real client

**Priority:** Medium. Independent.

**Problem.** MCP coverage uses an in-process FastMCP double; nothing
verifies the served process speaks actual MCP over stdio to a real client.

**Resolution strategy.**

1. Add a test (offline-capable: it uses the synthetic fixture KB built via
   `dicom-kb build-fixture`) that launches `dicom-kb mcp serve` as a
   subprocess and connects with the official `mcp` Python client over stdio.
2. Exercise: `initialize`, `tools/list` (assert all nine `dicom_*` tools and
   their input schemas), and at least two `tools/call` invocations
   (`dicom_lookup_data_element`, `dicom_list_modules_for_iod`) asserting the
   response envelope parses and carries `edition`, `refs`, `warnings`.
3. Gate the test on the optional `mcp` extra being installed (skip with a
   clear message otherwise), consistent with existing optional-dependency
   handling. Place it in the offline suite if the fixture build is fast and
   hermetic; otherwise under a dedicated marker documented in the Makefile.
4. Fix `make run-mcp` ergonomics: if no KB exists at the conventional path,
   the command must fail with an actionable message naming the fetch/build
   commands, not a raw traceback. Add a unit test for that error path.

**Completion conditions.**

- [ ] A real MCP client completes initialize → list → call against a served
      subprocess using the synthetic fixture KB.
- [ ] All nine tools appear in `tools/list` with schemas.
- [ ] `dicom-kb mcp serve` without a KB prints an actionable error.
- [ ] Offline gate passes.

---

### R6 — Repository layout reconciliation with §6.2

**Priority:** Medium. Independent. Mostly mechanical.

**Problem.** Spec layout files are missing. Two kinds: (a) behavior exists
but lives elsewhere; (b) behavior genuinely missing.

**Resolution strategy.**

*(a) Refactor existing behavior into the spec layout — no behavior change:*

1. Split `query/resolver.py` internals into `query/graph.py` (traversal,
   macro expansion), `query/conditions.py` (condition payload assembly),
   `query/citations.py` (source-ref → public ref conversion),
   `query/search.py` (FTS query construction) with `resolver.py` retaining
   the public resolver entry points. Pure moves; public API unchanged.
2. Split `mcp/server.py` into `mcp/server.py` (serving/transport),
   `mcp/tools.py` (tool registration/mapping), `mcp/schemas.py` (tool
   argument schemas), preserving the public `dicom-kb mcp serve` behavior.
3. One commit per split (`refactor(query): ...`, `refactor(mcp): ...`);
   the unchanged 101-test suite passing is the no-behavior-change check.

*(b) Create genuinely missing pieces:*

4. `docbook/variablelists.py` (WO-C deliverable): parse DocBook
   `<variablelist>` into term/definition IR with source refs — needed later
   for enumerated values/defined terms (§7.6). Implement the parser plus a
   synthetic fixture test; storage wiring may wait for the value-constraint
   slice and should be noted as pending.
5. `examples/` with the spec's subdirectories (`python/`, `cli/`, `mcp/`,
   `coding_agent_harness/`, `validators/`): minimal runnable examples
   against the synthetic fixture KB, each with a README stating it targets
   the fixture KB and how to point it at a real local build.
6. `tests/fixtures_minimal_attributed/`: create the directory with a README
   defining the attribution policy (per §5.3: tiny excerpts, explicit
   attribution, only where synthetic fixtures cannot reproduce a parser
   behavior). It may start with the README only — do not add real excerpts
   until a specific parser behavior requires one (likely surfaced by R1
   triage).

**Completion conditions.**

- [ ] All §6.2 paths exist (excluding post-v1 `api/` and v2 parsers, which
      stay absent by design — note this in `IMPLEMENTATION_PROGRESS.md`).
- [ ] Refactors land with zero public API change and no test deletions.
- [ ] `variablelists.py` has offline synthetic-fixture coverage.
- [ ] Each `examples/` entry runs successfully against the fixture KB
      (verified by a smoke test or documented manual command).
- [ ] Offline gate passes.

---

### R7 — Differential testing against external parsers

**Priority:** Medium. Benefits from R1 (shares local artifacts/KB).

**Problem.** §4.2 and §15.1 require differential testing against Innolitics
dicom-standard and pydicom dicom-validator to find parser bugs. None exists.

**Resolution strategy.**

1. Create `tests/integration_requires_dicom_download/test_differential.py`
   (or a sibling directory if a different gate is warranted) that:
   - downloads/loads the Innolitics JSON (network) or reads a path from
     `DICOM_KB_INNOLITICS_PATH`; skips cleanly when unavailable;
   - compares, for the §15.2 golden set and a broad sample (e.g. all PS3.6
     elements), tag/keyword/VR/VM/retired flags and CT Image module lists
     against the local KB;
   - reports mismatches as structured output, classified per §12-v3
     language: parser issue / interpretation issue / edition skew.
2. External outputs are *signals, never truth* (§4.2): a mismatch fails the
   test only when triage shows a local parser bug; interpretation
   differences and edition skew are recorded as accepted-diff entries in a
   committed allowlist file with reasons.
3. Mind edition skew explicitly: Innolitics tracks its own pinned revision;
   the comparison must record both edition labels and tolerate
   added/removed entities between them.
4. Fix any confirmed parser bugs via the R1 pattern (synthetic repro +
   offline regression test).

**Completion conditions.**

- [ ] Differential comparison runs in the integration tier and skips
      cleanly without network/local data.
- [ ] PS3.6 element comparison shows zero unexplained mismatches (every
      mismatch fixed or allowlisted with a reason).
- [ ] CT Image module-list comparison shows zero unexplained mismatches.
- [ ] Offline gate passes.

---

## 4. Definition of done for this review

This review is fully resolved when:

1. All R1–R7 completion conditions are checked off.
2. `make test` passes offline on a clean checkout; `make test-integration`
   passes with fetched artifacts and skips cleanly without them.
3. `IMPLEMENTATION_PROGRESS.md` reflects each resolved item and lists any
   accepted limitations (xfails, allowlisted diffs, parked parser gaps).
4. The v1 acceptance criteria (§12) can each be mapped to a passing test or
   a documented, deliberate exclusion.
5. No commit in the resolution range adds official standard artifacts or
   bulk derived content.

Items may be resolved across multiple sessions. Agents should work the
dependency order in §1, record per-item progress in
`IMPLEMENTATION_PROGRESS.md`, and stop at a clean, committed boundary.
