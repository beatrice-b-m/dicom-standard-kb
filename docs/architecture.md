# Architecture

The v1 architecture is a Python core library with thin surfaces: CLI, MCP,
and local SQLite storage. Official artifacts are acquired into a local cache,
parsed into canonical records, imported transactionally, and queried through
edition-aware response contracts.

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
context. Context matching is deterministic only for stored context labels and
exact PS3.3 module or macro names. IOD, SOP Class, TID, CID, and DICOMweb
contexts are not yet resolved to candidate attribute uses; those are Phase 6
extension points.
