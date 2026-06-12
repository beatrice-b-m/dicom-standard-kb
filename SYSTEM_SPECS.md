# dicom-standard-kb — System Specification

**Status:** pre-implementation. This document is the single authoritative
specification for coding agents implementing the system. Where it conflicts
with any earlier draft or discussion, this document wins.

---

## 1. Project identity

**dicom-standard-kb** is an open-source parser and query service for building
a local, edition-pinned knowledge base from the official DICOM standard. It
provides deterministic tools for coding agents, validators, and medical
imaging development workflows.

The defining design decision:

> This project is an open-source DICOM-standard **knowledge-base builder**,
> not an open-source **copy** of the DICOM standard knowledge base.

The public repository contains parser code, schemas, CLI, MCP/agent tooling,
a test harness, small fixtures, and documentation. The official standard
artifacts and the generated knowledge base are downloaded and built locally
by each user; they are never committed, packaged, or redistributed.

### 1.1 Non-affiliation and trademark notices

The following wording must appear in `README.md`, `NOTICE`, CLI startup
metadata, generated manifests, and the API `/about` endpoint:

> This project is not affiliated with, sponsored by, or endorsed by NEMA,
> MITA, or the DICOM Standards Committee.
> DICOM® is a registered trademark of the National Electrical Manufacturers
> Association (NEMA). The DICOM Standard is copyright owned by NEMA.
> Users should obtain the official current standard from dicomstandard.org.
> This project does not provide official DICOM conformance certification.

### 1.2 License

- Project code: **Apache License 2.0** (permissive, with explicit patent
  grant — appropriate for infrastructure used by companies, research labs,
  and device teams).
- The code license does **not** apply to the DICOM Standard text or to any
  locally generated knowledge base derived from it.

Required files:

```
LICENSE                  # Apache-2.0 for project code
NOTICE                   # DICOM/NEMA attribution and non-affiliation notice
THIRD_PARTY_NOTICES.md   # dependencies and external standard references
docs/legal.md            # practical redistribution notes
```

README must state:

> The Apache-2.0 license applies to this repository's original source code.
> It does not apply to the DICOM Standard or to third-party terminology
> content referenced by the DICOM Standard.

---

## 2. Assumptions and design principles

1. The system serves **coding agents and developer tooling** — not clinical
   diagnosis, regulatory certification, or official conformance
   certification.
2. The authoritative source corpus is the **official DICOM standard**, with
   every ingestion pinned to a concrete edition (e.g. `2026b`). The official
   "current" URL is mutable — DICOM is republished several times per year —
   so `current` must always be resolved to a concrete edition label before
   anything is stored.
3. The primary ingestion input is **DocBook XML**, not PDF scraping. The
   official release notes published with each edition state that DocBook XML
   is the source format, that the PDF remains the authoritative rendered
   form, that HTML/CHTML contain the same content, that paragraph anchors
   derive from DocBook `xml:id` values and are intended to remain stable
   across releases, and that several structures (enumerated values, defined
   terms, templates, context groups) are deliberately formatted to
   facilitate automated extraction.
4. The system exposes **deterministic tools**; LLMs are used only for
   routing, explanation, and synthesis.
5. Outputs are **citation-preserving, edition-aware, and machine-testable**.

The core principle:

> The model must not infer normative DICOM facts from memory. It must call
> tools that return parsed standard facts plus official references.

The DICOM standard specifies protocols, syntax/semantics, media services,
file formats, and conformance information, but does not specify
implementation details or a testing/validation procedure for assessing
conformance. This system therefore supports implementation and validation
workflows but never claims to certify DICOM conformance.

---

## 3. System purpose

A versioned, citation-preserving DICOM standard query engine for coding
agents, answering questions such as:

- What is the VR/VM for Modality?
- Which modules are required for the CT Image IOD?
- For this SOP Class UID, which IOD and modules apply?
- Is this transfer syntax retired?
- What attributes are Type 1C in this module?
- What is the condition for including this sequence?
- Where in the standard is this rule defined?
- What DICOMweb transaction defines this route?
- Which SR template or context group applies here?

---

## 4. Source hierarchy

### 4.1 Primary sources (in priority order)

1. **Official DocBook XML** — parsing, stable IDs, structured tables,
   cross-references, generated source references.
2. **Official PDF** — authoritative rendered form for conflicts or disputed
   interpretation.
3. **Official CHTML / HTML** — verifying anchors, generated links,
   human-readable references.
4. **Official DocBook target databases** — resolving cross-part `olink` and
   `xref` targets when available.

### 4.2 Secondary sources — differential testing only

Used to find parser bugs and compare outputs, never as source of truth:

- **Innolitics dicom-standard** (github.com/innolitics/dicom-standard) —
  parses the DICOM web standard into machine-friendly JSON; completely
  processes PS3.3, PS3.4, PS3.6 and references from several other parts.
- **pydicom dicom-validator** (github.com/pydicom/dicom-validator) — uses
  DocBook-format standard material to validate datasets against modules and
  attributes required by SOP Class.

The service must always be able to explain which official source artifact
produced each fact.

---

## 5. Distribution and artifact policy

### 5.1 Never vendor official artifacts

Do **not** commit, package, or release:

- any `*.xml` / `*.pdf` / `*.html` copied from official DICOM releases;
- bulk generated JSON of parsed standard content;
- bulk generated SQLite/PostgreSQL database dumps;
- full-text or vector indexes over the standard.

Instead the tool builds everything locally:

```
dicom-kb fetch --edition current      # resolves + downloads official artifacts
dicom-kb fetch --edition 2026b
dicom-kb build --edition 2026b        # parses into a local SQLite KB
dicom-kb serve --edition 2026b        # MCP (default) or HTTP surface
```

`fetch` downloads from official DICOM URLs, computes SHA-256 hashes, and
stores files in the local cache.

### 5.2 Local data layout

All downloaded artifacts and generated data live outside the repository, in
a configurable cache directory (default `~/.cache/dicom-standard-kb/`;
containerized default `/data/dicom-standard-kb/`):

```
~/.cache/dicom-standard-kb/
  artifacts/
    2026b/
      raw/
        source/          # DocBook XML
        html/
        pdf/
      manifest.json
      checksums.json
  db/
    2026b.sqlite
  indexes/
    2026b/
```

### 5.3 Repository fixtures

Tests commit only small, targeted fixtures:

- tiny **synthetic** DocBook tables authored for this project;
- tiny excerpts from DICOM with explicit attribution, only where needed to
  test specific parser behavior;
- generated expected outputs for a handful of well-known tags/UIDs.

Test groups:

```
make test                      # offline; no official artifacts required
make test-dicom-integration    # requires locally downloaded DICOM artifacts
make test-dicom-current        # optional networked test; resolves current
```

### 5.4 Packaging

- **PyPI**: publish `dicom-standard-kb` as code only — never with a built
  database.
- **Docker**: publish images containing only code and dependencies; users
  mount a data volume and run `fetch`/`build` themselves. Do not publish an
  image with the standard preloaded.
- **GitHub releases**: source tarballs, wheels, Docker images, parser test
  reports, schema versions, and small sample databases built from synthetic
  fixtures only.

### 5.5 Output excerpt policy

Default tool output returns structured facts plus official references, not
large copied text blocks. Local text retrieval is available behind an
explicit flag/parameter with a character cap
(e.g. `dicom-kb retrieve-text PS3.3 sect_A.3.3 --max-chars 800`).

A public hosted demo (if ever deployed) restricts to tag/UID lookup,
official-link generation, and short excerpts; it must not expose bulk
export endpoints (`/export/full-standard-json`, `/text/all`,
`/database/download`, `/vector-index/download`).

---

## 6. System architecture

### 6.1 Components

```
                  ┌────────────────────────────┐
                  │ Official DICOM Artifacts   │
                  │ XML / PDF / HTML / targetdb│
                  └──────────────┬─────────────┘
                                 │
                                 ▼
┌────────────────────────────────────────────────────────┐
│ Source Acquisition Layer                               │
│ - edition resolver                                     │
│ - downloader / local loader                            │
│ - checksum manifest                                    │
│ - artifact registry (local cache)                      │
└───────────────────────────────┬────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────┐
│ DocBook Parsing Layer                                  │
│ - section parser                                       │
│ - table parser (incl. Include-row recognition)         │
│ - variablelist parser                                  │
│ - xref / olink resolver                                │
│ - anchor extractor                                     │
│ - text chunker                                         │
└───────────────────────────────┬────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────┐
│ Canonical Intermediate Representation                  │
│ - documents, tables, entities, relationships,          │
│   macros, conditions, source refs                      │
└───────────────────────────────┬────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────┐
│ Storage Layer                                          │
│ - SQLite (primary; single-file local KB)               │
│ - PostgreSQL (optional service deployment)             │
│ - JSON source snapshots (raw table IR)                 │
│ - full-text search                                     │
│ - optional vector index for prose (v2+)                │
└───────────────────────────────┬────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────┐
│ Query and Reasoning Layer                              │
│ - exact lookup                                         │
│ - graph traversal (incl. macro expansion)              │
│ - effective-type computation                           │
│ - condition classification                             │
│ - text retrieval                                       │
│ - citation builder                                     │
└───────────────────────────────┬────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
 Python API                 CLI                     MCP Tools
        ▼                       ▼                       ▼
 Coding agents             Developers              Agent harnesses
                    (HTTP API: optional, post-v1)
```

### 6.2 Repository layout

```
dicom-standard-kb/
  LICENSE
  NOTICE
  README.md
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  SECURITY.md
  THIRD_PARTY_NOTICES.md
  pyproject.toml
  Dockerfile
  Makefile
  docs/
    overview.md
    legal.md
    public_distribution_policy.md
    quickstart.md
    agent_tools.md
    build_local_kb.md
    editions.md
    validation_scope.md
    architecture.md
    contributing_parser_fixtures.md
  src/dicom_kb/
    __init__.py
    sources/
      edition_resolver.py
      downloader.py
      manifest.py
      checksums.py
    docbook/
      namespaces.py
      parser.py
      tables.py
      variablelists.py
      xrefs.py
      targetdb.py
      text_chunks.py
    ir/
      models.py
      serializers.py
      validators.py
    parsers/
      part03_iods.py
      part04_sop_classes.py
      part06_data_dictionary.py
      part16_templates.py        # v2
      part18_web_services.py     # v2
    db/
      models.py
      migrations/
      importers.py
      repositories.py
    query/
      resolver.py
      graph.py
      conditions.py
      citations.py
      search.py
      answer_contracts.py
    api/                         # optional, post-v1
      app.py
      routes.py
      schemas.py
    cli/
      main.py
    mcp/
      server.py
      tools.py
      schemas.py
    eval/
      prompt_cases.py
      expected_tool_traces.py
      scoring.py
  schemas/
    tool_response.schema.json
    source_manifest.schema.json
    standard_ref.schema.json
    condition.schema.json
  tests/
    unit/
    fixtures_synthetic/
    fixtures_minimal_attributed/
    integration_requires_dicom_download/
    agent_regression/
  examples/
    python/
    cli/
    mcp/
    coding_agent_harness/
    validators/
```

`.gitignore` must exclude all local artifacts and generated data:
`artifacts/`, `*.sqlite*`, `*.db`, `*.duckdb`, `*.parquet`, downloaded
`part*.xml`/`part*.pdf`, `generated-standard-json/`,
`generated-standard-text/`, `vector-indexes/`, plus standard Python
exclusions.

### 6.3 Implementation stack

| Concern   | Choice |
|-----------|--------|
| Language  | Python 3.12+ |
| Packaging / env | `uv` (`uv sync`); `pyproject.toml` |
| Parsing   | `lxml` (primary), `pydantic` (IR models); `beautifulsoup4` only for HTML cross-checks |
| Database  | SQLite (primary, single-file local KB); PostgreSQL (optional deployment) — schema must be portable to both |
| CLI       | Typer |
| HTTP API (post-v1) | FastAPI + OpenAPI schema generation |
| Agent tooling | MCP server adapter; JSON Schema tool contracts |
| Search    | SQLite FTS5 for v1 (PostgreSQL full-text when deployed); optional vector index for prose in v2+ |
| Testing   | pytest, syrupy (snapshots), hypothesis (normalization/property tests) |
| Lint / types | ruff, mypy |

SQLite comes first because the primary user is an individual running coding
harnesses: a single-file generated database is easy to mount into
containers, commit nowhere, regenerate anytime, and hand to local agents.
The architecture is a Python core library with thin surfaces: CLI, MCP, and
(optionally, later) HTTP.

---

## 7. Canonical data model

All `*_id` columns ending in `condition_id` reference `condition(id)`. Every
fact-level table carries at least one `source_ref_id`.

### 7.1 Source and citation entities

```sql
standard_edition (
  id TEXT PRIMARY KEY,              -- e.g. "2026b"
  source_label TEXT NOT NULL,       -- e.g. "DICOM PS3 2026b"
  resolved_from TEXT,               -- "current" or explicit edition
  acquired_at TIMESTAMP NOT NULL,
  is_default BOOLEAN NOT NULL,
  manifest_sha256 TEXT NOT NULL
)

source_artifact (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL REFERENCES standard_edition(id),
  part TEXT NOT NULL,               -- "PS3.3"
  format TEXT NOT NULL,             -- "docbook_xml", "pdf", "html", "chtml", "targetdb"
  local_path TEXT NOT NULL,         -- path within the local cache
  source_url TEXT,
  sha256 TEXT NOT NULL,
  byte_size INTEGER,
  acquired_at TIMESTAMP NOT NULL
)

source_ref (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  part TEXT NOT NULL,
  chapter TEXT,
  section TEXT,
  table_id TEXT,
  figure_id TEXT,
  xml_id TEXT,
  anchor TEXT,
  title TEXT,
  source_artifact_id TEXT REFERENCES source_artifact(id),
  canonical_url TEXT,
  text_excerpt TEXT,
  excerpt_hash TEXT
)
```

### 7.2 Standard structure entities

```sql
doc_node (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  part TEXT NOT NULL,
  node_type TEXT NOT NULL,          -- book, chapter, section, table, figure, para, note
  parent_id TEXT,
  xml_id TEXT,
  anchor TEXT,
  number TEXT,
  title TEXT,
  ordinal INTEGER,
  plain_text TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id)
)

xref (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  source_node_id TEXT NOT NULL,
  target_ref TEXT NOT NULL,
  target_node_id TEXT,
  link_type TEXT NOT NULL,          -- xref, olink, link
  resolved BOOLEAN NOT NULL,
  resolution_warning TEXT
)
```

### 7.3 Dictionary and UID entities

```sql
data_element (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  tag TEXT NOT NULL,                -- "(0008,0060)" or range form "(60xx,0010)"
  group_pattern TEXT NOT NULL,      -- "0008" or "60xx"
  element_pattern TEXT NOT NULL,    -- "0060" or "xxxx"
  is_range BOOLEAN NOT NULL,        -- true when pattern contains 'x' placeholders
  name TEXT NOT NULL,
  keyword TEXT,                     -- nullable: some retired elements lack keywords
  vr TEXT,
  vm TEXT,
  retired BOOLEAN NOT NULL,
  retired_in_or_last_seen TEXT,
  source_ref_id TEXT NOT NULL,
  UNIQUE (edition_id, tag)
)

uid_registry_entry (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  uid_value TEXT NOT NULL,
  uid_name TEXT NOT NULL,
  uid_keyword TEXT,
  uid_type TEXT NOT NULL,           -- SOP Class, Transfer Syntax, etc.
  part TEXT,
  retired BOOLEAN NOT NULL,
  retired_in_or_last_seen TEXT,
  source_ref_id TEXT NOT NULL,
  UNIQUE (edition_id, uid_value)
)
```

**Tag normalization and range tags.** Hex digits are normalized to
uppercase; the PS3.6 range placeholder `x` is preserved lowercase (e.g.
`(60xx,3000)` overlay groups, `(50xx,xxxx)` retired curve data,
`(0020,31xx)`). `is_range` marks such rows. Concrete-tag lookups (e.g.
`(6002,3000)`) must match range rows by pattern: a lowercase `x` position
matches any hex digit. Exact (non-range) matches take precedence over
pattern matches when both exist. The uniqueness constraint is
`(edition_id, tag)` — keyword is excluded because it is nullable and NULL
semantics in unique constraints differ between SQLite and PostgreSQL.

### 7.4 IOD, module, macro, and attribute graph

```sql
iod (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  name TEXT NOT NULL,
  keyword TEXT,
  iod_type TEXT,                    -- composite, normalized, etc.
  part TEXT NOT NULL DEFAULT 'PS3.3',
  section TEXT,
  source_ref_id TEXT NOT NULL,
  UNIQUE (edition_id, name)
)

module (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  name TEXT NOT NULL,
  section TEXT,
  description TEXT,
  source_ref_id TEXT NOT NULL,
  UNIQUE (edition_id, name, section)
)

macro (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  name TEXT NOT NULL,               -- e.g. "General Anatomy Optional Macro"
  table_id TEXT,                    -- DocBook table id, e.g. "table_10-7"
  section TEXT,
  macro_kind TEXT,                  -- attribute_macro, functional_group_macro
  source_ref_id TEXT NOT NULL,
  UNIQUE (edition_id, table_id)
)

iod_module_use (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  iod_id TEXT NOT NULL REFERENCES iod(id),
  information_entity TEXT,
  module_id TEXT NOT NULL REFERENCES module(id),
  usage TEXT NOT NULL,              -- M, U, C
  usage_condition_text TEXT,
  condition_id TEXT REFERENCES condition(id),
  source_ref_id TEXT NOT NULL
)

iod_functional_group_use (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  iod_id TEXT NOT NULL REFERENCES iod(id),
  macro_id TEXT NOT NULL REFERENCES macro(id),
  usage TEXT NOT NULL,              -- M, U, C
  usage_condition_text TEXT,
  condition_id TEXT REFERENCES condition(id),
  source_ref_id TEXT NOT NULL
)

attribute_use (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  owner_type TEXT NOT NULL,         -- 'module' | 'macro'
  owner_id TEXT NOT NULL,           -- module.id or macro.id
  parent_attribute_use_id TEXT,     -- enclosing sequence attribute row
  row_kind TEXT NOT NULL,           -- 'attribute' | 'include'
  attribute_tag TEXT,               -- NULL for include rows
  attribute_keyword TEXT,
  attribute_name TEXT,              -- NULL for include rows
  type_designation TEXT,            -- 1, 1C, 2, 2C, 3 (attribute rows)
  description_text TEXT,
  condition_id TEXT REFERENCES condition(id),
  included_macro_id TEXT REFERENCES macro(id),  -- include rows, when resolved
  include_target_text TEXT,         -- raw include text when unresolved
  sequence_depth INTEGER NOT NULL DEFAULT 0,
  row_order INTEGER NOT NULL,
  source_ref_id TEXT NOT NULL
)
```

**Include rows and macros.** PS3.3 module and macro attribute tables contain
`Include Table 10-x "..."` rows; this is the standard's reuse mechanism and
it is pervasive even in basic modules. The parser must:

1. parse macro tables into `macro` + `attribute_use` rows
   (`owner_type='macro'`), structurally identical to module tables;
2. represent each include row as `row_kind='include'`, resolving
   `included_macro_id` by table reference where possible, preserving the
   raw text and emitting a warning where not;
3. **not** expand includes at parse time — expansion happens at query time
   in the graph layer, so every expanded attribute retains the provenance
   of both the including table and the macro definition.

Functional-group IODs (e.g. Enhanced CT) define applicable functional group
macros in a per-IOD table; these are captured in `iod_functional_group_use`
and traversed the same way.

The CT Image IOD module table (PS3.3 Table A.3-1) is a representative v1
fixture: it lists Information Entity, Module, Reference, and Usage columns
(Patient/M, General Study/M, Contrast/Bolus/C, CT Image/M, SOP Common/M,
etc.).

### 7.5 Service classes and SOP classes (PS3.4)

```sql
service_class (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  name TEXT NOT NULL,
  section TEXT,
  source_ref_id TEXT NOT NULL,
  UNIQUE (edition_id, name)
)

sop_class (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  name TEXT NOT NULL,
  uid_value TEXT NOT NULL,          -- joins to uid_registry_entry
  service_class_id TEXT REFERENCES service_class(id),
  source_ref_id TEXT NOT NULL,
  UNIQUE (edition_id, uid_value)
)

sop_class_iod (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  sop_class_id TEXT NOT NULL REFERENCES sop_class(id),
  iod_id TEXT NOT NULL REFERENCES iod(id),
  resolution TEXT NOT NULL,         -- 'parsed' | 'ambiguous'
  resolution_warning TEXT,
  source_ref_id TEXT NOT NULL
)
```

SOP Class → IOD relationships are recorded only where deterministically
extractable; ambiguous relationships are stored with
`resolution='ambiguous'` plus a warning, never guessed.

### 7.6 Value constraints

```sql
attribute_value_term (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  attribute_use_id TEXT REFERENCES attribute_use(id),
  data_element_id TEXT REFERENCES data_element(id),
  context_label TEXT,
  term_kind TEXT NOT NULL,          -- enumerated_value, defined_term
  value TEXT NOT NULL,
  meaning TEXT,
  source_ref_id TEXT NOT NULL
)
```

### 7.7 Conditions

```sql
condition (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  condition_kind TEXT,              -- required_if, required_unless, permitted_if, etc.
  raw_text TEXT NOT NULL,
  normalized_text TEXT,
  machine_status TEXT NOT NULL,     -- parsed, partially_parsed, raw_text, not_machine_decidable
  expression_json TEXT,             -- JSON (JSONB on PostgreSQL)
  source_ref_id TEXT NOT NULL
)
```

Conditions are facts, not model opinions. If the parser cannot produce a
reliable expression, it preserves the raw normative text and marks
`machine_status` accordingly. The full constraint representation (v3):

```json
{
  "condition_id": "cond.ps3.3.C.8.2.1.x",
  "source_text": "Required if ...",
  "condition_kind": "required_if",
  "machine_status": "parsed | partially_parsed | raw_text | not_machine_decidable",
  "dependencies": [
    {"tag": "(0018,9361)", "keyword": "MultiEnergyCTAcquisition"}
  ],
  "evaluator": {
    "available": true,
    "logic": "tag_equals",
    "expression": {"left": "MultiEnergyCTAcquisition", "op": "==", "right": "YES"}
  },
  "refs": []
}
```

A condition must not be marked `parsed` unless its evaluator can be tested
against synthetic metadata.

---

## 8. Public tool contract

All tool responses share a common envelope:

```json
{
  "edition": "2026b",
  "tool": "lookup_data_element",
  "input": {"tag_or_keyword": "Modality"},
  "status": "ok",
  "result": {},
  "refs": [],
  "warnings": [],
  "notice": "Consult the official DICOM Standard for authoritative text.",
  "trace": {
    "query_id": "uuid",
    "resolved_at": "2026-06-11T00:00:00Z",
    "source_manifest_sha256": "..."
  }
}
```

Universal rules:

- every response includes `edition`, `refs` (with official URLs where
  derivable), and `warnings`;
- unknown or ambiguous inputs return `candidates` or structured
  `not_found`/`validation_error` statuses — never fabricated data;
- structured facts by default; text excerpts only via explicit
  parameters with caps.

### 8.1 `lookup_data_element`

Request / response:

```json
{"tag_or_keyword": "(0008,0060)", "edition": "2026b"}
```

```json
{
  "edition": "2026b",
  "tool": "lookup_data_element",
  "status": "ok",
  "result": {
    "tag": "(0008,0060)",
    "name": "Modality",
    "keyword": "Modality",
    "vr": "CS",
    "vm": "1",
    "retired": false
  },
  "refs": [
    {
      "part": "PS3.6",
      "section": "Registry of DICOM Data Elements",
      "table": "Registry of DICOM Data Elements",
      "anchor": "...",
      "official_url": "https://dicom.nema.org/...",
      "edition": "2026b"
    }
  ],
  "warnings": []
}
```

Required tests:

- tag lookup and keyword lookup return the same entity;
- lowercase keyword resolves or returns a candidate;
- malformed tag returns a validation error;
- unknown tag returns `not_found`, never fabricated data;
- retired elements include `retired: true` and a source reference;
- a concrete tag matching a range row (e.g. `(6002,3000)`) resolves to the
  range entry with the match noted in `warnings` or result metadata.

### 8.2 `lookup_uid`

```json
{"uid_or_keyword": "1.2.840.10008.1.2.1", "edition": "2026b"}
```

```json
{
  "edition": "2026b",
  "tool": "lookup_uid",
  "status": "ok",
  "result": {
    "uid_value": "1.2.840.10008.1.2.1",
    "uid_name": "Explicit VR Little Endian",
    "uid_keyword": "ExplicitVRLittleEndian",
    "uid_type": "Transfer Syntax",
    "part": "PS3.5",
    "retired": false
  },
  "refs": []
}
```

### 8.3 `list_modules_for_iod`

```json
{"iod": "CT Image", "edition": "2026b"}
```

```json
{
  "edition": "2026b",
  "tool": "list_modules_for_iod",
  "status": "ok",
  "result": {
    "iod": {"name": "CT Image", "part": "PS3.3"},
    "modules": [
      {
        "information_entity": "Patient",
        "module": "Patient",
        "usage": "M",
        "condition": null
      },
      {
        "information_entity": "Image",
        "module": "Contrast/Bolus",
        "usage": "C",
        "condition": {
          "raw_text": "Required if contrast media was used in this image",
          "machine_status": "raw_text"
        }
      }
    ]
  },
  "refs": [],
  "warnings": []
}
```

### 8.4 `list_attributes_for_module`

Returns the attribute rows of a module (or macro), including include rows.
Callers choose expansion behavior:

- `expand_macros: false` (default) — rows as printed, include rows
  represented explicitly with the referenced macro identity;
- `expand_macros: true` — query-time expansion; each expanded attribute
  carries both the macro source ref and the including row's source ref, and
  reports its effective `sequence_depth`.

### 8.5 `resolve_attribute_context`

The most important v1 tool for coding agents.

```json
{
  "attribute": "Modality",
  "context": {"iod": "CT Image"},
  "edition": "2026b"
}
```

```json
{
  "edition": "2026b",
  "tool": "resolve_attribute_context",
  "status": "ok",
  "result": {
    "attribute": {
      "tag": "(0008,0060)",
      "name": "Modality",
      "keyword": "Modality",
      "vr": "CS",
      "vm": "1"
    },
    "uses": [
      {
        "iod": "CT Image",
        "module": "General Series",
        "type_designation": "1",
        "sequence_path": [],
        "via_macro": null,
        "condition": null
      }
    ],
    "effective_type": "1",
    "effective_type_explanation": "Single applicable use in resolved context."
  },
  "refs": [],
  "warnings": []
}
```

Required behavior: when the same attribute appears in multiple modules for
an IOD, the tool computes and explains the effective type. PS3.3 states that
when an attribute appears in more than one module for an IOD, the applicable
type is the lowest type value unless the attribute description explicitly
states otherwise. Resolution must traverse macro expansions
(`via_macro` records the path).

### 8.6 `retrieve_standard_text`

```json
{"part": "PS3.3", "section_or_anchor": "sect_A.3.3", "edition": "2026b"}
```

```json
{
  "edition": "2026b",
  "tool": "retrieve_standard_text",
  "status": "ok",
  "result": {
    "part": "PS3.3",
    "section": "A.3.3",
    "title": "CT Image IOD Module Table",
    "text_excerpt": "...",
    "tables": [{"table_id": "table_A.3-1", "title": "CT Image IOD Modules"}]
  },
  "refs": [],
  "warnings": []
}
```

Subject to the excerpt policy in §5.5 (explicit opt-in, char cap).

### 8.7 Full v1 tool list

```
lookup_data_element(tag_or_keyword)
lookup_uid(uid_or_keyword)
lookup_sop_class(uid_or_name_or_keyword)
lookup_iod(iod_name_or_id)
list_modules_for_iod(iod)
list_attributes_for_module(module, expand_macros?)
resolve_attribute_context(attribute, iod_or_sop_class)
retrieve_standard_text(part, section_or_anchor)
search_standard_text(query, part_filter?)
```

Later-version tools are listed in their roadmap sections (§12).

---

## 9. Query routing rules for coding agents

### 9.1 Routing order

1. **Exact identifier lookup** — tags, keywords, UIDs, SOP Class names, IOD
   names, module names, TID, CID, section IDs, anchors.
2. **Structured graph traversal** — SOP Class → IOD → modules (and
   functional groups) → attributes (through macro expansion) → PS3.6
   dictionary.
3. **Contextual value lookup** — enumerated values and defined terms only
   within the applicable module/IOD context where possible.
4. **Condition lookup** — raw condition text plus machine-checkability
   status.
5. **Text retrieval** — section-level retrieval for prose-only details.
6. **Answer synthesis** — the LLM may summarize tool results but must not
   add uncited normative claims.

### 9.2 Agent policy

- Never answer a normative DICOM question from model memory.
- Always call exact lookup tools before text search.
- Always preserve edition IDs in generated code comments and tests.
- Treat raw-text conditions as unresolved unless a condition evaluator
  exists.
- Do not silently convert defined terms into enumerated values.
- Do not claim DICOM conformance certification.
- When generating code, include tests derived from structured tool outputs.

---

## 10. Ingestion pipeline

### 10.1 Artifact manifest

Every ingestion run produces an immutable manifest in the local cache:

```json
{
  "edition": "2026b",
  "resolved_from": "current",
  "acquired_at": "2026-06-11T00:00:00Z",
  "artifacts": [
    {
      "part": "PS3.3",
      "format": "docbook_xml",
      "local_path": "artifacts/2026b/raw/source/docbook/part03/part03.xml",
      "source_url": "https://dicom.nema.org/...",
      "sha256": "...",
      "byte_size": 12345678
    }
  ],
  "parser_version": "dicom-kb-parser/1.0.0",
  "source_manifest_sha256": "..."
}
```

(`local_path` is relative to the cache root, §5.2.)

Every locally generated database embeds build metadata:

```json
{
  "edition": "2026b",
  "resolved_from": "current",
  "source_urls": [],
  "source_sha256": {},
  "built_at": "2026-06-11T00:00:00Z",
  "parser_version": "1.0.0",
  "schema_version": "1",
  "repository_commit": "..."
}
```

### 10.2 Parser normalization requirements

The parser must:

1. **Strip zero-width spaces** before interpreting keywords, UIDs, and tags
   — the official release notes explicitly warn that zero-width spaces may
   appear in long words such as PS3.6 keywords and UIDs and need filtering
   before literal use.
2. Preserve DocBook `xml:id` where present.
3. Preserve generated HTML anchors where available.
4. Normalize whitespace.
5. Normalize tags to `(GGGG,EEEE)` with uppercase hex, preserving lowercase
   `x` range placeholders per §7.3.
6. Normalize UID values as strings.
7. Preserve retired markers.
8. Preserve table captions.
9. Preserve row order.
10. Preserve unresolved cross-references as warnings, not data loss.

### 10.3 Table parser requirements

Support: DocBook namespace-aware parsing; `thead`/`tbody` separation; entry
spans; nested links; emphasis markers; inline xrefs; footnotes and notes;
sequence indentation (`>` markers); repeated headers; multiline cell
content; **recognition of `Include Table …` rows** as include rows rather
than attribute rows.

Every parsed table produces both:

1. a **raw table IR** (snapshot of the table as parsed), and
2. a **normalized domain entity representation**.

This allows parser bugs to be investigated without redownloading or
reparsing the original source.

---

## 11. Response safety and correctness policy

Every generated answer is classified:

```json
{
  "normativity": "normative | explanatory | derived | heuristic | unsupported",
  "evidence_level": "parsed_table | parsed_registry | parsed_cross_reference | retrieved_text | external_comparison",
  "machine_decidability": "decidable | partially_decidable | not_decidable | not_applicable"
}
```

Rules:

- `parsed_table` beats `retrieved_text` for structured facts;
- `parsed_registry` beats approximate string search for tags and UIDs;
- `retrieved_text` may explain but must not override structured parsed data
  without a warning;
- external projects may be used for differential testing but never as
  primary evidence;
- unsupported answers must state what could not be found.

---

## 12. Versioned roadmap

### v1 — Public parser and local core knowledge service

**Scope:** complete local build pipeline and edition-pinned query service
for the highest-value structured parts:

- PS3.3 Information Object Definitions
- PS3.4 Service Class Specifications
- PS3.6 Data Dictionary and UID Registry
- selected PS3.1 definitions needed for source labeling and terminology

PS3.3's module definition structure is well-suited: module tables enumerate
attribute name, tag, type designation, and definition, with tags indexing
into PS3.6. PS3.6 has explicit conventions for tag syntax, retired markers,
and table notes; its UID registry lists UID values, names, keywords, types,
and the relevant part.

**Public deliverables:** open-source parser; local fetch/build workflow;
local SQLite knowledge base; Python API; CLI; MCP server; offline synthetic
fixture tests; integration tests against locally downloaded official XML;
coding-agent documentation. **No prebuilt full DICOM database is
published.**

**Tools:** the list in §8.7. All v1 responses return normalized structured
facts, edition ID, source references, official section/table anchors when
available, parse confidence, and unresolved warnings.

**Exclusions:** full Type 1C/2C condition parsing; PS3.5 encoding behavior;
DICOMweb routes; SR templates and context groups; full DICOM object
validation; conformance statement generation. Conditions are stored as raw
normative text with `machine_status` set accordingly. HTTP API and
PostgreSQL deployment are optional post-v1 work, not v1 requirements.

**v1 acceptance criteria:**

1. The pipeline can fetch (or load locally) a pinned DICOM edition and
   produce a reproducible artifact manifest; `current` resolves to a
   concrete edition.
2. PS3.6 Data Element rows parse into normalized records (tag, name,
   keyword, VR, VM, retired status, source ref), including range-tag rows.
3. PS3.6 UID registry rows parse into normalized records (UID value, name,
   keyword, type, retired status, related part, source ref).
4. PS3.3 IOD module tables parse into graph records.
5. PS3.3 module **and macro** attribute tables parse into `attribute_use`
   records, with include rows resolved to macros (or preserved with
   warnings) and functional group usage captured for functional-group IODs.
6. PS3.4 SOP Classes link to IODs where deterministically extractable.
7. Every public query response includes edition, result, refs, warnings.
8. Unknown or ambiguous inputs return candidates or structured errors,
   never fabricated answers.
9. A golden test suite covers at least: CT Image IOD, MR Image IOD,
   Enhanced CT Image (exercising functional group macro resolution),
   Segmentation, Comprehensive SR basics, Encapsulated PDF, and several
   transfer syntax UID lookups.
10. The same functionality is exposed through Python API, CLI, and MCP.
11. The repository, PyPI package, and Docker image contain no bulk standard
    content.

**v1 success criterion:**

> A user can clone the public repository, run a documented build command
> that fetches the official standard locally, and then query an
> edition-pinned DICOM knowledge base through CLI, Python, or MCP tools —
> receiving deterministic structured data, edition metadata, and official
> citations without relying on model memory.

### v2 — Implementation semantics expansion

**Scope adds:** PS3.5 (Data Structures and Encoding), PS3.7 (selected),
PS3.8 (selected), PS3.10 (Media Storage and File Format), PS3.16 (Content
Mapping Resource), PS3.18 (Web Services).

**New tools:**

```
lookup_vr(vr)
lookup_transfer_syntax(uid_or_keyword)
explain_encoding_rule(topic)
lookup_dicomweb_transaction(name_or_route)
lookup_media_type(media_type_or_context)
lookup_sr_template(tid)
lookup_context_group(cid)
lookup_code_meaning(code_value, scheme?)
lookup_enumerated_values(attribute, context?)
lookup_defined_terms(attribute, context?)
```

**Extraction:** VR behavior; transfer syntax properties; file meta
information requirements; DICOMweb resources, methods, media types,
request/response rules; enumerated values and defined terms; SR templates;
context groups; coded concepts; template/context-group extensibility flags.
This is feasible because the official release notes identify DocBook
structures designed for automated extraction of exactly these.

**PS3.16 terminology caution:** DICOM incorporates external terminology
including SNOMED CT under a license agreement permitting a subset to be used
in DICOM and by implementers of DICOM-compliant products. Policy: parse
PS3.16 locally; expose local lookup tools; cite official DICOM source
locations; avoid publishing a standalone terminology dump; include explicit
third-party terminology notices.

**v2 acceptance criteria:**

1. Transfer syntax UID lookups return UID metadata plus encoding refs.
2. DICOMweb transaction lookups return route, method, resource type,
   request/response constraints, and standard references.
3. TID and CID lookups return structured rows and extensibility metadata.
4. Enumerated values and defined terms link to their attribute context.
5. Fallback text retrieval covers prose-only rules.
6. At least 100 coding-task regression prompts pass through deterministic
   tool calls before answer synthesis.

### v3 — Constraint reasoning and validation assistance

**Scope:** a formal constraint layer classifying DICOM requirements by
mechanical checkability (constraint model in §7.7).

**New tools:**

```
explain_condition(condition_id)
evaluate_condition(condition_id, dataset_metadata)
validate_dataset_structure(dicom_metadata_json, sop_class?)
explain_validation_failure(failure_id)
generate_required_attribute_plan(sop_class_or_iod)
compare_dataset_to_iod(dicom_metadata_json, iod)
```

**OSS constraints:** the rule engine is open source; the standard-derived
rule database is built locally; published examples use synthetic metadata;
real test DICOMs must be deidentified and license-compatible; no conformance
certification claims.

**v3 acceptance criteria:**

1. Type 1C/2C requirements classified machine-checkable vs not.
2. At least 200 condition fixtures across common IODs.
3. Dataset metadata validation identifies missing Type 1, Type 2, and
   mechanically resolvable Type 1C/2C attributes.
4. The system can explain why a rule was not evaluated.
5. Differential tests against pydicom dicom-validator on selected public
   sample files, mismatches triaged as parser issue, interpretation issue,
   or unsupported condition.
6. No validation result claims official conformance certification.

### v4 — Edition management, diffs, and operational hardening

Critical because the official `current` URL is mutable.

**New tools / commands:**

```
list_available_editions()
compare_editions(entity_ref, from_edition, to_edition)
explain_standard_change(entity_ref, from_edition, to_edition)
watch_current_edition()
generate_agent_context_bundle(task_description)
audit_answer(answer_id)
```

```
dicom-kb editions list-local
dicom-kb editions fetch-current
dicom-kb editions pin 2026b
dicom-kb editions compare 2026a 2026b --entity Modality
dicom-kb build --edition 2026b --reproducible
```

**Operational features:** scheduled ingestion of new editions; non-mutating
side-by-side imports; edition diff reports; CI gates before a new edition
becomes default; compatibility tests across prior parsed editions; query
audit logs; source artifact checksums; parse warning dashboards; rate
limits and caching; safe excerpt policies for any public-facing surface.

**v4 acceptance criteria:**

1. At least three editions load side-by-side.
2. Queries pin to a specific edition or use the deployment default.
3. Diffs report added, changed, retired, removed entities.
4. Current-edition ingestion never silently overwrites a pinned edition.
5. Coding agents can request compact task-specific context bundles.
6. All answer synthesis traces include tool calls, source refs, version IDs.

### v5 — Full corpus coverage and implementation playbooks

**Scope adds:** PS3.2 conformance statement requirements; PS3.11 media
storage application profiles; PS3.12 media formats; PS3.14 grayscale
display; PS3.15 security profiles; PS3.17 explanatory material; PS3.19
application hosting; PS3.20 CDA imaging reports; PS3.21 transformations;
PS3.22 real-time communication.

**New tools:**

```
generate_conformance_statement_outline(product_profile)
lookup_security_profile(profile_name)
lookup_application_hosting_interface(topic)
lookup_transformation_rule(source_representation, target_representation)
retrieve_explanatory_example(topic)
generate_implementation_checklist(task_type)
```

v5 is full-corpus operational maturity, not a prerequisite for useful
agentic coding support.

---

## 13. Implementation work orders

Work orders are ordered units of delivery for coding agents. Each must end
with passing tests and a granular commit (see `AGENTS.md`).

### Work order A — Repository and build system

Deliverables: Python 3.12 project managed with `uv`; `pyproject.toml`;
ruff / mypy / pytest configured; Dockerfile (code-only image); Makefile;
CI workflow; legal skeleton (LICENSE, NOTICE, THIRD_PARTY_NOTICES.md,
docs/legal.md, README legal block per §1).

Required commands:

```
make install          # uv sync
make lint             # ruff
make typecheck        # mypy
make test             # offline unit tests
make test-integration # requires local DICOM artifacts
make ingest-fixture
make run-mcp
make run-api          # once HTTP surface exists (post-v1)
```

Completion: clean checkout runs unit tests; CI runs lint, typecheck, tests;
no network access needed for default tests; no database server required
(SQLite only). PostgreSQL via docker-compose is deferred to the optional
deployment work (§14, step 14).

### Work order B — Source acquisition

Deliverables: `sources/edition_resolver.py`, `sources/downloader.py`,
`sources/manifest.py`, `sources/checksums.py`.

Behavior: load from local cache directory; optionally download current
official artifacts; resolve `current` to a concrete edition label; compute
SHA-256 checksums; write immutable manifest; never overwrite a pinned
edition unless `--force` is passed.

Tests: fixture manifest generation; checksum mismatch failure; repeated
ingestion idempotent; `current` alias resolves to a concrete edition in the
manifest.

### Work order C — DocBook parser core

Deliverables: `docbook/parser.py`, `docbook/tables.py`, `docbook/xrefs.py`,
`docbook/targetdb.py`, `docbook/text_chunks.py`.

Behavior: namespace-aware DocBook parsing; sections, titles, labels,
`xml:id` extraction; paragraphs with stable references; tables into raw
table IR; `Include Table …` row recognition; local xref resolution;
unresolved xrefs preserved with warnings; zero-width-space removal during
normalized-token extraction.

Tests: table with spans; nested xref in table cell; section with `xml:id`;
zero-width space in UID keyword; unresolved reference warning; include row
recognized and distinguished from attribute rows.

### Work order D — PS3.6 parser

Deliverable: `parsers/part06_data_dictionary.py`.

Entities: `data_element` (including range-tag rows), `uid_registry_entry`,
file meta elements, directory structuring elements (if parsed in v1).

Tests: known tag lookup fixtures; known UID lookup fixtures; retired item
detection; duplicate UID rejection; malformed row warning; range-tag rows
(`(60xx,3000)`-style) parsed with `is_range=true` and matchable by concrete
tags.

### Work order E — PS3.3 parser

Deliverable: `parsers/part03_iods.py`.

Entities: `iod`, `module`, `macro`, `iod_module_use`,
`iod_functional_group_use`, `attribute_use` (attribute and include rows),
raw conditions, sequence nesting, enumerated/defined-term placeholders.

Tests: CT Image IOD module table; required and conditional module usage;
module attribute table; macro attribute table; include row resolved to its
macro; functional group usage table for an Enhanced family IOD; nested
sequence attributes; Type 1/1C/2/2C/3 extraction; source ref on every
attribute use.

### Work order F — PS3.4 parser

Deliverable: `parsers/part04_sop_classes.py`.

Entities: `service_class`, `sop_class`, `sop_class_iod`, service-specific
overrides where extractable.

Tests: CT Image Storage SOP Class resolves to CT Image IOD; Segmentation
Storage resolves to Segmentation IOD; unsupported or ambiguous SOP
relationships create warnings; UID registry entries join to SOP Class
records.

### Work order G — Database import and migrations

Deliverables: `db/models.py`, `db/importers.py`, `db/repositories.py`,
`db/migrations/`.

Behavior: SQLite-first schema, portable to PostgreSQL; transactional import
of parsed IR; reject partial imports unless `--allow-partial`; import
summary; uniqueness constraints enforced; side-by-side editions supported.

Tests: rollback on failure; duplicate tag handling; duplicate UID handling;
edition isolation; `source_ref` foreign-key coverage.

### Work order H — Query engine

Deliverables: `query/resolver.py`, `query/graph.py`, `query/conditions.py`,
`query/citations.py`, `query/search.py`.

Behavior: exact lookup by tag (including range-pattern matching), keyword,
UID, name; fuzzy candidate suggestions for near misses; graph traversal
SOP Class → IOD → modules/functional groups → attributes with query-time
macro expansion preserving dual provenance; effective attribute type
computation; condition retrieval; citation generation; structured
`not_found` responses.

Tests: exact lookup; range-tag match; ambiguous lookup; graph traversal
including macro expansion; effective type; missing entity; citations.

### Work order I — CLI and MCP server (HTTP optional, post-v1)

Deliverables: `cli/main.py` (Typer), `mcp/server.py`; later, optionally
`api/app.py` (FastAPI).

CLI examples:

```
dicom-kb fetch --edition current
dicom-kb build --edition 2026b --backend sqlite
dicom-kb verify --edition 2026b
dicom-kb doctor
dicom-kb lookup tag Modality --edition 2026b
dicom-kb lookup uid 1.2.840.10008.1.2.1 --edition 2026b
dicom-kb iod modules "CT Image" --edition 2026b
dicom-kb module attributes "General Series" --edition 2026b
dicom-kb context attribute Modality --iod "CT Image" --edition 2026b
dicom-kb mcp serve --edition 2026b
```

MCP tools (prefix `dicom_`): `dicom_lookup_data_element`,
`dicom_lookup_uid`, `dicom_lookup_sop_class`, `dicom_lookup_iod`,
`dicom_list_modules_for_iod`, `dicom_list_attributes_for_module`,
`dicom_resolve_attribute_context`, `dicom_retrieve_standard_text`,
`dicom_search_standard_text`.

HTTP examples (when implemented):

```
GET  /v1/data-elements/Modality?edition=2026b
GET  /v1/uids/1.2.840.10008.1.2.1?edition=2026b
GET  /v1/iods/CT%20Image/modules?edition=2026b
POST /v1/resolve-attribute-context
GET  /about
```

Tests: CLI snapshot tests; MCP schema validation; error envelope
consistency; JSON output stability; (HTTP schema tests when implemented).

### Work order J — Agent evaluation harness

Deliverables: `eval/prompt_cases.py`, `eval/expected_tool_traces.py`,
`tests/agent_regression/`.

Behavior: run prompt cases against a configured agent; record tool traces;
validate required tools were called; validate answer references; detect
unsupported normative claims; emit scorecard.

Completion: at least 50 v1 prompt cases (100+ at v2); failure reports show
missing tool calls or citations; all eval fixtures edition-pinned.

---

## 14. Build sequence

Implement in this order:

1. Repository skeleton, license/NOTICE/legal docs, CI, test harness (WO-A).
2. Local artifact cache and manifest system (WO-B).
3. Synthetic DocBook fixtures + DocBook section/table parser core (WO-C).
4. Official-artifact fetch command (WO-B completion).
5. PS3.6 Data Element and UID registry parser (WO-D) — tag/UID lookup is
   the fastest useful win.
6. SQLite schema and import (WO-G).
7. CLI with `lookup tag` / `lookup uid` (WO-I, first slice).
8. PS3.3 IOD/module/macro parser (WO-E).
9. `list_modules_for_iod`, `list_attributes_for_module` (WO-H slice).
10. PS3.4 SOP Class parser and SOP Class → IOD traversal (WO-F).
11. `resolve_attribute_context` with macro expansion and effective type
    (WO-H completion).
12. MCP server (WO-I completion).
13. Agent regression harness (WO-J); documentation and example workflows.
14. **Optional / post-v1:** FastAPI HTTP surface, PostgreSQL backend and
    docker-compose deployment.
15. v2 expansion: PS3.5, PS3.16, PS3.18.

---

## 15. Testing strategy

### 15.1 Test layers

| Layer | Coverage |
|-------|----------|
| Unit | parser primitives, tag/UID normalization (incl. range tags, zero-width spaces), table handling |
| Parser integration | PS3.3, PS3.4, PS3.6 extraction against pinned local artifacts |
| Database | import, uniqueness, referential integrity, migration stability |
| Query | exact lookup, graph traversal, macro expansion, condition retrieval, citation generation |
| Agent | prompt → tool trace → answer contract |
| Differential | selected outputs vs Innolitics dicom-standard and pydicom dicom-validator |
| Edition | multiple editions side-by-side, source hash stability, diff behavior |

### 15.2 Golden fixtures (v1)

```
Data Elements
  Modality, SOPClassUID, SOPInstanceUID, PixelData, TransferSyntaxUID,
  PatientName, StudyInstanceUID, SeriesInstanceUID
UIDs
  Verification SOP Class, CT Image Storage, MR Image Storage,
  Segmentation Storage, Explicit VR Little Endian,
  Implicit VR Little Endian, Deflated Explicit VR Little Endian,
  Explicit VR Big Endian (retired case)
IODs
  CT Image, MR Image, Enhanced CT Image (functional group macro
  resolution), Segmentation, Comprehensive SR, Encapsulated PDF
Modules
  Patient, General Study, General Series, Image Pixel, SOP Common,
  CT Image, Contrast/Bolus
Macros
  at least one attribute macro included by a v1 module, and one
  functional group macro used by Enhanced CT
```

### 15.3 Agent regression case format

```json
{
  "id": "agent.ct.required_modules",
  "prompt": "List the required modules for CT Image IOD and cite the standard.",
  "expected_tools": ["lookup_iod", "list_modules_for_iod"],
  "must_include": ["edition", "module usage", "source references"],
  "must_not_include": [
    "uncited normative claims",
    "official conformance certification"
  ]
}
```

### 15.4 Acceptance gates

A release cannot pass unless:

- all generated entities have edition IDs;
- all public query responses contain source refs or structured `not_found`
  errors;
- parser warnings are counted and reported;
- no generated fixture is manually edited without source trace;
- every agent regression answer is produced from tool output;
- all default tests pass offline using committed fixtures;
- online/integration ingestion tests are separated behind explicit targets;
- all database migrations are reversible or accompanied by migration
  fixtures.

---

## 16. Operational metrics and quality gates

Emit after every ingestion:

```json
{
  "edition": "2026b",
  "parts_loaded": ["PS3.3", "PS3.4", "PS3.6"],
  "data_elements": 0,
  "uids": 0,
  "iods": 0,
  "modules": 0,
  "macros": 0,
  "iod_module_uses": 0,
  "iod_functional_group_uses": 0,
  "attribute_uses": 0,
  "include_rows_resolved": 0,
  "include_rows_unresolved": 0,
  "sop_classes": 0,
  "conditions": 0,
  "xrefs_total": 0,
  "xrefs_unresolved": 0,
  "parse_warnings": 0,
  "source_refs": 0
}
```

Quality gates fail when:

- source refs are missing for parsed entities;
- xref or include-row unresolved rate exceeds configured threshold;
- data element or UID counts change unexpectedly between parser versions
  without an edition change;
- parser warnings increase above baseline;
- golden outputs change without explicit approval.

---

## 17. Configuration profiles

Personal/local full service:

```yaml
dicom_kb:
  edition: "current-resolved"
  artifact_dir: "~/.cache/dicom-standard-kb/artifacts"
  database_url: "sqlite:///~/.cache/dicom-standard-kb/db/current.sqlite"
  allow_text_retrieval: true
  max_text_excerpt_chars: 1200
  require_citations: true
  require_edition_pin: true
  allow_network_fetch: false
```

Public CI:

```yaml
dicom_kb:
  allow_text_retrieval: false
  use_synthetic_fixtures_only: true
  require_dicom_download_for_integration: true
  publish_generated_db: false
```

---

## 18. Example coding-agent workflow

A coding agent asked to generate a validator for CT Image Storage:

1. `dicom_lookup_sop_class("CT Image Storage")`
2. `dicom_lookup_iod("CT Image")`
3. `dicom_list_modules_for_iod("CT Image")`
4. for each required/conditional module:
   `dicom_list_attributes_for_module(module, expand_macros=true)`
5. for each attribute: `dicom_lookup_data_element(tag)`
6. for each Type 1C/2C: `dicom_explain_condition(condition_id)` (v3)
7. generate code from structured facts
8. generate tests using golden expected attributes
9. include edition ID and source refs in generated test metadata

Generated code carries provenance:

```json
{
  "generated_from": {
    "service": "dicom-standard-kb",
    "edition": "2026b",
    "source_manifest_sha256": "...",
    "tool_trace_id": "..."
  }
}
```

---

## 19. Risks and mitigations

**Edition drift.** DICOM is republished several times per year; the
`current` URL always resolves to the newest edition. Mitigation: never
store only "current"; always resolve to a concrete edition; pin generated
code and tests to edition; import new editions side-by-side; require
regression tests before changing the default edition.

**False precision.** Some DICOM rules depend on clinical context,
acquisition context, other objects, negotiated behavior, or implementation
role. Mitigation: classify conditions by machine decidability; preserve raw
normative text; expose unresolved warnings; never claim conformance
certification.

**Parser brittleness.** DocBook tables contain spans, nested references,
footnotes, formatting artifacts, include rows, and unusual indentation.
Mitigation: store raw table IR alongside normalized entities; snapshot
parsed tables; test known difficult sections (macro-heavy Enhanced IODs in
particular); compare selected outputs with external tools; count parser
warnings.

**Copyright and redistribution.** The DICOM publication is free to download
and use, and the official IP guidance states no license is required to
download or implement it — but the publications are NEMA copyright, and
reproduction requests go through the DICOM Secretariat. Mitigation: the
builder-not-mirror posture of §1 and §5 — local artifacts only, concise
excerpts, structured facts plus official links, legal review before any
bulk public exposure.

**Model hallucination.** A coding agent may answer directly instead of
using tools. Mitigation: enforce the tool-first agent policy (§9.2);
evaluate prompt traces; fail answers with uncited normative claims; keep
tool responses compact enough that agents prefer them.

---

## 20. References

- Official DICOM standard portal: https://www.dicomstandard.org/current
- Official artifact host (current edition, all formats):
  https://dicom.nema.org/medical/dicom/current/
- Release notes published with each edition (DocBook source format, anchor
  stability, zero-width-space caveat, extraction-friendly structures):
  distributed alongside each edition at the artifact host above.
- Innolitics dicom-standard (differential testing only):
  https://github.com/innolitics/dicom-standard
- pydicom dicom-validator (differential testing only):
  https://github.com/pydicom/dicom-validator

Claims in this specification attributed to "the official release notes" or
the DICOM IP/relations pages should be re-verified against the pinned
edition during Work order B, and the verified URLs recorded in
`THIRD_PARTY_NOTICES.md` and `docs/legal.md`.
