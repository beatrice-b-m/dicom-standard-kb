"""PS3.10 media and PS3.18 transaction lookups."""

from __future__ import annotations

import re
import sqlite3

from dicom_kb.db.repositories._rows import (
    _dicom_media_type_from_row,
    _dicomweb_transaction_from_row,
)
from dicom_kb.ir.models import (
    DicomMediaType,
    DicomwebTransaction,
)


class Part10Repository:
    """Lookup imported PS3.10 media storage semantics."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_media_types(
        self, media_type_or_context: str, *, edition: str
    ) -> list[DicomMediaType]:
        """Return media-type rows matching an exact type or context."""
        normalized = media_type_or_context.strip().casefold()
        rows = self.connection.execute(
            """
            SELECT media.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM dicom_media_type media
            JOIN source_ref sr ON sr.id = media.source_ref_id
            WHERE media.edition_id = ?
            ORDER BY media.media_type, media.service_context, media.id
            """,
            (edition,),
        ).fetchall()
        records = [_dicom_media_type_from_row(row) for row in rows]
        exact_media_type = [
            record for record in records if record.media_type.casefold() == normalized
        ]
        if exact_media_type:
            canonical_instance_media = [
                record
                for record in exact_media_type
                if (record.service_context or "").casefold() == "instance media types"
            ]
            if len(canonical_instance_media) == 1:
                return canonical_instance_media
            return exact_media_type
        return [
            record for record in records if _media_context_matches(record, normalized)
        ]


class Part18Repository:
    """Lookup imported PS3.18 DICOMweb transaction semantics."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_dicomweb_transactions(
        self, name_or_route: str, *, edition: str
    ) -> list[DicomwebTransaction]:
        """Return transaction rows matching an exact name or route template."""
        normalized = name_or_route.strip()
        rows = self.connection.execute(
            """
            SELECT txn.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM dicomweb_transaction txn
            JOIN source_ref sr ON sr.id = txn.source_ref_id
            WHERE txn.edition_id = ?
            ORDER BY txn.transaction_name, txn.http_method, txn.route_template, txn.id
            """,
            (edition,),
        ).fetchall()
        records = [_dicomweb_transaction_from_row(row) for row in rows]
        exact_name = [
            record
            for record in records
            if record.transaction_name.casefold() == normalized.casefold()
        ]
        if exact_name:
            return exact_name
        normalized_route = _canonical_route_template(normalized)
        return [
            record
            for record in records
            if _canonical_route_template(record.route_template) == normalized_route
        ]


def _media_context_matches(record: DicomMediaType, normalized: str) -> bool:
    context = record.service_context.casefold() if record.service_context else ""
    directions = {direction.casefold() for direction in record.directions}
    return normalized == context or normalized in directions


def _canonical_route_template(route_template: str) -> str:
    placeholder_index = 0

    def replace_placeholder(_match: re.Match[str]) -> str:
        nonlocal placeholder_index
        placeholder_index += 1
        return f"{{var{placeholder_index}}}"

    return re.sub(r"\{[^}/]+\}", replace_placeholder, route_template.strip())
