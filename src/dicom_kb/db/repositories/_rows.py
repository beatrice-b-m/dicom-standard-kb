"""Internal conversion of SQLite rows into canonical IR models."""

from __future__ import annotations

import json
import sqlite3

from dicom_kb.ir.models import (
    DataElement,
    DocNode,
    SourceRef,
    TransferSyntaxDetail,
    UIDRegistryEntry,
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


def _transfer_syntax_detail_from_row(row: sqlite3.Row) -> TransferSyntaxDetail:
    return TransferSyntaxDetail(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        uid_value=str(row["uid_value"]),
        vr_encoding=str(row["vr_encoding"]),
        byte_order=str(row["byte_order"]),
        pixel_data=str(row["pixel_data"]),
        deflate=row["deflate"],
        section_xml_id=str(row["section_xml_id"]),
        see_also=tuple(json.loads(str(row["see_also_json"]))),
    )
