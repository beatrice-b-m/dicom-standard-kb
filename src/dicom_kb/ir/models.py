"""Canonical records shared by parsers, storage, and queries."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SourceRef(BaseModel):
    """A compact source reference attached to parsed facts."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    part: str
    section: str | None = None
    table_id: str | None = None
    xml_id: str | None = None
    title: str | None = None
    canonical_url: str | None = None


class DataElement(BaseModel):
    """PS3.6 data element registry row."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    tag: str
    group_pattern: str
    element_pattern: str
    is_range: bool
    name: str
    keyword: str | None
    vr: str | None
    vm: str | None
    retired: bool
    retired_in_or_last_seen: str | None = None
    source_ref: SourceRef


class UIDRegistryEntry(BaseModel):
    """PS3.6 UID registry row."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    uid_value: str
    uid_name: str
    uid_keyword: str | None
    uid_type: str
    part: str | None
    retired: bool
    retired_in_or_last_seen: str | None = None
    source_ref: SourceRef


class IOD(BaseModel):
    """PS3.3 Information Object Definition."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    name: str
    keyword: str | None = None
    iod_type: str | None = None
    part: str = "PS3.3"
    section: str | None = None
    source_ref: SourceRef


class Module(BaseModel):
    """PS3.3 module definition."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    name: str
    section: str | None = None
    description: str | None = None
    source_ref: SourceRef


class Macro(BaseModel):
    """PS3.3 reusable macro definition."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    name: str
    table_id: str | None = None
    section: str | None = None
    macro_kind: str | None = None
    source_ref: SourceRef


class IODModuleUse(BaseModel):
    """A module listed in an IOD module table."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    iod_id: str
    information_entity: str | None
    module_id: str
    usage: str
    usage_condition_text: str | None = None
    condition_id: str | None = None
    source_ref: SourceRef


class IODFunctionalGroupUse(BaseModel):
    """A functional group macro listed for an IOD."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    iod_id: str
    macro_id: str
    usage: str
    usage_condition_text: str | None = None
    condition_id: str | None = None
    source_ref: SourceRef


class AttributeUse(BaseModel):
    """An attribute or include row owned by a PS3.3 module or macro."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    owner_type: str
    owner_id: str
    parent_attribute_use_id: str | None = None
    row_kind: str
    attribute_tag: str | None = None
    attribute_keyword: str | None = None
    attribute_name: str | None = None
    type_designation: str | None = None
    description_text: str | None = None
    condition_id: str | None = None
    included_macro_id: str | None = None
    include_target_text: str | None = None
    sequence_depth: int = 0
    row_order: int
    source_ref: SourceRef


class AttributeValueTerm(BaseModel):
    """A parsed enumerated value or defined term for an attribute context."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    attribute_use_id: str | None = None
    data_element_id: str | None = None
    context_label: str | None = None
    term_kind: str
    value: str
    meaning: str | None = None
    source_ref: SourceRef


class VRDefinition(BaseModel):
    """PS3.5 value representation behavior row."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    vr: str
    name: str
    value_representation_class: str | None = None
    length_notes: tuple[str, ...] = ()
    padding_behavior: str | None = None
    character_repertoire_notes: tuple[str, ...] = ()
    binary_or_text: str | None = None
    source_ref: SourceRef


class TransferSyntaxDetail(BaseModel):
    """Deterministic encoding details for a PS3.6 transfer syntax UID."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    uid_registry_entry_id: str
    uid_value: str
    explicit_vr: bool | None = None
    endian: str | None = None
    encapsulated: bool | None = None
    compression_family: str | None = None
    encoding_notes: tuple[str, ...] = ()
    source_ref: SourceRef


class FileMetaRequirement(BaseModel):
    """PS3.10 file meta information attribute requirement row."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    data_element_id: str | None = None
    attribute_tag: str
    attribute_keyword: str | None = None
    type_designation: str
    rule_context: str | None = None
    source_ref: SourceRef


class DicomMediaType(BaseModel):
    """DICOM media type rule row from PS3.10 or PS3.18."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    media_type: str
    service_context: str | None = None
    transfer_syntax_constraints: tuple[str, ...] = ()
    directions: tuple[str, ...] = ()
    source_ref: SourceRef


class DicomwebTransaction(BaseModel):
    """DICOMweb transaction row parsed from PS3.18."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    transaction_name: str
    resource_category: str | None = None
    http_method: str
    route_template: str
    request_constraints: tuple[str, ...] = ()
    response_constraints: tuple[str, ...] = ()
    status_codes: tuple[str, ...] = ()
    media_type_refs: tuple[str, ...] = ()
    source_ref: SourceRef


class SRTemplate(BaseModel):
    """PS3.16 SR template metadata row."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    tid: str
    name: str
    extensibility: str | None = None
    source_ref: SourceRef


class SRTemplateRow(BaseModel):
    """PS3.16 SR template content row."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    sr_template_id: str
    row_order: int
    relationship_type: str | None = None
    value_type: str | None = None
    concept_name: str | None = None
    cardinality: str | None = None
    condition_text: str | None = None
    condition_id: str | None = None
    include_tid: str | None = None
    source_ref: SourceRef


class Condition(BaseModel):
    """A preserved raw condition with machine-readability metadata."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    condition_kind: str | None = None
    raw_text: str
    normalized_text: str | None = None
    machine_status: str
    expression_json: str | None = None
    source_ref: SourceRef


class ServiceClass(BaseModel):
    """PS3.4 service class definition."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    name: str
    section: str | None = None
    source_ref: SourceRef


class SOPClass(BaseModel):
    """PS3.4 SOP Class definition."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    name: str
    uid_value: str
    service_class_id: str | None = None
    source_ref: SourceRef


class SOPClassIOD(BaseModel):
    """PS3.4 SOP Class to PS3.3 IOD relationship."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    sop_class_id: str
    iod_id: str
    resolution: str
    resolution_warning: str | None = None
    source_ref: SourceRef


class DocNode(BaseModel):
    """Persisted DocBook structural node for retrieval and citations."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    part: str
    node_type: str
    parent_id: str | None = None
    xml_id: str | None = None
    anchor: str | None = None
    number: str | None = None
    title: str | None = None
    ordinal: int
    plain_text: str | None = None
    source_ref: SourceRef


class Xref(BaseModel):
    """Persisted DocBook cross-reference edge."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    source_node_id: str
    target_ref: str
    target_node_id: str | None = None
    link_type: str
    resolved: bool
    resolution_warning: str | None = None
    text: str | None = None


class RawTableIR(BaseModel):
    """Persisted JSON snapshot of parsed raw table IR."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    part: str
    table_id: str | None = None
    title: str | None = None
    ordinal: int
    source_ref: SourceRef
    ir_json: str
    ir_sha256: str


class ParserWarning(BaseModel):
    """Structured parser warning."""

    model_config = ConfigDict(frozen=True)

    part: str
    table_id: str | None
    row_index: int | None
    message: str
