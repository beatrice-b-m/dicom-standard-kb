"""Internal conversion of SQLite rows into canonical IR models."""

from __future__ import annotations

import json
import sqlite3

from dicom_kb.ir.models import (
    DataElement,
    DicomMediaType,
    DicomwebTransaction,
    DocNode,
    SourceRef,
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
        markdown=row["markdown"],
        informative=bool(row["informative"]),
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
