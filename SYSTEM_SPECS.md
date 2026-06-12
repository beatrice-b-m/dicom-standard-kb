I do not see a blocking ambiguity, so I’ll formalize this using a concrete set of assumptions. The only decision I would confirm before coding is whether the system is internal-only or intended for public/commercial redistribution, because that affects how much standard text the service should store and expose.

DICOM Standard Knowledge Service: system specification and implementation plan

0. Assumptions

This specification assumes:

1. The system is for coding agents and developer tooling, not for clinical diagnosis, regulatory certification, or official conformance certification.
2. The authoritative source corpus is the official DICOM standard, with each ingestion pinned to a concrete edition such as 2026b.
3. The primary ingestion input is DocBook XML, not PDF scraping. The official current edition page publishes DICOM parts in multiple formats including XML, and states that XML is useful for machine readability and self-updating validators; it also says the “current” path is republished several times per year.  ￼
4. The generated system should expose deterministic tools to coding agents, with LLMs used only for routing, explanation, and synthesis.
5. Outputs must be citation-preserving, edition-aware, and machine-testable.

The official release notes are especially useful for this design: they state that DocBook XML is the source format, that the PDF remains the authoritative form, that HTML/CHTML contain the same content in a browser-friendly form, and that paragraph anchors are derived from DocBook xml:id values and intended to remain stable across releases. The same release notes also mention automated-extraction-friendly structures for enumerated values, defined terms, templates, and context groups.  ￼

⸻

1. System purpose

The system should be a versioned, citation-preserving DICOM standard query engine for coding agents.

Its job is to answer questions such as:

What is the VR/VM for Modality?
Which modules are required for CT Image IOD?
For this SOP Class UID, which IOD and modules apply?
Is this transfer syntax retired?
What attributes are Type 1C in this module?
What is the condition for including this sequence?
Where in the standard is this rule defined?
What DICOMweb transaction defines this route?
Which SR template or context group applies here?

The core design principle is:

The model should not infer normative DICOM facts from memory. It should call tools that return parsed standard facts plus official references.

The DICOM standard itself says it specifies protocols, syntax/semantics, media services, file formats, and conformance information, but does not specify implementation details or a testing/validation procedure for assessing conformance. That means this system should support implementation and validation workflows, but it should not claim to certify DICOM conformance.  ￼

⸻

2. Source hierarchy

2.1 Primary sources

The system must ingest official DICOM standard source artifacts.

Priority order:

1. Official DocBook XML
    Used for parsing, stable IDs, structured tables, cross-references, and generated source references.
2. Official PDF
    Treated as the authoritative rendered form when there is a conflict or a disputed interpretation.
3. Official CHTML / HTML
    Used to verify anchors, generated links, and human-readable references.
4. Official DocBook target databases
    Used for resolving cross-part olink and xref targets when available.

2.2 Secondary sources for differential testing only

These may be used to find parser bugs or compare outputs, but not as the source of truth:

* Innolitics dicom-standard, which parses the DICOM web standard into machine-friendly JSON and models relationships between IODs, modules, attributes, and cross-referenced sections. It currently states that it completely processes PS3.3, PS3.4, and PS3.6, and processes references from several other parts.  ￼
* pydicom dicom-validator, which uses DocBook-format DICOM standard material to validate datasets against modules and attributes required by the SOP Class.  ￼

The generated service must always be able to explain which official source artifact produced each fact.

⸻

3. Product versions

v1 — Core edition-pinned reference service

Goal

v1 provides a complete, bounded, edition-pinned query service for the highest-value structured parts of the standard:

* PS3.3: Information Object Definitions
* PS3.4: Service Class Specifications
* PS3.6: Data Dictionary and UID Registry
* selected PS3.1 definitions needed for source labeling and terminology

Part 3’s module definition structure is highly suitable for this: module tables enumerate attributes and include attribute name, tag, type designation, and attribute definition, and tags index into Part 6.  ￼ Part 6 also has explicit conventions for tag syntax, retired markers, and table notes, and its UID registry lists UID values, names, keywords, UID types, and the relevant DICOM part.  ￼

Required v1 capabilities

v1 must support:

lookup_data_element(tag_or_keyword)
lookup_uid(uid_or_keyword)
lookup_sop_class(uid_or_name_or_keyword)
lookup_iod(iod_name_or_id)
list_modules_for_iod(iod)
list_attributes_for_module(module)
resolve_attribute_context(attribute, iod_or_sop_class)
retrieve_standard_text(part, section_or_anchor)
search_standard_text(query, part_filter?)

v1 must return:

* normalized structured facts;
* edition ID;
* source references;
* official section/table anchors when available;
* parse confidence;
* unresolved warnings when extraction is incomplete.

v1 exclusions

v1 should not attempt to fully solve:

* all Type 1C / 2C conditions;
* all Part 5 encoding behavior;
* all DICOMweb routes;
* all SR templates and context groups;
* full DICOM object validation;
* conformance statement generation.

Conditions may be stored as raw normative text with a machine_status such as raw_text, partially_parsed, or not_machine_decidable.

v1 acceptance criteria

v1 is complete when:

1. The ingestion pipeline can download or load a pinned DICOM edition and produce a reproducible artifact manifest.
2. PS3.6 Data Element rows are parsed into normalized records with tag, name, keyword, VR, VM, retired status, and source reference.
3. PS3.6 UID registry rows are parsed into normalized records with UID value, name, keyword, UID type, retired status, related part, and source reference.
4. PS3.3 IOD/module tables are parsed into graph records.
5. PS3.3 module attribute tables are parsed into attribute-use records.
6. PS3.4 SOP Classes are linked to IODs where the relationship can be extracted deterministically.
7. Every public query response includes edition, result, refs, and warnings.
8. Unknown or ambiguous inputs return candidates or structured errors, never fabricated answers.
9. A golden test suite covers at least CT Image IOD, MR Image IOD, Enhanced CT, Segmentation Storage, Structured Report basics, Encapsulated PDF, and several transfer syntax UID lookups.
10. The service exposes the same functionality through Python API, CLI, HTTP API, and agent tool interface.

⸻

v2 — Encoding, values, DICOMweb, and content mapping expansion

Goal

v2 expands the system from core object structure into implementation semantics.

Covered parts:

* PS3.5: Data Structures and Encoding
* PS3.7: Message Exchange, selected
* PS3.8: Network Communication, selected
* PS3.10: Media Storage and File Format
* PS3.16: Content Mapping Resource
* PS3.18: Web Services

Required v2 capabilities

Add tools:

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

Required v2 extraction features

v2 must parse or index:

* VR behavior;
* transfer syntax properties;
* file meta information requirements;
* DICOMweb resources, HTTP methods, media types, request/response rules;
* enumerated values and defined terms;
* SR templates;
* context groups;
* coded concepts;
* template and context group extensibility flags.

This is feasible because the official release notes explicitly identify DocBook structures meant to facilitate automated extraction of enumerated values, defined terms, templates, and context groups.  ￼

v2 acceptance criteria

v2 is complete when:

1. Transfer syntax UID lookups return UID metadata plus encoding-related references.
2. DICOMweb transaction lookups return route, method, resource type, request constraints, response constraints, and standard references.
3. TID and CID lookups return structured rows and extensibility metadata.
4. Enumerated values and defined terms are linked to the attribute context in which they apply.
5. Fallback text retrieval is available for rules that are prose-only.
6. At least 100 coding-task regression prompts pass through deterministic tool calls before answer synthesis.

⸻

v3 — Constraint reasoning and validation assistance

Goal

v3 introduces a formal constraint layer that can classify DICOM requirements by how mechanically checkable they are.

Required v3 capabilities

Add tools:

explain_condition(condition_id)
evaluate_condition(condition_id, dataset_metadata)
validate_dataset_structure(dicom_metadata_json, sop_class?)
explain_validation_failure(failure_id)
generate_required_attribute_plan(sop_class_or_iod)
compare_dataset_to_iod(dicom_metadata_json, iod)

Constraint model

Every condition should be represented as:

{
  "condition_id": "cond.ps3.3.C.8.2.1.x",
  "source_text": "Required if ...",
  "condition_kind": "required_if",
  "machine_status": "parsed | partially_parsed | raw_text | not_machine_decidable",
  "dependencies": [
    {
      "tag": "(0018,9361)",
      "keyword": "MultiEnergyCTAcquisition"
    }
  ],
  "evaluator": {
    "available": true,
    "logic": "tag_equals",
    "expression": {
      "left": "MultiEnergyCTAcquisition",
      "op": "==",
      "right": "YES"
    }
  },
  "refs": []
}

A condition must not be marked parsed unless the evaluator can be tested against synthetic metadata.

v3 acceptance criteria

v3 is complete when:

1. Type 1C and 2C requirements are classified into machine-checkable and non-machine-checkable categories.
2. At least 200 condition fixtures exist across common IODs.
3. Dataset metadata validation can identify missing Type 1, Type 2, and mechanically resolvable Type 1C/2C attributes.
4. The system can explain why a rule was not evaluated.
5. Differential tests compare outputs against pydicom dicom-validator for selected public sample files, with mismatches triaged as parser issue, interpretation issue, or unsupported condition.
6. No validation result claims official conformance certification.

⸻

v4 — Edition diffs, operational hardening, and agent integration

Goal

v4 makes the system suitable for long-running automated use by coding harnesses across DICOM editions.

Required v4 capabilities

Add tools:

list_available_editions()
compare_editions(entity_ref, from_edition, to_edition)
explain_standard_change(entity_ref, from_edition, to_edition)
watch_current_edition()
generate_agent_context_bundle(task_description)
audit_answer(answer_id)

Required v4 operational features

v4 must include:

* scheduled ingestion of new official editions;
* non-mutating import of new editions;
* edition diff reports;
* CI gates before a new edition becomes default;
* compatibility tests across prior parsed editions;
* query audit logs;
* source artifact checksums;
* parse warning dashboards;
* rate limits and caching;
* safe excerpt policies for public-facing use.

v4 acceptance criteria

v4 is complete when:

1. At least three DICOM editions can be loaded side-by-side.
2. A query can be pinned to a specific edition or use the deployment default.
3. Standard diffs can report added, changed, retired, or removed entities.
4. Current-edition ingestion never silently overwrites a pinned edition.
5. Coding agents can request compact task-specific context bundles.
6. All answer synthesis traces include tool calls, source references, and version IDs.

⸻

v5 — Full corpus coverage and implementation playbooks

Goal

v5 extends coverage to all active DICOM parts and adds curated implementation guidance.

Covered areas include:

* PS3.2 conformance statement requirements;
* PS3.11 media storage application profiles;
* PS3.12 media formats;
* PS3.14 grayscale display;
* PS3.15 security profiles;
* PS3.17 explanatory material;
* PS3.19 application hosting;
* PS3.20 CDA imaging reports;
* PS3.21 transformations;
* PS3.22 real-time communication.

Required v5 capabilities

Add tools:

generate_conformance_statement_outline(product_profile)
lookup_security_profile(profile_name)
lookup_application_hosting_interface(topic)
lookup_transformation_rule(source_representation, target_representation)
retrieve_explanatory_example(topic)
generate_implementation_checklist(task_type)

v5 should be viewed as full-corpus operational maturity, not as a prerequisite for useful agentic coding support.

⸻

4. System architecture

4.1 Components

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
│ - artifact registry                                    │
└───────────────────────────────┬────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────┐
│ DocBook Parsing Layer                                  │
│ - section parser                                       │
│ - table parser                                         │
│ - variablelist parser                                  │
│ - xref / olink resolver                                │
│ - anchor extractor                                     │
│ - text chunker                                         │
└───────────────────────────────┬────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────┐
│ Canonical Intermediate Representation                  │
│ - documents                                            │
│ - tables                                               │
│ - entities                                             │
│ - relationships                                        │
│ - conditions                                           │
│ - source refs                                          │
└───────────────────────────────┬────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────┐
│ Storage Layer                                          │
│ - PostgreSQL / SQLite                                  │
│ - JSONB source snapshots                               │
│ - full-text search                                     │
│ - optional vector index for prose                      │
└───────────────────────────────┬────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────┐
│ Query and Reasoning Layer                              │
│ - exact lookup                                         │
│ - graph traversal                                      │
│ - condition classification                             │
│ - text retrieval                                       │
│ - citation builder                                     │
└───────────────────────────────┬────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
 Python API                  HTTP API                MCP Tools
        ▼                       ▼                       ▼
 Coding agents             Apps / services          Agent harnesses

4.2 Repository layout

dicom-standard-kb/
  pyproject.toml
  README.md
  LICENSE
  Makefile
  docker-compose.yml
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
      part16_templates.py
      part18_web_services.py
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
    api/
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
    standard_ref.schema.json
    tool_response.schema.json
    condition.schema.json
  tests/
    unit/
    integration/
    golden/
    fixtures/
    agent_regression/
  artifacts/
    raw/
    parsed/
    manifests/

⸻

5. Canonical data model

5.1 Source and citation entities

standard_edition

standard_edition (
  id TEXT PRIMARY KEY,              -- e.g. "2026b"
  source_label TEXT NOT NULL,       -- e.g. "DICOM PS3 2026b"
  resolved_from TEXT,               -- "current" or explicit edition
  acquired_at TIMESTAMP NOT NULL,
  is_default BOOLEAN NOT NULL,
  manifest_sha256 TEXT NOT NULL
)

source_artifact

source_artifact (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL REFERENCES standard_edition(id),
  part TEXT NOT NULL,               -- "PS3.3"
  format TEXT NOT NULL,             -- "docbook_xml", "pdf", "html", "chtml", "targetdb"
  local_path TEXT NOT NULL,
  source_url TEXT,
  sha256 TEXT NOT NULL,
  byte_size INTEGER,
  acquired_at TIMESTAMP NOT NULL
)

source_ref

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

Every fact-level table should have at least one source_ref_id.

⸻

5.2 Standard structure entities

doc_node

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

xref

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

⸻

5.3 Dictionary and UID entities

data_element

data_element (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  tag TEXT NOT NULL,                -- "(0008,0060)"
  group_hex TEXT NOT NULL,
  element_hex TEXT NOT NULL,
  name TEXT NOT NULL,
  keyword TEXT,
  vr TEXT,
  vm TEXT,
  retired BOOLEAN NOT NULL,
  retired_in_or_last_seen TEXT,
  source_ref_id TEXT NOT NULL,
  UNIQUE (edition_id, tag, keyword)
)

uid_registry_entry

uid_registry_entry (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  uid_value TEXT NOT NULL,
  uid_name TEXT NOT NULL,
  uid_keyword TEXT,
  uid_type TEXT NOT NULL,           -- SOP Class, Transfer Syntax, Well-known Frame of Reference, etc.
  part TEXT,
  retired BOOLEAN NOT NULL,
  retired_in_or_last_seen TEXT,
  source_ref_id TEXT NOT NULL,
  UNIQUE (edition_id, uid_value)
)

⸻

5.4 IOD, module, and attribute graph

iod

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

module

module (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  name TEXT NOT NULL,
  section TEXT,
  description TEXT,
  source_ref_id TEXT NOT NULL,
  UNIQUE (edition_id, name, section)
)

iod_module_use

iod_module_use (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  iod_id TEXT NOT NULL REFERENCES iod(id),
  information_entity TEXT,
  module_id TEXT NOT NULL REFERENCES module(id),
  usage TEXT NOT NULL,              -- M, U, C
  usage_condition_text TEXT,
  condition_id TEXT,
  source_ref_id TEXT NOT NULL
)

The CT Image IOD table is a representative v1 fixture: it lists Information Entity, Module, Reference, and Usage columns, with entries such as Patient / Patient / M, General Study / M, Contrast/Bolus / conditional, CT Image / M, and SOP Common / M.  ￼

module_attribute_use

module_attribute_use (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  module_id TEXT NOT NULL REFERENCES module(id),
  parent_attribute_use_id TEXT,
  attribute_tag TEXT,
  attribute_keyword TEXT,
  attribute_name TEXT NOT NULL,
  type_designation TEXT,            -- 1, 1C, 2, 2C, 3
  description_text TEXT,
  condition_id TEXT,
  sequence_depth INTEGER NOT NULL DEFAULT 0,
  row_order INTEGER NOT NULL,
  source_ref_id TEXT NOT NULL
)

⸻

5.5 Value constraints

attribute_value_term

attribute_value_term (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  attribute_use_id TEXT REFERENCES module_attribute_use(id),
  data_element_id TEXT REFERENCES data_element(id),
  context_label TEXT,
  term_kind TEXT NOT NULL,          -- enumerated_value, defined_term
  value TEXT NOT NULL,
  meaning TEXT,
  source_ref_id TEXT NOT NULL
)

⸻

5.6 Conditions

condition

condition (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  condition_kind TEXT,              -- required_if, required_unless, permitted_if, etc.
  raw_text TEXT NOT NULL,
  normalized_text TEXT,
  machine_status TEXT NOT NULL,     -- parsed, partially_parsed, raw_text, not_machine_decidable
  expression_json JSONB,
  source_ref_id TEXT NOT NULL
)

Conditions are facts, not model opinions. If the parser cannot produce a reliable expression, it should preserve the raw normative text and mark the machine status accordingly.

⸻

6. Public tool contract

All tool responses should share a common envelope.

{
  "edition": "2026b",
  "tool": "lookup_data_element",
  "input": {
    "tag_or_keyword": "Modality"
  },
  "status": "ok",
  "result": {},
  "refs": [],
  "warnings": [],
  "trace": {
    "query_id": "uuid",
    "resolved_at": "2026-06-11T00:00:00Z",
    "source_manifest_sha256": "..."
  }
}

6.1 lookup_data_element

Request

{
  "tag_or_keyword": "(0008,0060)",
  "edition": "2026b"
}

Response

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
      "edition": "2026b"
    }
  ],
  "warnings": []
}

Required tests

- tag lookup and keyword lookup return the same entity.
- lowercase keyword resolves or returns candidate.
- malformed tag returns validation error.
- unknown tag returns not_found, not fabricated data.
- retired elements include retired=true and source reference.

⸻

6.2 lookup_uid

Request

{
  "uid_or_keyword": "1.2.840.10008.1.2.1",
  "edition": "2026b"
}

Response

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

⸻

6.3 list_modules_for_iod

Request

{
  "iod": "CT Image",
  "edition": "2026b"
}

Response

{
  "edition": "2026b",
  "tool": "list_modules_for_iod",
  "status": "ok",
  "result": {
    "iod": {
      "name": "CT Image",
      "part": "PS3.3"
    },
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

⸻

6.4 resolve_attribute_context

This is the most important v1 tool for coding agents.

Request

{
  "attribute": "Modality",
  "context": {
    "iod": "CT Image"
  },
  "edition": "2026b"
}

Response

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
        "condition": null
      }
    ],
    "effective_type": "1",
    "effective_type_explanation": "Single applicable use in resolved context."
  },
  "refs": [],
  "warnings": []
}

Required behavior

When the same attribute appears in multiple modules for an IOD, the tool must compute and explain the effective type. Part 3 notes that when an attribute appears in more than one module for an IOD, the applicable type is the lowest type value unless the attribute description explicitly states otherwise.  ￼

⸻

6.5 retrieve_standard_text

Request

{
  "part": "PS3.3",
  "section_or_anchor": "sect_A.3.3",
  "edition": "2026b"
}

Response

{
  "edition": "2026b",
  "tool": "retrieve_standard_text",
  "status": "ok",
  "result": {
    "part": "PS3.3",
    "section": "A.3.3",
    "title": "CT Image IOD Module Table",
    "text_excerpt": "...",
    "tables": [
      {
        "table_id": "table_A.3-1",
        "title": "CT Image IOD Modules"
      }
    ]
  },
  "refs": [],
  "warnings": []
}

⸻

7. Query routing rules for coding agents

The agent harness should follow a deterministic routing policy.

7.1 Routing order

For any user or coding-agent query:

1. Exact identifier lookup
    Try tags, keywords, UIDs, SOP Class names, IOD names, module names, TID, CID, section IDs, and anchors.
2. Structured graph traversal
    Resolve SOP Class → IOD → modules → attributes → Part 6 dictionary.
3. Contextual value lookup
    Resolve enumerated values and defined terms only within the applicable module/IOD context where possible.
4. Condition lookup
    Return raw condition text plus machine-checkability status.
5. Text retrieval
    Use section-level retrieval for prose-only implementation details.
6. Answer synthesis
    The LLM may summarize the tool results, but it must not add uncited normative claims.

7.2 Agent policy

Coding agents using this system should follow these rules:

- Never answer a normative DICOM question from model memory.
- Always call exact lookup tools before text search.
- Always preserve edition IDs in generated code comments and tests.
- Treat raw-text conditions as unresolved unless a condition evaluator exists.
- Do not silently convert defined terms into enumerated values.
- Do not claim DICOM conformance certification.
- When generating code, include tests derived from structured tool outputs.

⸻

8. Ingestion pipeline specification

8.1 Artifact manifest

Every ingestion run must produce a manifest.

{
  "edition": "2026b",
  "resolved_from": "current",
  "acquired_at": "2026-06-11T00:00:00Z",
  "artifacts": [
    {
      "part": "PS3.3",
      "format": "docbook_xml",
      "local_path": "artifacts/raw/2026b/source/docbook/part03/part03.xml",
      "sha256": "...",
      "byte_size": 12345678
    }
  ],
  "parser_version": "dicom-kb-parser/1.0.0",
  "source_manifest_sha256": "..."
}

8.2 Required parser normalization

The parser must:

1. Strip zero-width spaces before interpreting keywords, UIDs, and tags. The DICOM release notes explicitly warn that zero-width spaces may appear in long words such as PS3.6 keywords and UIDs and need filtering before literal use.  ￼
2. Preserve DocBook xml:id where present.
3. Preserve generated HTML anchors where available.
4. Normalize whitespace.
5. Normalize tags to (gggg,eeee).
6. Normalize UID values as strings.
7. Preserve retired markers.
8. Preserve table captions.
9. Preserve row order.
10. Preserve unresolved cross-references as warnings, not data loss.

8.3 Table parser requirements

The table parser must support:

- DocBook namespace-aware parsing
- thead/tbody separation
- entry spans
- nested links
- emphasis markers
- inline xrefs
- footnotes and notes
- sequence indentation
- repeated headers
- multiline cell content

Every parsed table should produce both:

1. a raw table representation, and
2. a normalized domain entity representation.

This allows parser bugs to be investigated without redownloading or reparsing the original source.

⸻

9. Testing strategy

9.1 Test layers

Unit tests
  parser primitives, tag normalization, UID normalization, table handling
Parser integration tests
  PS3.3, PS3.4, PS3.6 extraction against pinned fixtures
Database tests
  import, uniqueness, referential integrity, migration stability
Query tests
  exact lookup, graph traversal, condition retrieval, citation generation
Agent tests
  prompt → tool trace → answer contract
Differential tests
  compare selected outputs against Innolitics and pydicom dicom-validator
Edition tests
  multiple editions side-by-side, source hash stability, diff behavior

9.2 Golden fixtures

v1 should include golden fixtures for:

Data Elements
  - Modality
  - SOPClassUID
  - SOPInstanceUID
  - PixelData
  - TransferSyntaxUID
  - PatientName
  - StudyInstanceUID
  - SeriesInstanceUID
UIDs
  - Verification SOP Class
  - CT Image Storage
  - MR Image Storage
  - Segmentation Storage
  - Explicit VR Little Endian
  - Implicit VR Little Endian
  - Deflated Explicit VR Little Endian
  - Explicit VR Big Endian retired case
IODs
  - CT Image
  - MR Image
  - Enhanced CT Image
  - Segmentation
  - Comprehensive SR
  - Encapsulated PDF
Modules
  - Patient
  - General Study
  - General Series
  - Image Pixel
  - SOP Common
  - CT Image
  - Contrast/Bolus

9.3 Agent regression cases

Each agent regression test should contain:

{
  "id": "agent.ct.required_modules",
  "prompt": "List the required modules for CT Image IOD and cite the standard.",
  "expected_tools": [
    "lookup_iod",
    "list_modules_for_iod"
  ],
  "must_include": [
    "edition",
    "module usage",
    "source references"
  ],
  "must_not_include": [
    "uncited normative claims",
    "official conformance certification"
  ]
}

9.4 Acceptance gates

A release cannot pass unless:

- all generated entities have edition IDs;
- all public query responses contain source refs or structured not_found errors;
- parser warnings are counted and reported;
- no generated fixture is manually edited without source trace;
- every agent regression answer is produced from tool output;
- all tests pass offline using pinned fixtures;
- online ingestion tests are separated behind an explicit flag;
- all database migrations are reversible or accompanied by migration fixtures.

⸻

10. Implementation work orders for coding agents

Work order A — Repository and build system

Deliverables

- Python 3.12 project
- pyproject.toml
- ruff / mypy / pytest
- Dockerfile
- docker-compose with PostgreSQL
- Makefile targets
- CI workflow

Required commands

make install
make lint
make typecheck
make test
make test-integration
make ingest-fixture
make run-api
make run-mcp

Completion criteria

- clean checkout runs unit tests;
- CI runs lint, typecheck, tests;
- local PostgreSQL starts through docker-compose;
- no network access needed for default tests.

⸻

Work order B — Source acquisition

Deliverables

src/dicom_kb/sources/edition_resolver.py
src/dicom_kb/sources/downloader.py
src/dicom_kb/sources/manifest.py

Required behavior

- load from local artifact directory;
- optionally download current official artifacts;
- resolve current edition label;
- compute SHA-256 checksums;
- write immutable manifest;
- never overwrite a pinned edition unless --force is passed.

Tests

- fixture manifest generation;
- checksum mismatch failure;
- repeated ingestion is idempotent;
- current alias resolves to concrete edition in manifest.

⸻

Work order C — DocBook parser core

Deliverables

src/dicom_kb/docbook/parser.py
src/dicom_kb/docbook/tables.py
src/dicom_kb/docbook/xrefs.py
src/dicom_kb/docbook/targetdb.py
src/dicom_kb/docbook/text_chunks.py

Required behavior

- parse DocBook XML namespace-aware;
- extract sections, titles, labels, xml:id values;
- extract paragraphs with stable references;
- extract tables into raw table IR;
- resolve local xrefs;
- preserve unresolved xrefs with warnings;
- remove zero-width spaces during normalized-token extraction.

Tests

- table with spans;
- nested xref in table cell;
- section with xml:id;
- zero-width space in UID keyword;
- unresolved reference warning.

⸻

Work order D — PS3.6 parser

Deliverables

src/dicom_kb/parsers/part06_data_dictionary.py

Required entities

- data_element
- uid_registry_entry
- file_meta_element
- directory_structuring_element, if parsed in v1

Tests

- known tag lookup fixtures;
- known UID lookup fixtures;
- retired item detection;
- duplicate UID rejection;
- malformed row warning.

⸻

Work order E — PS3.3 parser

Deliverables

src/dicom_kb/parsers/part03_iods.py

Required entities

- iod
- module
- iod_module_use
- module_attribute_use
- raw conditions
- sequence nesting
- enumerated / defined-term placeholders

Tests

- CT Image IOD module table;
- required and conditional module usage;
- module attribute table;
- nested sequence attributes;
- Type 1, 1C, 2, 2C, 3 extraction;
- source ref for every attribute use.

⸻

Work order F — PS3.4 parser

Deliverables

src/dicom_kb/parsers/part04_sop_classes.py

Required entities

- service_class
- sop_class
- sop_class_to_iod relationship
- service-specific overrides where extractable

Tests

- CT Image Storage SOP Class resolves to CT Image IOD;
- Segmentation Storage resolves to Segmentation IOD;
- unsupported or ambiguous SOP relationships create warnings;
- UID registry entries join to SOP Class records.

⸻

Work order G — Database import and migrations

Deliverables

src/dicom_kb/db/models.py
src/dicom_kb/db/importers.py
src/dicom_kb/db/repositories.py
migrations/

Required behavior

- import parsed IR transactionally;
- reject partial imports unless --allow-partial is passed;
- write import summary;
- enforce uniqueness constraints;
- support side-by-side editions.

Tests

- transaction rollback on failure;
- duplicate tag handling;
- duplicate UID handling;
- edition isolation;
- source_ref foreign-key coverage.

⸻

Work order H — Query engine

Deliverables

src/dicom_kb/query/resolver.py
src/dicom_kb/query/graph.py
src/dicom_kb/query/conditions.py
src/dicom_kb/query/citations.py
src/dicom_kb/query/search.py

Required behavior

- exact lookup by tag, keyword, UID, name;
- fuzzy candidate suggestions for near misses;
- graph traversal from SOP Class to IOD to modules to attributes;
- effective attribute type calculation;
- condition retrieval;
- source citation generation;
- structured not_found responses.

Tests

- exact lookup tests;
- ambiguous lookup tests;
- graph traversal tests;
- effective type tests;
- missing entity tests;
- source citation tests.

⸻

Work order I — CLI, HTTP API, and MCP tools

Deliverables

src/dicom_kb/cli/main.py
src/dicom_kb/api/app.py
src/dicom_kb/mcp/server.py

CLI examples

dicom-kb lookup tag Modality --edition 2026b
dicom-kb lookup uid 1.2.840.10008.1.2.1 --edition 2026b
dicom-kb iod modules "CT Image" --edition 2026b
dicom-kb module attributes "General Series" --edition 2026b
dicom-kb context attribute Modality --iod "CT Image" --edition 2026b

HTTP examples

GET /v1/data-elements/Modality?edition=2026b
GET /v1/uids/1.2.840.10008.1.2.1?edition=2026b
GET /v1/iods/CT%20Image/modules?edition=2026b
POST /v1/resolve-attribute-context

MCP tools

dicom_lookup_data_element
dicom_lookup_uid
dicom_lookup_sop_class
dicom_lookup_iod
dicom_list_modules_for_iod
dicom_list_attributes_for_module
dicom_resolve_attribute_context
dicom_retrieve_standard_text
dicom_search_standard_text

Tests

- CLI snapshot tests;
- HTTP schema tests;
- MCP schema validation;
- error envelope consistency;
- JSON output stability.

⸻

Work order J — Agent evaluation harness

Deliverables

src/dicom_kb/eval/prompt_cases.py
src/dicom_kb/eval/expected_tool_traces.py
tests/agent_regression/

Required behavior

- run prompt cases against a configured agent;
- record tool traces;
- validate required tools were called;
- validate answer references;
- detect unsupported normative claims;
- emit scorecard.

Completion criteria

- at least 50 v1 prompt cases;
- at least 100 v2 prompt cases;
- failure reports show missing tool calls or missing citations;
- all eval fixtures are edition-pinned.

⸻

11. Response safety and correctness policy

Every generated answer should be classified.

{
  "normativity": "normative | explanatory | derived | heuristic | unsupported",
  "evidence_level": "parsed_table | parsed_registry | parsed_cross_reference | retrieved_text | external_comparison",
  "machine_decidability": "decidable | partially_decidable | not_decidable | not_applicable"
}

Rules:

- parsed_table beats retrieved_text for structured facts;
- parsed_registry beats approximate string search for tags and UIDs;
- retrieved_text may explain but should not override structured parsed data without warning;
- external projects may be used for differential testing but not as primary evidence;
- unsupported answers must say what could not be found.

⸻

12. Operational metrics

The system should emit metrics after every ingestion:

{
  "edition": "2026b",
  "parts_loaded": ["PS3.3", "PS3.4", "PS3.6"],
  "data_elements": 0,
  "uids": 0,
  "iods": 0,
  "modules": 0,
  "iod_module_uses": 0,
  "module_attribute_uses": 0,
  "conditions": 0,
  "xrefs_total": 0,
  "xrefs_unresolved": 0,
  "parse_warnings": 0,
  "source_refs": 0
}

Quality gates should fail when:

- source refs are missing for parsed entities;
- xref unresolved rate exceeds configured threshold;
- data element count changes unexpectedly between parser versions without edition change;
- UID count changes unexpectedly between parser versions without edition change;
- parser warnings increase above baseline;
- golden outputs change without explicit approval.

⸻

13. Recommended implementation stack

A practical stack for coding agents:

Language
  Python 3.12+
Parsing
  lxml
  pydantic
  beautifulsoup4 only for HTML cross-checks, not primary parsing
Database
  PostgreSQL for service deployment
  SQLite for local single-agent use
API
  FastAPI
  OpenAPI schema generation
CLI
  Typer or argparse
Testing
  pytest
  syrupy or approvaltests for snapshots
  hypothesis for normalization/property tests
  mypy or pyright
  ruff
Agent tooling
  MCP server adapter
  JSON Schema for tool contracts
Search
  PostgreSQL full-text search for v1
  optional vector index for prose retrieval in v2+

The simplest robust architecture is a Python core library with three thin surfaces: CLI, HTTP, and MCP.

⸻

14. Example coding-agent workflow

A coding agent asked to generate a validator for CT Image Storage should follow this trace:

1. call dicom_lookup_sop_class("CT Image Storage")
2. call dicom_lookup_iod("CT Image")
3. call dicom_list_modules_for_iod("CT Image")
4. for each required/conditional module:
     call dicom_list_attributes_for_module(module)
5. for each attribute:
     call dicom_lookup_data_element(tag)
6. for each Type 1C/2C:
     call dicom_explain_condition(condition_id)
7. generate code from structured facts
8. generate tests using golden expected attributes
9. include edition ID and source refs in generated test metadata

Generated code should carry provenance metadata:

{
  "generated_from": {
    "service": "dicom-standard-kb",
    "edition": "2026b",
    "source_manifest_sha256": "...",
    "tool_trace_id": "..."
  }
}

⸻

15. Main risks and mitigations

Risk: edition drift

DICOM changes several times per year, and the current URL always resolves to the current edition.  ￼

Mitigation:

- never store only "current";
- always resolve current to concrete edition;
- pin all generated code and tests to edition;
- import new editions side-by-side;
- require regression tests before changing default edition.

Risk: false precision

Some DICOM rules depend on clinical context, acquisition context, other objects, negotiated behavior, or implementation role.

Mitigation:

- classify conditions by machine decidability;
- preserve raw normative text;
- expose unresolved warnings;
- avoid claiming conformance certification.

Risk: parser brittleness

DocBook tables can contain spans, nested references, footnotes, formatting artifacts, and unusual indentation.

Mitigation:

- store raw table IR and normalized entities;
- snapshot parsed tables;
- test known difficult sections;
- compare selected outputs with external tools;
- count parser warnings.

Risk: copyright and redistribution

The DICOM publication is public and free to use, but public redistribution of large quantities of standard text should be reviewed.

Mitigation:

- store source artifacts internally;
- expose concise excerpts only where needed;
- prefer structured facts and official links;
- obtain legal review before public/commercial release.

Risk: model hallucination

A coding agent may answer directly instead of using tools.

Mitigation:

- enforce tool-first agent policy;
- evaluate prompt traces;
- fail answers with uncited normative claims;
- make tool responses compact enough that agents prefer them.

⸻

16. Recommended v1 build sequence

For v1, implement in this order:

1. repository, CI, Docker, test harness;
2. source acquisition and manifest system;
3. DocBook section/table parser;
4. source_ref and doc_node extraction;
5. PS3.6 Data Element and UID registry parser;
6. database schema and import;
7. lookup_data_element and lookup_uid;
8. PS3.3 IOD/module parser;
9. list_modules_for_iod and list_attributes_for_module;
10. PS3.4 SOP Class parser;
11. SOP Class → IOD graph traversal;
12. resolve_attribute_context;
13. CLI;
14. HTTP API;
15. MCP server;
16. agent regression tests;
17. documentation and example coding-agent workflows.

A good v1 release target is:

A coding agent can ask about a SOP Class, IOD, module, attribute, tag, or UID and receive deterministic structured data, edition metadata, and official citations without relying on model memory.

That clarification changes the packaging and licensing posture more than the technical design. I would keep the core architecture the same, but make the public repository primarily a parser/query engine, not a redistribution channel for the DICOM standard itself.

The DICOM site says the standard is free to download and use, and its IP page says no license is required to download or implement it. However, DICOM publications are copyright owned by NEMA, and requests to reproduce the standard should go through the DICOM Secretariat. The current edition is also republished several times per year and is available in PDF, HTML, CHTML, DOCX, ODT, and XML formats.  ￼  ￼  ￼

Recommended public-open-source posture

For your use case, I would structure the project like this:

Public GitHub repository:
  - parser code
  - schemas
  - CLI
  - HTTP API
  - MCP / coding-agent tools
  - test harness
  - small attribution-preserving fixtures
  - documentation
  - scripts to download/build a local knowledge base
Not committed to GitHub:
  - full official DICOM XML/PDF/HTML source artifacts
  - full generated JSON dumps of the standard
  - large text chunks copied from the standard
  - bulk PS3.16 terminology-derived data unless licensing is reviewed
Locally generated by the user:
  - downloaded official DICOM artifacts
  - parsed database
  - full-text index
  - vector index, if used
  - generated edition-specific knowledge graph

This avoids turning the repository into a mirror or derivative redistribution of the standard, while still giving you a fully usable tool locally.

⸻

Revised project specification for public OSS use

1. Project identity

Suggested project description:

dicom-standard-kb is an open-source parser and query service for building a local, edition-pinned knowledge base from the official DICOM standard. It provides deterministic tools for coding agents, validators, and medical imaging development workflows.

Important wording:

This project is not affiliated with or endorsed by NEMA, MITA, or the DICOM Standards Committee.
DICOM® is a registered trademark of the National Electrical Manufacturers Association.
The DICOM Standard is copyright owned by NEMA.
Users should obtain the official current standard from dicomstandard.org.
This project does not certify DICOM conformance.

I would include that in README.md, NOTICE, CLI startup metadata, generated manifests, and API /about.

⸻

2. Repository license

For the code, I would use Apache License 2.0 rather than MIT.

Reason: Apache 2.0 is still permissive, but it includes an explicit patent grant, which is helpful for infrastructure projects that may be used by companies, research labs, medical-device teams, and imaging software vendors.

Recommended files:

LICENSE                  # Apache-2.0 for project code
NOTICE                   # DICOM/NEMA attribution and non-affiliation notice
THIRD_PARTY_NOTICES.md   # dependencies and external standard references
docs/legal.md            # practical redistribution notes

The code license should not imply that the DICOM standard text or derived local knowledge base is licensed under Apache 2.0.

Add this to the README:

The Apache-2.0 license applies to this repository’s original source code.
It does not apply to the DICOM Standard or to third-party terminology content
referenced by the DICOM Standard.

⸻

3. Source-artifact policy

3.1 Do not vendor official artifacts

Do not commit:

dicom.nema.org/medical/dicom/current/source/docbook/*
*.xml copied from official DICOM releases
*.pdf copied from official DICOM releases
*.html copied from official DICOM releases
bulk generated JSON of all parsed standard content
bulk generated SQLite/PostgreSQL dumps

Instead, provide:

dicom-kb fetch --edition current
dicom-kb fetch --edition 2026b
dicom-kb build --edition 2026b
dicom-kb serve --edition 2026b

The fetch command should download from official DICOM URLs, compute hashes, and store files locally.

Suggested local layout:

~/.cache/dicom-standard-kb/
  artifacts/
    2026b/
      raw/
        source/
        html/
        pdf/
      manifest.json
      checksums.json
  db/
    2026b.sqlite
  indexes/
    2026b/

For containerized use:

/data/dicom-standard-kb/
  artifacts/
  db/
  indexes/

⸻

3.2 Commit only minimal fixtures

For tests, include only small, targeted fixtures.

Allowed fixture types:

- tiny synthetic DocBook tables created by you;
- tiny excerpts from DICOM with explicit attribution, only when needed to test parser behavior;
- generated expected outputs for a handful of well-known tags/UIDs;
- test cases that require the user or CI to download the official standard before running integration tests.

Split tests into two groups:

make test
# Runs offline, no official DICOM bulk artifacts required.
make test-dicom-integration
# Requires local downloaded DICOM artifacts.
make test-dicom-current
# Optional networked test; resolves official current edition.

This lets contributors validate the parser without requiring the repository to carry the full standard.

⸻

4. Distribution model

4.1 Python package

Publish the package to PyPI as code only:

dicom-standard-kb

Installation:

pip install dicom-standard-kb

Then:

dicom-kb fetch --edition current
dicom-kb build --edition current
dicom-kb lookup tag Modality

The package should not include the built database.

4.2 Docker image

Publish a Docker image containing only code and dependencies:

docker run --rm -v dicom-kb-data:/data ghcr.io/yourname/dicom-standard-kb fetch --edition current
docker run --rm -v dicom-kb-data:/data ghcr.io/yourname/dicom-standard-kb build --edition current
docker run --rm -p 8000:8000 -v dicom-kb-data:/data ghcr.io/yourname/dicom-standard-kb serve

Do not publish a Docker image with the full DICOM standard preloaded unless you get permission or decide after legal review that it is acceptable.

4.3 GitHub releases

Release:

- source code tarballs;
- wheels;
- Docker images;
- parser test reports;
- schema versions;
- maybe small sample databases built from synthetic fixtures.

Avoid releasing:

- full parsed DICOM database;
- full DocBook mirror;
- full-text indexes over the standard;
- vector indexes containing large text chunks.

⸻

Revised system versions

v1 — Public parser and local core knowledge service

v1 should deliver a complete local build pipeline for:

PS3.3  Information Object Definitions
PS3.4  Service Class Specifications
PS3.6  Data Dictionary and UID Registry

v1 public deliverables:

- public open-source parser;
- local fetch/build workflow;
- local SQLite knowledge base;
- Python API;
- CLI;
- MCP server;
- small offline fixture tests;
- optional integration tests against locally downloaded official DICOM XML;
- documentation for coding-agent use.

v1 should not publish a prebuilt full DICOM database.

The primary success criterion becomes:

A user can clone the public repository, run a documented build command that fetches the official standard locally, and then query an edition-pinned DICOM knowledge base through CLI, Python, HTTP, or MCP tools.

⸻

v2 — Local implementation-semantics expansion

v2 adds:

PS3.5   Data Structures and Encoding
PS3.10  Media Storage and File Format
PS3.16  Content Mapping Resource
PS3.18  Web Services

For public OSS, PS3.16 needs special care because DICOM incorporates external terminology, including SNOMED CT. The DICOM IP page notes that DICOM incorporates SNOMED CT, and the DICOM relations page says DICOM and SNOMED have a license agreement permitting a subset of SNOMED CT to be used in DICOM and by implementers/users of DICOM-compliant products.  ￼  ￼

Practical policy:

- parse PS3.16 locally;
- expose local lookup tools;
- cite official DICOM source locations;
- avoid publishing a standalone terminology dump;
- include explicit third-party terminology notices.

⸻

v3 — Constraint reasoning and validation assistance

v3 remains as previously specified, but with public OSS constraints:

- validation rule engine is open source;
- official standard-derived rule database is built locally;
- published examples use synthetic metadata;
- real test DICOMs must be deidentified and license-compatible;
- no claim of official DICOM conformance certification.

⸻

v4 — Edition management and reproducible local builds

v4 becomes especially important for your use case because the current DICOM URL is mutable. The official current page says DICOM is updated and republished several times per year, and the “current” path always resolves to the current edition.  ￼

v4 should support:

dicom-kb editions list-local
dicom-kb editions fetch-current
dicom-kb editions pin 2026b
dicom-kb editions compare 2026a 2026b --entity Modality
dicom-kb build --edition 2026b --reproducible

Every local generated database should include:

{
  "edition": "2026b",
  "resolved_from": "current",
  "source_urls": [],
  "source_sha256": {},
  "built_at": "2026-06-11T00:00:00Z",
  "parser_version": "1.4.0",
  "schema_version": "4",
  "repository_commit": "..."
}

⸻

Concrete public repository layout

dicom-standard-kb/
  LICENSE
  NOTICE
  README.md
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  SECURITY.md
  THIRD_PARTY_NOTICES.md
  pyproject.toml
  docker-compose.yml
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
    sources/
    docbook/
    parsers/
    ir/
    db/
    query/
    api/
    cli/
    mcp/
    eval/
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

⸻

Recommended .gitignore

# Local DICOM artifacts
artifacts/raw/
artifacts/parsed/
artifacts/indexes/
*.sqlite
*.sqlite3
*.db
# Official standard downloads
dicom-xml-*/
dicom-html-*/
dicom-pdf-*/
part*.xml
part*.pdf
# Generated KB data
*.duckdb
*.parquet
generated-standard-json/
generated-standard-text/
vector-indexes/
# Python
.venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
dist/
build/

⸻

README legal block

I would include something close to this:

## DICOM Standard source material
This project does not redistribute the DICOM Standard.
The software can download and parse official DICOM Standard artifacts from
the official DICOM website for local use. The DICOM Standard is published
by and copyright owned by the National Electrical Manufacturers Association
(NEMA). DICOM® is a registered trademark of NEMA.
The DICOM Standard is under continuous maintenance. Users should consult
the current official version at dicomstandard.org.
This project is not affiliated with, sponsored by, or endorsed by NEMA,
MITA, or the DICOM Standards Committee. It does not provide official
DICOM conformance certification.

⸻

Generated-output policy

For public use, I would make the default behavior conservative.

CLI output

Good default:

{
  "edition": "2026b",
  "result": {
    "tag": "(0008,0060)",
    "keyword": "Modality",
    "vr": "CS",
    "vm": "1"
  },
  "refs": [
    {
      "part": "PS3.6",
      "section": "Registry of DICOM Data Elements",
      "official_url": "https://dicom.nema.org/..."
    }
  ],
  "notice": "Consult the official DICOM Standard for authoritative text."
}

Avoid by default:

{
  "full_standard_paragraph": "large copied block..."
}

Provide an explicit flag for local excerpts:

dicom-kb retrieve-text PS3.3 sect_A.3.3 --max-chars 800

For public hosted demos, I would disable or heavily limit raw text retrieval.

⸻

Public hosted demo policy

Because you want public open source but primarily personal use, I would separate:

Local full service:
  full structured lookup
  local text retrieval
  local search
  local generated DB
Public demo:
  tag lookup
  UID lookup
  official-link generation
  limited short excerpts
  no bulk download endpoint
  no full database export

A public demo should not expose:

GET /export/full-standard-json
GET /text/all
GET /database/download
GET /vector-index/download

⸻

Coding-agent harness policy

For your personal coding harnesses, use the full local service.

Recommended local configuration:

dicom_kb:
  edition: "current-resolved"
  artifact_dir: "~/.cache/dicom-standard-kb/artifacts"
  database_url: "sqlite:///~/.cache/dicom-standard-kb/db/current.sqlite"
  allow_text_retrieval: true
  max_text_excerpt_chars: 1200
  require_citations: true
  require_edition_pin: true
  allow_network_fetch: false

For public CI:

dicom_kb:
  allow_text_retrieval: false
  use_synthetic_fixtures_only: true
  require_dicom_download_for_integration: true
  publish_generated_db: false

⸻

Concrete build commands

First-time personal local build

git clone https://github.com/yourname/dicom-standard-kb
cd dicom-standard-kb
uv sync
dicom-kb fetch --edition current
dicom-kb build --edition current --backend sqlite
dicom-kb doctor
dicom-kb lookup tag Modality
dicom-kb lookup uid 1.2.840.10008.1.2.1
dicom-kb iod modules "CT Image"

Reproducible pinned build

dicom-kb fetch --edition 2026b
dicom-kb build --edition 2026b --backend sqlite --output ~/.cache/dicom-standard-kb/db/2026b.sqlite
dicom-kb verify --edition 2026b

Agent server

dicom-kb mcp serve --edition 2026b

or:

dicom-kb api serve --edition 2026b --host 127.0.0.1 --port 8765

⸻

Adjusted implementation priorities

Given your public/personal hybrid goal, I would implement in this order:

1. Public repository skeleton, license, NOTICE, README, legal docs.
2. Local artifact cache and manifest system.
3. Synthetic DocBook parser fixtures.
4. Official-artifact fetch command.
5. PS3.6 parser, because tag/UID lookup is the fastest useful win.
6. SQLite backend, because it is ideal for personal research tooling.
7. CLI lookup tools.
8. PS3.3 parser for IOD/module/attribute traversal.
9. MCP server for coding agents.
10. Agent regression harness.
11. Optional PostgreSQL/FastAPI deployment.
12. PS3.4 SOP Class linking.
13. PS3.5, PS3.16, PS3.18 expansion.

The reason I would put SQLite before PostgreSQL is that your primary user is you, using coding harnesses. A single-file generated database is easy to mount into containers, commit nowhere, regenerate anytime, and hand to local agents.

⸻

Key design decision

The project should be:

An open-source DICOM-standard knowledge-base builder, not an open-source copy of the DICOM standard knowledge base.

That distinction gives you the best balance: public, useful, reproducible, agent-friendly, and conservative about redistribution.
