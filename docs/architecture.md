# Architecture

The architecture is a Python core library with thin public surfaces: CLI,
MCP, and local SQLite storage. Official artifacts are acquired into a local
cache, parsed into canonical records, imported transactionally, and queried
through edition-aware response contracts.

The repository remains a knowledge-base builder. Official DICOM artifacts,
generated databases, full-text indexes, and standalone terminology dumps stay
outside the repository and are rebuilt locally from an edition-pinned source
manifest.

## V2 Entities

V2 extends the v1 PS3.3/PS3.4/PS3.6 graph with parser-specific entities for
PS3.5, PS3.10, PS3.16, and PS3.18. Each table stores an `edition_id` and a
`source_ref_id` so every returned fact can be traced back to the official
part, section, table, or DocBook anchor that produced it.

`vr_definition` stores PS3.5 value representation definitions by VR keyword,
including the VR name, value-representation class, length notes, padding
behavior, character repertoire notes, and binary/text classification.
`transfer_syntax_detail` enriches PS3.6 transfer syntax UID rows with parsed
encoding facts such as explicit or implicit VR behavior, endian behavior,
encapsulation, compression family, and bounded encoding notes.

`file_meta_requirement` stores PS3.10 file meta information requirements by
attribute tag, keyword, type designation, and rule context. `dicom_media_type`
stores PS3.10 and PS3.18 media type rows with service context, transfer
syntax constraints, request/response directions, and citations.

`dicomweb_transaction` stores PS3.18 DICOMweb transaction rows with
transaction name, HTTP method, route template, resource category, request and
response constraints, status codes, media-type references, and source
references. Route lookup is deterministic; ambiguous route matches return
candidates instead of guessing.

`sr_template` and `sr_template_row` store PS3.16 SR template metadata and
ordered rows, including extensibility, relationship type, value type, concept
name, cardinality, condition text, and include-TID references.
`context_group` and `context_group_row` store PS3.16 context group metadata
and ordered coded or include rows, including CID, extensibility, version,
coding scheme, code value, code meaning, and include-CID references.
`coded_concept` stores locally derived coded concepts from parsed context
group rows for lookup and joins; it is not a standalone terminology export.

## Attribute Value Terms

Enumerated values and defined terms are stored in `attribute_value_term`.
The current importer scans parsed DocBook variable lists whose titles contain
`Enumerated Values` or `Defined Terms`, then imports each listed term with the
variable-list source reference. Defined terms stay distinct from enumerated
values through the `term_kind` column.

The importer links a term to the PS3.6 `data_element` row when the surrounding
section title, section anchor, tag, keyword, or section prose identifies a
single attribute. When PS3.3 attribute usage has already been imported, the
term also links to an `attribute_use` row when the variable list appears in
the same source section as that attribute use, or when the attribute has a
single imported use in the edition.

The public `lookup_enumerated_values` and `lookup_defined_terms` resolvers
currently accept an attribute tag, keyword, or name and an optional text
context. Context matching is deterministic for stored context labels, exact
PS3.3 module names, exact PS3.3 macro names, exact PS3.3 IOD names or keywords,
and exact PS3.4 SOP Class names, keywords, or UIDs that resolve to IODs
through the imported SOP Class graph.

When an IOD or SOP Class context resolves to one or more applicable
`attribute_use` rows, lookup filters value terms through those attribute-use
ids and includes the IOD, SOP Class, module, macro, and attribute-use
references in the response. If the context input still maps to multiple
value-term contexts, the resolver returns candidates rather than merging the
terms into a guessed answer. TID, CID, and DICOMweb contexts are not
attribute-use contexts today; those domains are exposed through their own v2
lookup entities.
