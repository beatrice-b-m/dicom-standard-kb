"""Persisted DocBook text retrieval and search."""

from __future__ import annotations

import sqlite3

from dicom_kb.db.repositories._rows import _doc_node_from_row
from dicom_kb.db.repositories.records import DocumentSearchResult
from dicom_kb.ir.models import (
    DocNode,
)

_NODE_COLUMNS = """
    dn.*, sr.part AS source_part, sr.section AS source_section,
    sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
    sr.title AS source_title, sr.canonical_url AS source_url
"""


class DocumentRepository:
    """Lookup persisted DocBook structure for citation-preserving retrieval."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def nodes_by_label(
        self,
        *,
        label: str,
        node_types: tuple[str, ...],
        edition: str,
        part: str | None = None,
    ) -> list[DocNode]:
        """Return sections or tables whose label matches, in part order."""
        placeholders = ", ".join("?" for _ in node_types)
        rows = self.connection.execute(
            f"""
            SELECT {_NODE_COLUMNS}
            FROM doc_node dn
            JOIN source_ref sr ON sr.id = dn.source_ref_id
            WHERE dn.edition_id = ?
              AND dn.number = ? COLLATE NOCASE
              AND dn.node_type IN ({placeholders})
              AND (? IS NULL OR dn.part = ?)
            ORDER BY CAST(substr(dn.part, 5) AS INTEGER), dn.ordinal
            """,
            (edition, label, *node_types, part, part),
        ).fetchall()
        return [_doc_node_from_row(row) for row in rows]

    def nodes_by_title(
        self,
        *,
        title: str,
        node_types: tuple[str, ...],
        edition: str,
        part: str | None = None,
    ) -> list[DocNode]:
        """Return sections or tables whose title matches, in part order."""
        placeholders = ", ".join("?" for _ in node_types)
        rows = self.connection.execute(
            f"""
            SELECT {_NODE_COLUMNS}
            FROM doc_node dn
            JOIN source_ref sr ON sr.id = dn.source_ref_id
            WHERE dn.edition_id = ?
              AND dn.title = ? COLLATE NOCASE
              AND dn.node_type IN ({placeholders})
              AND (? IS NULL OR dn.part = ?)
            ORDER BY CAST(substr(dn.part, 5) AS INTEGER), dn.ordinal
            """,
            (edition, title, *node_types, part, part),
        ).fetchall()
        return [_doc_node_from_row(row) for row in rows]

    def node_by_id(self, node_id: str) -> DocNode | None:
        """Return one node by its database id."""
        row = self.connection.execute(
            f"""
            SELECT {_NODE_COLUMNS}
            FROM doc_node dn
            JOIN source_ref sr ON sr.id = dn.source_ref_id
            WHERE dn.id = ?
            """,
            (node_id,),
        ).fetchone()
        return _doc_node_from_row(row) if row else None

    def nodes_by_xml_id(
        self, *, xml_id: str, edition: str, part: str | None = None
    ) -> list[DocNode]:
        """Return nodes with an exact xml:id, in part order."""
        rows = self.connection.execute(
            f"""
            SELECT {_NODE_COLUMNS}
            FROM doc_node dn
            JOIN source_ref sr ON sr.id = dn.source_ref_id
            WHERE dn.edition_id = ?
              AND dn.xml_id = ?
              AND (? IS NULL OR dn.part = ?)
            ORDER BY CAST(substr(dn.part, 5) AS INTEGER)
            """,
            (edition, xml_id, part, part),
        ).fetchall()
        return [_doc_node_from_row(row) for row in rows]

    def descendant_sections(self, node: DocNode, *, edition: str) -> list[DocNode]:
        """Return every section below a node, in document order."""
        rows = self.connection.execute(
            f"""
            WITH RECURSIVE descendants(id) AS (
              SELECT id FROM doc_node WHERE parent_id = ? AND edition_id = ?
              UNION ALL
              SELECT child.id
              FROM doc_node child
              JOIN descendants parent ON parent.id = child.parent_id
            )
            SELECT {_NODE_COLUMNS}
            FROM doc_node dn
            JOIN descendants d ON d.id = dn.id
            JOIN source_ref sr ON sr.id = dn.source_ref_id
            WHERE dn.node_type IN ('chapter', 'section')
            ORDER BY dn.ordinal
            """,
            (node.id, edition),
        ).fetchall()
        return [_doc_node_from_row(row) for row in rows]

    def subtree_chars(self, node: DocNode) -> int:
        """Return the stored markdown size of everything below a node."""
        row = self.connection.execute(
            """
            WITH RECURSIVE descendants(id) AS (
              SELECT id FROM doc_node WHERE parent_id = ?
              UNION ALL
              SELECT child.id
              FROM doc_node child
              JOIN descendants parent ON parent.id = child.parent_id
            )
            SELECT coalesce(sum(length(dn.markdown)), 0) AS size
            FROM doc_node dn
            JOIN descendants d ON d.id = dn.id
            """,
            (node.id,),
        ).fetchone()
        return int(row["size"])

    def child_sections(self, node: DocNode) -> list[DocNode]:
        """Return the sections directly below a node, in document order."""
        rows = self.connection.execute(
            f"""
            SELECT {_NODE_COLUMNS}
            FROM doc_node dn
            JOIN source_ref sr ON sr.id = dn.source_ref_id
            WHERE dn.parent_id = ? AND dn.node_type IN ('chapter', 'section')
            ORDER BY dn.ordinal
            """,
            (node.id,),
        ).fetchall()
        return [_doc_node_from_row(row) for row in rows]

    def table_markdown(
        self, *, part: str, xml_ids: list[str], edition: str
    ) -> dict[str, str]:
        """Return the stored markdown of tables in one part, keyed by xml:id."""
        if not xml_ids:
            return {}
        placeholders = ", ".join("?" for _ in xml_ids)
        rows = self.connection.execute(
            f"""
            SELECT xml_id, markdown
            FROM doc_node
            WHERE edition_id = ? AND part = ? AND node_type = 'table'
              AND xml_id IN ({placeholders})
            """,
            (edition, part, *xml_ids),
        ).fetchall()
        return {str(row["xml_id"]): str(row["markdown"] or "") for row in rows}

    def labels_with_prefix(
        self, *, prefix: str, edition: str, part: str | None = None, limit: int = 8
    ) -> list[DocNode]:
        """Return labelled nodes whose label starts with a prefix."""
        rows = self.connection.execute(
            f"""
            SELECT {_NODE_COLUMNS}
            FROM doc_node dn
            JOIN source_ref sr ON sr.id = dn.source_ref_id
            WHERE dn.edition_id = ?
              AND dn.number LIKE ? ESCAPE '\\'
              AND (? IS NULL OR dn.part = ?)
            ORDER BY length(dn.number), CAST(substr(dn.part, 5) AS INTEGER),
                     dn.ordinal
            LIMIT ?
            """,
            (edition, _like_prefix(prefix), part, part, limit),
        ).fetchall()
        return [_doc_node_from_row(row) for row in rows]

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
        """Search persisted DocBook text with SQLite FTS5.

        Title matches weigh more than body matches. Normative text comes
        before informative annexes among the best-ranked candidates.
        """
        rows = self.connection.execute(
            f"""
            SELECT {_NODE_COLUMNS},
                   snippet(doc_node_fts, 4, '', '', '…', 14) AS snippet,
                   bm25(doc_node_fts, 0.0, 0.0, 0.0, 6.0, 1.0) AS rank
            FROM doc_node_fts
            JOIN doc_node dn ON dn.id = doc_node_fts.node_id
            JOIN source_ref sr ON sr.id = dn.source_ref_id
            WHERE doc_node_fts MATCH ?
              AND doc_node_fts.edition_id = ?
              AND (? IS NULL OR doc_node_fts.part = ?)
            ORDER BY rank, dn.part, dn.ordinal
            LIMIT ?
            """,
            (fts_query, edition, part_filter, part_filter, max(limit * 4, 40)),
        ).fetchall()
        results = [
            DocumentSearchResult(
                node=_doc_node_from_row(row),
                snippet=str(row["snippet"] or ""),
            )
            for row in rows
        ]
        results.sort(key=lambda result: result.node.informative)
        return results[:limit]


def _like_prefix(prefix: str) -> str:
    escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"
