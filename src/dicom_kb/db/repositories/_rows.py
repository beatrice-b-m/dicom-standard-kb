"""Internal conversion of SQLite rows into canonical IR models."""

from __future__ import annotations

import json
import sqlite3

from dicom_kb.ir.models import (
    IOD,
    AttributeUse,
    AttributeValueTerm,
    CodedConcept,
    Condition,
    ContextGroup,
    ContextGroupRow,
    DataElement,
    DicomMediaType,
    DicomwebTransaction,
    DocNode,
    IODFunctionalGroupUse,
    IODModuleUse,
    Macro,
    Module,
    ServiceClass,
    SOPClass,
    SOPClassIOD,
    SourceRef,
    SRTemplate,
    SRTemplateRow,
    TransferSyntaxDetail,
    UIDRegistryEntry,
    VRDefinition,
)


def _source_ref_from_row(row: sqlite3.Row) -> SourceRef:
    return SourceRef(
        id=str(row["source_ref_id"]),
        edition_id=str(row["edition_id"]),
        part=str(row["source_part"]),
        section=row["source_section"],
        table_id=row["source_table_id"],
        xml_id=row["source_xml_id"],
        title=row["source_title"],
        canonical_url=row["source_url"],
    )


def _data_element_from_row(row: sqlite3.Row) -> DataElement:
    return DataElement(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        tag=str(row["tag"]),
        group_pattern=str(row["group_pattern"]),
        element_pattern=str(row["element_pattern"]),
        is_range=bool(row["is_range"]),
        name=str(row["name"]),
        keyword=row["keyword"],
        vr=row["vr"],
        vm=row["vm"],
        retired=bool(row["retired"]),
        retired_in_or_last_seen=row["retired_in_or_last_seen"],
        source_ref=_source_ref_from_row(row),
    )


def _doc_node_from_row(row: sqlite3.Row) -> DocNode:
    return DocNode(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        part=str(row["part"]),
        node_type=str(row["node_type"]),
        parent_id=row["parent_id"],
        xml_id=row["xml_id"],
        anchor=row["anchor"],
        number=row["number"],
        title=row["title"],
        ordinal=int(row["ordinal"]),
        plain_text=row["plain_text"],
        source_ref=_source_ref_from_row(row),
    )


def _uid_from_row(row: sqlite3.Row) -> UIDRegistryEntry:
    return UIDRegistryEntry(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        uid_value=str(row["uid_value"]),
        uid_name=str(row["uid_name"]),
        uid_keyword=row["uid_keyword"],
        uid_type=str(row["uid_type"]),
        part=row["part"],
        retired=bool(row["retired"]),
        retired_in_or_last_seen=row["retired_in_or_last_seen"],
        source_ref=_source_ref_from_row(row),
    )


def _vr_definition_from_row(row: sqlite3.Row) -> VRDefinition:
    return VRDefinition(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        vr=str(row["vr"]),
        name=str(row["name"]),
        value_representation_class=row["value_representation_class"],
        length_notes=tuple(json.loads(str(row["length_notes_json"]))),
        padding_behavior=row["padding_behavior"],
        character_repertoire_notes=tuple(
            json.loads(str(row["character_repertoire_notes_json"]))
        ),
        binary_or_text=row["binary_or_text"],
        source_ref=_source_ref_from_row(row),
    )


def _dicom_media_type_from_row(row: sqlite3.Row) -> DicomMediaType:
    return DicomMediaType(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        media_type=str(row["media_type"]),
        service_context=row["service_context"],
        transfer_syntax_constraints=tuple(
            json.loads(str(row["transfer_syntax_constraints_json"]))
        ),
        directions=tuple(json.loads(str(row["directions_json"]))),
        source_ref=_source_ref_from_row(row),
    )


def _dicomweb_transaction_from_row(row: sqlite3.Row) -> DicomwebTransaction:
    return DicomwebTransaction(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        transaction_name=str(row["transaction_name"]),
        resource_category=row["resource_category"],
        http_method=str(row["http_method"]),
        route_template=str(row["route_template"]),
        request_constraints=tuple(json.loads(str(row["request_constraints_json"]))),
        response_constraints=tuple(json.loads(str(row["response_constraints_json"]))),
        status_codes=tuple(json.loads(str(row["status_codes_json"]))),
        media_type_refs=tuple(json.loads(str(row["media_type_refs_json"]))),
        source_ref=_source_ref_from_row(row),
    )


def _coded_concept_from_row(row: sqlite3.Row) -> CodedConcept:
    return CodedConcept(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        code_value=str(row["code_value"]),
        coding_scheme_designator=str(row["coding_scheme_designator"]),
        coding_scheme_version=str(row["coding_scheme_version"]),
        code_meaning=str(row["code_meaning"]),
        source_ref=_source_ref_from_row(row),
    )


def _context_group_from_row(row: sqlite3.Row) -> ContextGroup:
    return ContextGroup(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        cid=str(row["cid"]),
        name=str(row["name"]),
        extensibility=row["extensibility"],
        version=row["version"],
        source_ref=_source_ref_from_row(row),
    )


def _context_group_row_from_row(row: sqlite3.Row) -> ContextGroupRow:
    return ContextGroupRow(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        context_group_id=str(row["context_group_id"]),
        row_order=int(row["row_order"]),
        coding_scheme_designator=row["coding_scheme_designator"],
        coding_scheme_version=row["coding_scheme_version"],
        code_value=row["code_value"],
        code_meaning=row["code_meaning"],
        include_cid=row["include_cid"],
        source_ref=_source_ref_from_row(row),
    )


def _sr_template_from_row(row: sqlite3.Row) -> SRTemplate:
    return SRTemplate(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        tid=str(row["tid"]),
        name=str(row["name"]),
        extensibility=row["extensibility"],
        source_ref=_source_ref_from_row(row),
    )


def _sr_template_row_from_row(row: sqlite3.Row) -> SRTemplateRow:
    return SRTemplateRow(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        sr_template_id=str(row["sr_template_id"]),
        row_order=int(row["row_order"]),
        relationship_type=row["relationship_type"],
        value_type=row["value_type"],
        concept_name=row["concept_name"],
        cardinality=row["cardinality"],
        condition_text=row["condition_text"],
        condition_id=row["condition_id"],
        include_tid=row["include_tid"],
        source_ref=_source_ref_from_row(row),
    )


def _iod_from_row(row: sqlite3.Row) -> IOD:
    return IOD(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        name=str(row["name"]),
        keyword=row["keyword"],
        iod_type=row["iod_type"],
        part=str(row["part"]),
        section=row["section"],
        source_ref=_source_ref_from_row(row),
    )


def _module_from_row(row: sqlite3.Row) -> Module:
    return Module(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        name=str(row["name"]),
        section=row["section"],
        description=row["description"],
        source_ref=_source_ref_from_row(row),
    )


def _macro_from_row(row: sqlite3.Row) -> Macro:
    return Macro(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        name=str(row["name"]),
        table_id=row["table_id"],
        section=row["section"],
        macro_kind=row["macro_kind"],
        source_ref=_source_ref_from_row(row),
    )


def _source_ref_from_prefixed_row(row: sqlite3.Row, prefix: str) -> SourceRef:
    return SourceRef(
        id=str(row[f"{prefix}_source_ref_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        part=str(row[f"{prefix}_source_part"]),
        section=row[f"{prefix}_source_section"],
        table_id=row[f"{prefix}_source_table_id"],
        xml_id=row[f"{prefix}_source_xml_id"],
        title=row[f"{prefix}_source_title"],
        canonical_url=row[f"{prefix}_source_url"],
    )


def _data_element_from_prefixed_row(row: sqlite3.Row, prefix: str) -> DataElement:
    return DataElement(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        tag=str(row[f"{prefix}_tag"]),
        group_pattern=str(row[f"{prefix}_group_pattern"]),
        element_pattern=str(row[f"{prefix}_element_pattern"]),
        is_range=bool(row[f"{prefix}_is_range"]),
        name=str(row[f"{prefix}_name"]),
        keyword=row[f"{prefix}_keyword"],
        vr=row[f"{prefix}_vr"],
        vm=row[f"{prefix}_vm"],
        retired=bool(row[f"{prefix}_retired"]),
        retired_in_or_last_seen=row[f"{prefix}_retired_in_or_last_seen"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _uid_from_prefixed_row(row: sqlite3.Row, prefix: str) -> UIDRegistryEntry:
    return UIDRegistryEntry(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        uid_value=str(row[f"{prefix}_uid_value"]),
        uid_name=str(row[f"{prefix}_uid_name"]),
        uid_keyword=row[f"{prefix}_uid_keyword"],
        uid_type=str(row[f"{prefix}_uid_type"]),
        part=row[f"{prefix}_part"],
        retired=bool(row[f"{prefix}_retired"]),
        retired_in_or_last_seen=row[f"{prefix}_retired_in_or_last_seen"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _optional_bool(value: object) -> bool | None:
    return None if value is None else bool(value)


def _transfer_syntax_detail_from_prefixed_row(
    row: sqlite3.Row,
) -> TransferSyntaxDetail:
    return TransferSyntaxDetail(
        id=str(row["detail_id"]),
        edition_id=str(row["detail_edition_id"]),
        uid_registry_entry_id=str(row["detail_uid_registry_entry_id"]),
        uid_value=str(row["detail_uid_value"]),
        explicit_vr=_optional_bool(row["detail_explicit_vr"]),
        endian=row["detail_endian"],
        encapsulated=_optional_bool(row["detail_encapsulated"]),
        compression_family=row["detail_compression_family"],
        encoding_notes=tuple(json.loads(str(row["detail_encoding_notes_json"]))),
        source_ref=_source_ref_from_prefixed_row(row, "detail"),
    )


def _attribute_value_term_from_prefixed_row(row: sqlite3.Row) -> AttributeValueTerm:
    return AttributeValueTerm(
        id=str(row["term_id"]),
        edition_id=str(row["term_edition_id"]),
        attribute_use_id=row["term_attribute_use_id"],
        data_element_id=row["term_data_element_id"],
        context_label=row["term_context_label"],
        term_kind=str(row["term_term_kind"]),
        value=str(row["term_value"]),
        meaning=row["term_meaning"],
        source_ref=_source_ref_from_prefixed_row(row, "term"),
    )


def _condition_from_prefixed_row(row: sqlite3.Row, prefix: str) -> Condition:
    return Condition(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        condition_kind=row[f"{prefix}_condition_kind"],
        raw_text=str(row[f"{prefix}_raw_text"]),
        normalized_text=row[f"{prefix}_normalized_text"],
        machine_status=str(row[f"{prefix}_machine_status"]),
        expression_json=row[f"{prefix}_expression_json"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _module_from_prefixed_row(row: sqlite3.Row, prefix: str) -> Module:
    return Module(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        name=str(row[f"{prefix}_name"]),
        section=row[f"{prefix}_section"],
        description=row[f"{prefix}_description"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _macro_from_prefixed_row(row: sqlite3.Row, prefix: str) -> Macro:
    return Macro(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        name=str(row[f"{prefix}_name"]),
        table_id=row[f"{prefix}_table_id"],
        section=row[f"{prefix}_section"],
        macro_kind=row[f"{prefix}_macro_kind"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _service_class_from_prefixed_row(row: sqlite3.Row, prefix: str) -> ServiceClass:
    return ServiceClass(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        name=str(row[f"{prefix}_name"]),
        section=row[f"{prefix}_section"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _sop_class_from_prefixed_row(row: sqlite3.Row, prefix: str) -> SOPClass:
    return SOPClass(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        name=str(row[f"{prefix}_name"]),
        uid_value=str(row[f"{prefix}_uid_value"]),
        service_class_id=row[f"{prefix}_service_class_id"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _iod_from_prefixed_row(row: sqlite3.Row, prefix: str) -> IOD:
    return IOD(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        name=str(row[f"{prefix}_name"]),
        keyword=row[f"{prefix}_keyword"],
        iod_type=row[f"{prefix}_iod_type"],
        part=str(row[f"{prefix}_part"]),
        section=row[f"{prefix}_section"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _iod_module_use_from_prefixed_row(row: sqlite3.Row) -> IODModuleUse:
    return IODModuleUse(
        id=str(row["use_id"]),
        edition_id=str(row["use_edition_id"]),
        iod_id=str(row["use_iod_id"]),
        information_entity=row["use_information_entity"],
        module_id=str(row["use_module_id"]),
        usage=str(row["use_usage"]),
        usage_condition_text=row["use_usage_condition_text"],
        condition_id=row["use_condition_id"],
        source_ref=_source_ref_from_prefixed_row(row, "use"),
    )


def _iod_functional_group_use_from_prefixed_row(
    row: sqlite3.Row,
) -> IODFunctionalGroupUse:
    return IODFunctionalGroupUse(
        id=str(row["use_id"]),
        edition_id=str(row["use_edition_id"]),
        iod_id=str(row["use_iod_id"]),
        macro_id=str(row["use_macro_id"]),
        usage=str(row["use_usage"]),
        usage_condition_text=row["use_usage_condition_text"],
        condition_id=row["use_condition_id"],
        source_ref=_source_ref_from_prefixed_row(row, "use"),
    )


def _sop_class_iod_from_prefixed_row(row: sqlite3.Row, prefix: str) -> SOPClassIOD:
    return SOPClassIOD(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        sop_class_id=str(row[f"{prefix}_sop_class_id"]),
        iod_id=str(row[f"{prefix}_iod_id"]),
        resolution=str(row[f"{prefix}_resolution"]),
        resolution_warning=row[f"{prefix}_resolution_warning"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _attribute_use_from_prefixed_row(row: sqlite3.Row) -> AttributeUse:
    return AttributeUse(
        id=str(row["attribute_id"]),
        edition_id=str(row["attribute_edition_id"]),
        owner_type=str(row["attribute_owner_type"]),
        owner_id=str(row["attribute_owner_id"]),
        parent_attribute_use_id=row["attribute_parent_attribute_use_id"],
        row_kind=str(row["attribute_row_kind"]),
        attribute_tag=row["attribute_attribute_tag"],
        attribute_keyword=row["attribute_attribute_keyword"],
        attribute_name=row["attribute_attribute_name"],
        type_designation=row["attribute_type_designation"],
        description_text=row["attribute_description_text"],
        condition_id=row["attribute_condition_id"],
        included_macro_id=row["attribute_included_macro_id"],
        include_target_text=row["attribute_include_target_text"],
        sequence_depth=int(row["attribute_sequence_depth"]),
        row_order=int(row["attribute_row_order"]),
        source_ref=_source_ref_from_prefixed_row(row, "attribute"),
    )
