# Agent Tools

Coding agents should use deterministic lookup and traversal tools before
answer synthesis. Normative DICOM facts must come from parsed facts or
retrieved cited text, not model memory.

## Response Envelope

Every public resolver response uses the same envelope:

- `status`: `ok`, `not_found`, or `validation_error`.
- `result`: structured parsed data or a structured error message.
- `refs`: DICOM Standard source references for the facts used.
- `warnings`: uncertainty, unsupported cases, or bounded heuristic notes.
- `classification`: deterministic normativity, evidence level, and machine
  decidability metadata.
- `parse_confidence`: conservative parse confidence metadata.
- `trace`: query id, resolution time, and optional source-manifest digest.

Do not drop `classification`, `parse_confidence`, `warnings`, or `refs` when
passing tool output into answer synthesis.

## Preferred Context Queries

Use context-aware tools when answering whether an attribute is required or how
it is used in a specific IOD or SOP Class:

```bash
dicom-kb context attribute Modality --edition 2026b --iod "CT Image"
dicom-kb resolve attribute-context Modality --edition 2026b --iod "CT Image"
```

`context attribute` is the documented alias. It calls the same resolver as
`resolve attribute-context`.

For MCP clients, use the matching `dicom_resolve_attribute_context` tool and
preserve its response envelope in downstream reasoning.

## Effective Type

`resolve_attribute_context` reports `effective_type` only when the resolver can
make a bounded determination from parsed rows:

- A single applicable use returns that use's declared type.
- Multiple applicable uses use the DICOM lowest-type rule after matched
  attribute-use descriptions and condition text are inspected for explicit
  override phrases.
- Explicit override language such as "shall be Type 1" or "is Type 3 in this
  module" takes precedence and is cited in the explanation by source ref.
- Conflicting or ambiguous override prose leaves `effective_type` null and
  reports source-ref warnings. The response remains
  `partially_decidable`.

Agents should not infer a stricter type from null `effective_type`; quote or
retrieve the cited standard text instead.

## V2 Tool Routing

Prefer structured v2 tools before text retrieval for implementation semantics
from PS3.5, PS3.10, PS3.16, and PS3.18:

| Question type | CLI command | MCP tool |
|---|---|---|
| Value Representation behavior | `dicom-kb lookup vr <vr>` | `dicom_lookup_vr` |
| Transfer Syntax encoding details | `dicom-kb lookup transfer-syntax <uid-or-keyword>` | `dicom_lookup_transfer_syntax` |
| Encoding prose rule | `dicom-kb explain encoding <topic>` | `dicom_explain_encoding_rule` |
| DICOMweb transaction route or name | `dicom-kb lookup dicomweb <name-or-route>` | `dicom_lookup_dicomweb_transaction` |
| Media type constraints or context | `dicom-kb lookup media-type <media-type-or-context>` | `dicom_lookup_media_type` |
| SR template rows | `dicom-kb lookup sr-template <tid-or-name>` | `dicom_lookup_sr_template` |
| Context group rows | `dicom-kb lookup context-group <cid-or-name>` | `dicom_lookup_context_group` |
| Coded concept meaning | `dicom-kb lookup code <code-value> [--scheme <scheme>]` | `dicom_lookup_code_meaning` |

For enumerated values and defined terms, keep using
`dicom-kb lookup enumerated-values <attribute>` and
`dicom-kb lookup defined-terms <attribute>` with `--context` when an IOD,
SOP Class, module, or macro context is known. MCP clients should use
`dicom_lookup_enumerated_values` and `dicom_lookup_defined_terms` with the
optional `context` argument.

When a v2 structured tool returns `not_found`, candidates, or warnings, do
not fill in the missing normative fact from memory. Use
`dicom_retrieve_standard_text` or `dicom_search_standard_text` for bounded,
cited prose fallback, especially for selected PS3.7/PS3.8 messaging or
networking topics that do not have dedicated public tools.

## Verification

Before relying on a locally built official KB, validate the cache and build
metadata:

```bash
dicom-kb verify --edition 2026b
```

Verification recomputes cached artifact checksums from the manifest and checks
database build metadata when a database for the edition is present.
