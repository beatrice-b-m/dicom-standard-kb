"""PS3.6 registry and PS3.5 transfer syntax lookups."""

from __future__ import annotations

import sqlite3
from typing import cast

from dicom_kb.db.repositories._rows import (
    _data_element_from_row,
    _transfer_syntax_detail_from_row,
    _uid_from_row,
)
from dicom_kb.ir.models import DataElement, TransferSyntaxDetail, UIDRegistryEntry
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
        """Return a UID registry entry by value, keyword or exact name."""
        row = self.connection.execute(
            """
            SELECT uid.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM uid_registry_entry uid
            JOIN source_ref sr ON sr.id = uid.source_ref_id
            WHERE uid.edition_id = ?
              AND (
                uid.uid_value = ?
                OR lower(uid.uid_keyword) = lower(?)
                OR lower(uid.uid_name) = lower(?)
              )
            """,
            (edition, uid_or_keyword, uid_or_keyword, uid_or_keyword),
        ).fetchone()
        return _uid_from_row(row) if row else None


class TransferSyntaxRepository:
    """Lookup the PS3.5 encoding facts of a transfer syntax."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find(self, uid: str, *, edition: str) -> TransferSyntaxDetail | None:
        """Return the encoding facts for a transfer syntax UID."""
        row = self.connection.execute(
            "SELECT * FROM transfer_syntax_detail WHERE edition_id = ? "
            "AND uid_value = ?",
            (edition, uid),
        ).fetchone()
        return _transfer_syntax_detail_from_row(row) if row else None
