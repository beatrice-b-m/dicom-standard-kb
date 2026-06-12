"""SQLite repositories for exact deterministic lookups."""

from __future__ import annotations

import sqlite3
from typing import cast

from dicom_kb.ir.models import DataElement, SourceRef, UIDRegistryEntry
from dicom_kb.ir.validators import IdentifierValidationError, normalize_tag, tag_matches


class DataElementRepository:
    """Lookup PS3.6 data elements by tag or keyword."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_by_tag_or_keyword(
        self, tag_or_keyword: str, *, edition: str
    ) -> tuple[DataElement | None, str | None]:
        """Return an exact record and optional range-match warning."""
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
                WHERE de.edition_id = ? AND lower(de.keyword) = lower(?)
                """,
                (edition, tag_or_keyword),
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
