"""PS3.6 registry and PS3.5 encoding lookups."""

from __future__ import annotations

import sqlite3
from typing import cast

from dicom_kb.db.repositories._rows import (
    _data_element_from_row,
    _transfer_syntax_detail_from_prefixed_row,
    _uid_from_prefixed_row,
    _uid_from_row,
    _vr_definition_from_row,
)
from dicom_kb.db.repositories.records import TransferSyntaxDetailRecord
from dicom_kb.ir.models import (
    DataElement,
    UIDRegistryEntry,
    VRDefinition,
)
from dicom_kb.ir.validators import IdentifierValidationError, normalize_tag, tag_matches


class DataElementRepository:
    """Lookup PS3.6 data elements by tag or keyword."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_by_tag_or_keyword(
        self, tag_or_keyword: str, *, edition: str
    ) -> tuple[DataElement | None, str | None]:
        """Return an exact tag, keyword, or name record and optional warning."""
        try:
            tag = normalize_tag(tag_or_keyword)
        except IdentifierValidationError:
            row = self.connection.execute(
                """
                SELECT de.*, sr.part AS source_part, sr.section AS source_section,
                       sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                       sr.title AS source_title, sr.canonical_url AS source_url
                FROM data_element de
                JOIN source_ref sr ON sr.id = de.source_ref_id
                WHERE de.edition_id = ?
                  AND (lower(de.keyword) = lower(?) OR lower(de.name) = lower(?))
                """,
                (edition, tag_or_keyword, tag_or_keyword),
            ).fetchone()
            return (_data_element_from_row(row) if row else None), None

        row = self._find_exact_tag(tag, edition)
        if row is not None:
            return _data_element_from_row(row), None

        for candidate in self._range_rows(edition):
            if tag_matches(str(candidate["tag"]), tag):
                warning = f"concrete tag {tag} matched range row {candidate['tag']}"
                return _data_element_from_row(candidate), warning
        return None, None

    def _find_exact_tag(self, tag: str, edition: str) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT de.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM data_element de
            JOIN source_ref sr ON sr.id = de.source_ref_id
            WHERE de.edition_id = ? AND de.tag = ?
            """,
            (edition, tag),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def _range_rows(self, edition: str) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT de.*, sr.part AS source_part, sr.section AS source_section,
                       sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                       sr.title AS source_title, sr.canonical_url AS source_url
                FROM data_element de
                JOIN source_ref sr ON sr.id = de.source_ref_id
                WHERE de.edition_id = ? AND de.is_range = 1
                """,
                (edition,),
            )
        )


class UIDRepository:
    """Lookup PS3.6 UID registry entries by UID value or keyword."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_by_uid_or_keyword(
        self, uid_or_keyword: str, *, edition: str
    ) -> UIDRegistryEntry | None:
        """Return a UID registry entry by value or keyword."""
        row = self.connection.execute(
            """
            SELECT uid.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM uid_registry_entry uid
            JOIN source_ref sr ON sr.id = uid.source_ref_id
            WHERE uid.edition_id = ?
              AND (uid.uid_value = ? OR lower(uid.uid_keyword) = lower(?))
            """,
            (edition, uid_or_keyword, uid_or_keyword),
        ).fetchone()
        return _uid_from_row(row) if row else None


class Part05Repository:
    """Lookup imported PS3.5 encoding semantics."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_vr(self, vr: str, *, edition: str) -> VRDefinition | None:
        """Return a VR definition by exact VR code."""
        row = self.connection.execute(
            """
            SELECT vr.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM vr_definition vr
            JOIN source_ref sr ON sr.id = vr.source_ref_id
            WHERE vr.edition_id = ? AND upper(vr.vr) = upper(?)
            """,
            (edition, vr),
        ).fetchone()
        return _vr_definition_from_row(row) if row else None

    def find_transfer_syntax(
        self, uid_or_keyword: str, *, edition: str
    ) -> TransferSyntaxDetailRecord | None:
        """Return encoding details joined to a transfer syntax UID row."""
        row = self.connection.execute(
            """
            SELECT
              detail.id AS detail_id,
              detail.edition_id AS detail_edition_id,
              detail.uid_registry_entry_id AS detail_uid_registry_entry_id,
              detail.uid_value AS detail_uid_value,
              detail.explicit_vr AS detail_explicit_vr,
              detail.endian AS detail_endian,
              detail.encapsulated AS detail_encapsulated,
              detail.compression_family AS detail_compression_family,
              detail.encoding_notes_json AS detail_encoding_notes_json,
              detail.source_ref_id AS detail_source_ref_id,
              detail_sr.part AS detail_source_part,
              detail_sr.section AS detail_source_section,
              detail_sr.table_id AS detail_source_table_id,
              detail_sr.xml_id AS detail_source_xml_id,
              detail_sr.title AS detail_source_title,
              detail_sr.canonical_url AS detail_source_url,
              uid.id AS uid_id,
              uid.edition_id AS uid_edition_id,
              uid.uid_value AS uid_uid_value,
              uid.uid_name AS uid_uid_name,
              uid.uid_keyword AS uid_uid_keyword,
              uid.uid_type AS uid_uid_type,
              uid.part AS uid_part,
              uid.retired AS uid_retired,
              uid.retired_in_or_last_seen AS uid_retired_in_or_last_seen,
              uid.source_ref_id AS uid_source_ref_id,
              uid_sr.part AS uid_source_part,
              uid_sr.section AS uid_source_section,
              uid_sr.table_id AS uid_source_table_id,
              uid_sr.xml_id AS uid_source_xml_id,
              uid_sr.title AS uid_source_title,
              uid_sr.canonical_url AS uid_source_url
            FROM transfer_syntax_detail detail
            JOIN source_ref detail_sr ON detail_sr.id = detail.source_ref_id
            JOIN uid_registry_entry uid ON uid.id = detail.uid_registry_entry_id
            JOIN source_ref uid_sr ON uid_sr.id = uid.source_ref_id
            WHERE detail.edition_id = ?
              AND (
                detail.uid_value = ?
                OR lower(uid.uid_keyword) = lower(?)
                OR lower(uid.uid_name) = lower(?)
              )
            """,
            (edition, uid_or_keyword, uid_or_keyword, uid_or_keyword),
        ).fetchone()
        if row is None:
            return None
        return TransferSyntaxDetailRecord(
            detail=_transfer_syntax_detail_from_prefixed_row(row),
            uid=_uid_from_prefixed_row(row, "uid"),
        )
