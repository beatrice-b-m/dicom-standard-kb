"""Persisted DocBook text retrieval and search."""

from __future__ import annotations

import sqlite3

from dicom_kb.db.repositories._rows import _doc_node_from_row
from dicom_kb.db.repositories.records import DocumentSearchResult
from dicom_kb.ir.models import (
    DocNode,
)


class DocumentRepository:
    """Lookup persisted DocBook structure for citation-preserving retrieval."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_node(
        self, *, part: str, section_or_anchor: str, edition: str
    ) -> DocNode | None:
        """Return a document node by exact xml:id, anchor, or section number."""
        row = self.connection.execute(
            """
            SELECT dn.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM doc_node dn
            JOIN source_ref sr ON sr.id = dn.source_ref_id
            WHERE dn.edition_id = ?
              AND dn.part = ?
              AND (
                dn.xml_id = ?
                OR dn.anchor = ?
                OR dn.number = ?
              )
            ORDER BY
              CASE
                WHEN dn.xml_id = ? THEN 0
                WHEN dn.anchor = ? THEN 1
                ELSE 2
              END,
              dn.ordinal
            LIMIT 1
            """,
            (
                edition,
                part,
                section_or_anchor,
                section_or_anchor,
                section_or_anchor,
                section_or_anchor,
                section_or_anchor,
            ),
        ).fetchone()
        return _doc_node_from_row(row) if row else None

    def list_tables_under_node(self, node: DocNode, *, edition: str) -> list[DocNode]:
        """Return table nodes at or below a document node in document order."""
        if node.node_type == "table":
            return [node]
        rows = self.connection.execute(
            """
            WITH RECURSIVE descendants(id) AS (
              VALUES (?)
              UNION ALL
              SELECT child.id
              FROM doc_node child
              JOIN descendants parent ON parent.id = child.parent_id
              WHERE child.edition_id = ?
            )
            SELECT dn.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM doc_node dn
            JOIN descendants d ON d.id = dn.id
            JOIN source_ref sr ON sr.id = dn.source_ref_id
            WHERE dn.edition_id = ?
              AND dn.node_type = 'table'
            ORDER BY dn.ordinal
            """,
            (node.id, edition, edition),
        ).fetchall()
        return [_doc_node_from_row(row) for row in rows]

    def search_text(
        self,
        *,
        fts_query: str,
        edition: str,
        part_filter: str | None = None,
        limit: int = 10,
    ) -> list[DocumentSearchResult]:
        """Search persisted DocBook text with SQLite FTS5."""
        rows = self.connection.execute(
            """
            SELECT dn.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url,
                   snippet(doc_node_fts, -1, '', '', '...', 32) AS snippet,
                   bm25(doc_node_fts) AS rank
            FROM doc_node_fts
            JOIN doc_node dn ON dn.id = doc_node_fts.node_id
            JOIN source_ref sr ON sr.id = dn.source_ref_id
            WHERE doc_node_fts MATCH ?
              AND doc_node_fts.edition_id = ?
              AND (? IS NULL OR doc_node_fts.part = ?)
            ORDER BY rank, dn.part, dn.ordinal
            LIMIT ?
            """,
            (fts_query, edition, part_filter, part_filter, limit),
        ).fetchall()
        return [
            DocumentSearchResult(
                node=_doc_node_from_row(row),
                snippet=str(row["snippet"] or ""),
            )
            for row in rows
        ]
