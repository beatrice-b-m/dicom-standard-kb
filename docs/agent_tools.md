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
- `notice`: reminder to consult the official DICOM Standard.
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

## Verification

Before relying on a locally built official KB, validate the cache and build
metadata:

```bash
dicom-kb verify --edition 2026b
```

Verification recomputes cached artifact checksums from the manifest and checks
database build metadata when a database for the edition is present.
