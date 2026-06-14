"""SQLite repositories for exact deterministic lookups."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import cast

from dicom_kb.ir.models import (
    IOD,
    AttributeUse,
    AttributeValueTerm,
    Condition,
    DataElement,
    DocNode,
    IODFunctionalGroupUse,
    IODModuleUse,
    Macro,
    Module,
    ServiceClass,
    SOPClass,
    SOPClassIOD,
    SourceRef,
    TransferSyntaxDetail,
    UIDRegistryEntry,
    VRDefinition,
)
from dicom_kb.ir.validators import IdentifierValidationError, normalize_tag, tag_matches


@dataclass(frozen=True)
class IODModuleUseRecord:
    """A module-use edge joined to its module definition."""

    use: IODModuleUse
    module: Module
    condition: Condition | None = None


@dataclass(frozen=True)
class IODFunctionalGroupUseRecord:
    """A functional-group-use edge joined to its macro definition."""

    use: IODFunctionalGroupUse
    macro: Macro
    condition: Condition | None = None


@dataclass(frozen=True)
class AttributeUseRecord:
    """An attribute-use row with query-time expansion context."""

    attribute_use: AttributeUse
    owner_type: str
    owner_name: str
    included_macro: Macro | None = None
    condition: Condition | None = None
    expanded_from_include: AttributeUse | None = None
    macro_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class SOPClassIODRecord:
    """A SOP Class to IOD edge joined to the target IOD."""

    edge: SOPClassIOD
    iod: IOD


@dataclass(frozen=True)
class DocumentSearchResult:
    """A matched DocBook node with a short full-text search snippet."""

    node: DocNode
    snippet: str


@dataclass(frozen=True)
class AttributeValueTermRecord:
    """A value term joined to its optional PS3.6 data element."""

    term: AttributeValueTerm
    data_element: DataElement | None = None


@dataclass(frozen=True)
class TransferSyntaxDetailRecord:
    """A transfer-syntax detail row joined to its PS3.6 UID registry entry."""

    detail: TransferSyntaxDetail
    uid: UIDRegistryEntry


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


class AttributeValueTermRepository:
    """Lookup parsed enumerated values and defined terms."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_terms_for_attribute(
        self,
        *,
        attribute: str,
        term_kind: str,
        edition: str,
        context: str | None = None,
    ) -> list[AttributeValueTermRecord]:
        """Return value terms linked to a PS3.6 attribute identity."""
        element, _warning = DataElementRepository(
            self.connection
        ).find_by_tag_or_keyword(attribute, edition=edition)
        if element is None:
            return []
        rows = self.connection.execute(
            """
            SELECT
              avt.id AS term_id,
              avt.edition_id AS term_edition_id,
              avt.attribute_use_id AS term_attribute_use_id,
              avt.data_element_id AS term_data_element_id,
              avt.context_label AS term_context_label,
              avt.term_kind AS term_term_kind,
              avt.value AS term_value,
              avt.meaning AS term_meaning,
              avt.source_ref_id AS term_source_ref_id,
              term_sr.part AS term_source_part,
              term_sr.section AS term_source_section,
              term_sr.table_id AS term_source_table_id,
              term_sr.xml_id AS term_source_xml_id,
              term_sr.title AS term_source_title,
              term_sr.canonical_url AS term_source_url,
              de.id AS data_element_id,
              de.edition_id AS data_element_edition_id,
              de.tag AS data_element_tag,
              de.group_pattern AS data_element_group_pattern,
              de.element_pattern AS data_element_element_pattern,
              de.is_range AS data_element_is_range,
              de.name AS data_element_name,
              de.keyword AS data_element_keyword,
              de.vr AS data_element_vr,
              de.vm AS data_element_vm,
              de.retired AS data_element_retired,
              de.retired_in_or_last_seen AS data_element_retired_in_or_last_seen,
              de.source_ref_id AS data_element_source_ref_id,
              de_sr.part AS data_element_source_part,
              de_sr.section AS data_element_source_section,
              de_sr.table_id AS data_element_source_table_id,
              de_sr.xml_id AS data_element_source_xml_id,
              de_sr.title AS data_element_source_title,
              de_sr.canonical_url AS data_element_source_url
            FROM attribute_value_term avt
            JOIN source_ref term_sr ON term_sr.id = avt.source_ref_id
            LEFT JOIN data_element de ON de.id = avt.data_element_id
            LEFT JOIN source_ref de_sr ON de_sr.id = de.source_ref_id
            LEFT JOIN attribute_use au ON au.id = avt.attribute_use_id
            LEFT JOIN module m ON m.id = au.owner_id AND au.owner_type = 'module'
            LEFT JOIN macro ma ON ma.id = au.owner_id AND au.owner_type = 'macro'
            WHERE avt.edition_id = ?
              AND avt.term_kind = ?
              AND avt.data_element_id = ?
              AND (
                ? IS NULL
                OR lower(avt.context_label) LIKE '%' || lower(?) || '%'
                OR lower(m.name) = lower(?)
                OR lower(ma.name) = lower(?)
              )
            ORDER BY avt.context_label, avt.value, avt.id
            """,
            (edition, term_kind, element.id, context, context, context, context),
        ).fetchall()
        return [
            AttributeValueTermRecord(
                term=_attribute_value_term_from_prefixed_row(row),
                data_element=(
                    _data_element_from_prefixed_row(row, "data_element")
                    if row["data_element_id"] is not None
                    else None
                ),
            )
            for row in rows
        ]


class Part03Repository:
    """Lookup and traverse imported PS3.3 IOD/module/macro graph records."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_iod_by_name_or_keyword(
        self, name_or_keyword: str, *, edition: str
    ) -> IOD | None:
        """Return an IOD by exact name or keyword."""
        row = self.connection.execute(
            """
            SELECT i.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM iod i
            JOIN source_ref sr ON sr.id = i.source_ref_id
            WHERE i.edition_id = ?
              AND (lower(i.name) = lower(?) OR lower(i.keyword) = lower(?))
            """,
            (edition, name_or_keyword, name_or_keyword),
        ).fetchone()
        return _iod_from_row(row) if row else None

    def find_module_by_name(self, name: str, *, edition: str) -> Module | None:
        """Return a module by exact name."""
        row = self.connection.execute(
            """
            SELECT m.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM module m
            JOIN source_ref sr ON sr.id = m.source_ref_id
            WHERE m.edition_id = ? AND lower(m.name) = lower(?)
            ORDER BY m.section IS NULL, m.section
            LIMIT 1
            """,
            (edition, name),
        ).fetchone()
        return _module_from_row(row) if row else None

    def find_macro_by_name_or_table(
        self, name_or_table: str, *, edition: str
    ) -> Macro | None:
        """Return a macro by exact name or table/xml id."""
        row = self.connection.execute(
            """
            SELECT m.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM macro m
            JOIN source_ref sr ON sr.id = m.source_ref_id
            WHERE m.edition_id = ?
              AND (lower(m.name) = lower(?) OR lower(m.table_id) = lower(?))
            """,
            (edition, name_or_table, name_or_table),
        ).fetchone()
        return _macro_from_row(row) if row else None

    def list_module_uses_for_iod(
        self, iod_id: str, *, edition: str
    ) -> list[IODModuleUseRecord]:
        """Return modules listed by an IOD in table order."""
        rows = self.connection.execute(
            """
            SELECT
              imu.id AS use_id,
              imu.edition_id AS use_edition_id,
              imu.iod_id AS use_iod_id,
              imu.information_entity AS use_information_entity,
              imu.module_id AS use_module_id,
              imu.usage AS use_usage,
              imu.usage_condition_text AS use_usage_condition_text,
              imu.condition_id AS use_condition_id,
              imu.source_ref_id AS use_source_ref_id,
              use_sr.part AS use_source_part,
              use_sr.section AS use_source_section,
              use_sr.table_id AS use_source_table_id,
              use_sr.xml_id AS use_source_xml_id,
              use_sr.title AS use_source_title,
              use_sr.canonical_url AS use_source_url,
              m.id AS module_id,
              m.edition_id AS module_edition_id,
              m.name AS module_name,
              m.section AS module_section,
              m.description AS module_description,
              m.source_ref_id AS module_source_ref_id,
              module_sr.part AS module_source_part,
              module_sr.section AS module_source_section,
              module_sr.table_id AS module_source_table_id,
              module_sr.xml_id AS module_source_xml_id,
              module_sr.title AS module_source_title,
              module_sr.canonical_url AS module_source_url,
              c.id AS condition_id,
              c.edition_id AS condition_edition_id,
              c.condition_kind AS condition_condition_kind,
              c.raw_text AS condition_raw_text,
              c.normalized_text AS condition_normalized_text,
              c.machine_status AS condition_machine_status,
              c.expression_json AS condition_expression_json,
              c.source_ref_id AS condition_source_ref_id,
              condition_sr.part AS condition_source_part,
              condition_sr.section AS condition_source_section,
              condition_sr.table_id AS condition_source_table_id,
              condition_sr.xml_id AS condition_source_xml_id,
              condition_sr.title AS condition_source_title,
              condition_sr.canonical_url AS condition_source_url
            FROM iod_module_use imu
            JOIN module m ON m.id = imu.module_id
            JOIN source_ref use_sr ON use_sr.id = imu.source_ref_id
            JOIN source_ref module_sr ON module_sr.id = m.source_ref_id
            LEFT JOIN condition c ON c.id = imu.condition_id
            LEFT JOIN source_ref condition_sr ON condition_sr.id = c.source_ref_id
            WHERE imu.edition_id = ? AND imu.iod_id = ?
            ORDER BY imu.id
            """,
            (edition, iod_id),
        ).fetchall()
        return [
            IODModuleUseRecord(
                use=_iod_module_use_from_prefixed_row(row),
                module=_module_from_prefixed_row(row, "module"),
                condition=(
                    _condition_from_prefixed_row(row, "condition")
                    if row["condition_id"] is not None
                    else None
                ),
            )
            for row in sorted(rows, key=lambda row: _id_order(str(row["use_id"])))
        ]

    def list_functional_group_uses_for_iod(
        self, iod_id: str, *, edition: str
    ) -> list[IODFunctionalGroupUseRecord]:
        """Return functional-group macros listed by an IOD in table order."""
        rows = self.connection.execute(
            """
            SELECT
              fg.id AS use_id,
              fg.edition_id AS use_edition_id,
              fg.iod_id AS use_iod_id,
              fg.macro_id AS use_macro_id,
              fg.usage AS use_usage,
              fg.usage_condition_text AS use_usage_condition_text,
              fg.condition_id AS use_condition_id,
              fg.source_ref_id AS use_source_ref_id,
              use_sr.part AS use_source_part,
              use_sr.section AS use_source_section,
              use_sr.table_id AS use_source_table_id,
              use_sr.xml_id AS use_source_xml_id,
              use_sr.title AS use_source_title,
              use_sr.canonical_url AS use_source_url,
              m.id AS macro_id,
              m.edition_id AS macro_edition_id,
              m.name AS macro_name,
              m.table_id AS macro_table_id,
              m.section AS macro_section,
              m.macro_kind AS macro_macro_kind,
              m.source_ref_id AS macro_source_ref_id,
              macro_sr.part AS macro_source_part,
              macro_sr.section AS macro_source_section,
              macro_sr.table_id AS macro_source_table_id,
              macro_sr.xml_id AS macro_source_xml_id,
              macro_sr.title AS macro_source_title,
              macro_sr.canonical_url AS macro_source_url,
              c.id AS condition_id,
              c.edition_id AS condition_edition_id,
              c.condition_kind AS condition_condition_kind,
              c.raw_text AS condition_raw_text,
              c.normalized_text AS condition_normalized_text,
              c.machine_status AS condition_machine_status,
              c.expression_json AS condition_expression_json,
              c.source_ref_id AS condition_source_ref_id,
              condition_sr.part AS condition_source_part,
              condition_sr.section AS condition_source_section,
              condition_sr.table_id AS condition_source_table_id,
              condition_sr.xml_id AS condition_source_xml_id,
              condition_sr.title AS condition_source_title,
              condition_sr.canonical_url AS condition_source_url
            FROM iod_functional_group_use fg
            JOIN macro m ON m.id = fg.macro_id
            JOIN source_ref use_sr ON use_sr.id = fg.source_ref_id
            JOIN source_ref macro_sr ON macro_sr.id = m.source_ref_id
            LEFT JOIN condition c ON c.id = fg.condition_id
            LEFT JOIN source_ref condition_sr ON condition_sr.id = c.source_ref_id
            WHERE fg.edition_id = ? AND fg.iod_id = ?
            ORDER BY fg.id
            """,
            (edition, iod_id),
        ).fetchall()
        return [
            IODFunctionalGroupUseRecord(
                use=_iod_functional_group_use_from_prefixed_row(row),
                macro=_macro_from_prefixed_row(row, "macro"),
                condition=(
                    _condition_from_prefixed_row(row, "condition")
                    if row["condition_id"] is not None
                    else None
                ),
            )
            for row in sorted(rows, key=lambda row: _id_order(str(row["use_id"])))
        ]

    def list_attribute_uses(
        self, *, owner_type: str, owner_id: str, edition: str
    ) -> list[AttributeUseRecord]:
        """Return attribute rows for a module or macro in table order."""
        rows = self.connection.execute(
            """
            SELECT
              au.id AS attribute_id,
              au.edition_id AS attribute_edition_id,
              au.owner_type AS attribute_owner_type,
              au.owner_id AS attribute_owner_id,
              au.parent_attribute_use_id AS attribute_parent_attribute_use_id,
              au.row_kind AS attribute_row_kind,
              au.attribute_tag AS attribute_attribute_tag,
              au.attribute_keyword AS attribute_attribute_keyword,
              au.attribute_name AS attribute_attribute_name,
              au.type_designation AS attribute_type_designation,
              au.description_text AS attribute_description_text,
              au.condition_id AS attribute_condition_id,
              au.included_macro_id AS attribute_included_macro_id,
              au.include_target_text AS attribute_include_target_text,
              au.sequence_depth AS attribute_sequence_depth,
              au.row_order AS attribute_row_order,
              au.source_ref_id AS attribute_source_ref_id,
              attr_sr.part AS attribute_source_part,
              attr_sr.section AS attribute_source_section,
              attr_sr.table_id AS attribute_source_table_id,
              attr_sr.xml_id AS attribute_source_xml_id,
              attr_sr.title AS attribute_source_title,
              attr_sr.canonical_url AS attribute_source_url,
              im.id AS macro_id,
              im.edition_id AS macro_edition_id,
              im.name AS macro_name,
              im.table_id AS macro_table_id,
              im.section AS macro_section,
              im.macro_kind AS macro_macro_kind,
              im.source_ref_id AS macro_source_ref_id,
              macro_sr.part AS macro_source_part,
              macro_sr.section AS macro_source_section,
              macro_sr.table_id AS macro_source_table_id,
              macro_sr.xml_id AS macro_source_xml_id,
              macro_sr.title AS macro_source_title,
              macro_sr.canonical_url AS macro_source_url,
              c.id AS condition_id,
              c.edition_id AS condition_edition_id,
              c.condition_kind AS condition_condition_kind,
              c.raw_text AS condition_raw_text,
              c.normalized_text AS condition_normalized_text,
              c.machine_status AS condition_machine_status,
              c.expression_json AS condition_expression_json,
              c.source_ref_id AS condition_source_ref_id,
              condition_sr.part AS condition_source_part,
              condition_sr.section AS condition_source_section,
              condition_sr.table_id AS condition_source_table_id,
              condition_sr.xml_id AS condition_source_xml_id,
              condition_sr.title AS condition_source_title,
              condition_sr.canonical_url AS condition_source_url
            FROM attribute_use au
            JOIN source_ref attr_sr ON attr_sr.id = au.source_ref_id
            LEFT JOIN macro im ON im.id = au.included_macro_id
            LEFT JOIN source_ref macro_sr ON macro_sr.id = im.source_ref_id
            LEFT JOIN condition c ON c.id = au.condition_id
            LEFT JOIN source_ref condition_sr ON condition_sr.id = c.source_ref_id
            WHERE au.edition_id = ?
              AND au.owner_type = ?
              AND au.owner_id = ?
            ORDER BY au.row_order
            """,
            (edition, owner_type, owner_id),
        ).fetchall()
        owner_name = self._owner_name(owner_type, owner_id, edition=edition)
        return [
            AttributeUseRecord(
                attribute_use=_attribute_use_from_prefixed_row(row),
                owner_type=owner_type,
                owner_name=owner_name,
                included_macro=(
                    _macro_from_prefixed_row(row, "macro")
                    if row["macro_id"] is not None
                    else None
                ),
                condition=(
                    _condition_from_prefixed_row(row, "condition")
                    if row["condition_id"] is not None
                    else None
                ),
            )
            for row in rows
        ]

    def _owner_name(self, owner_type: str, owner_id: str, *, edition: str) -> str:
        if owner_type == "module":
            module = self.find_module_by_id(owner_id, edition=edition)
            return module.name if module else owner_id
        if owner_type == "macro":
            macro = self.find_macro_by_id(owner_id, edition=edition)
            return macro.name if macro else owner_id
        return owner_id

    def find_module_by_id(self, module_id: str, *, edition: str) -> Module | None:
        row = self.connection.execute(
            """
            SELECT m.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM module m
            JOIN source_ref sr ON sr.id = m.source_ref_id
            WHERE m.edition_id = ? AND m.id = ?
            """,
            (edition, module_id),
        ).fetchone()
        return _module_from_row(row) if row else None

    def find_macro_by_id(self, macro_id: str, *, edition: str) -> Macro | None:
        row = self.connection.execute(
            """
            SELECT m.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM macro m
            JOIN source_ref sr ON sr.id = m.source_ref_id
            WHERE m.edition_id = ? AND m.id = ?
            """,
            (edition, macro_id),
        ).fetchone()
        return _macro_from_row(row) if row else None


class Part04Repository:
    """Lookup and traverse imported PS3.4 service/SOP Class records."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_sop_class_by_uid_or_name(
        self, uid_or_name: str, *, edition: str
    ) -> tuple[SOPClass, ServiceClass | None] | None:
        """Return a SOP Class by UID value, name, or PS3.6 UID keyword."""
        row = self.connection.execute(
            """
            SELECT
              sc.id AS sop_id,
              sc.edition_id AS sop_edition_id,
              sc.name AS sop_name,
              sc.uid_value AS sop_uid_value,
              sc.service_class_id AS sop_service_class_id,
              sc.source_ref_id AS sop_source_ref_id,
              sop_sr.part AS sop_source_part,
              sop_sr.section AS sop_source_section,
              sop_sr.table_id AS sop_source_table_id,
              sop_sr.xml_id AS sop_source_xml_id,
              sop_sr.title AS sop_source_title,
              sop_sr.canonical_url AS sop_source_url,
              svc.id AS service_id,
              svc.edition_id AS service_edition_id,
              svc.name AS service_name,
              svc.section AS service_section,
              svc.source_ref_id AS service_source_ref_id,
              service_sr.part AS service_source_part,
              service_sr.section AS service_source_section,
              service_sr.table_id AS service_source_table_id,
              service_sr.xml_id AS service_source_xml_id,
              service_sr.title AS service_source_title,
              service_sr.canonical_url AS service_source_url
            FROM sop_class sc
            JOIN source_ref sop_sr ON sop_sr.id = sc.source_ref_id
            LEFT JOIN service_class svc ON svc.id = sc.service_class_id
            LEFT JOIN source_ref service_sr ON service_sr.id = svc.source_ref_id
            LEFT JOIN uid_registry_entry uid
              ON uid.edition_id = sc.edition_id AND uid.uid_value = sc.uid_value
            WHERE sc.edition_id = ?
              AND (
                sc.uid_value = ?
                OR lower(sc.name) = lower(?)
                OR lower(uid.uid_keyword) = lower(?)
              )
            """,
            (edition, uid_or_name, uid_or_name, uid_or_name),
        ).fetchone()
        if row is None:
            return None
        return (
            _sop_class_from_prefixed_row(row, "sop"),
            (
                _service_class_from_prefixed_row(row, "service")
                if row["service_id"] is not None
                else None
            ),
        )

    def list_iods_for_sop_class(
        self, sop_class_id: str, *, edition: str
    ) -> list[SOPClassIODRecord]:
        """Return IODs linked to a SOP Class in parsed table order."""
        rows = self.connection.execute(
            """
            SELECT
              sci.id AS edge_id,
              sci.edition_id AS edge_edition_id,
              sci.sop_class_id AS edge_sop_class_id,
              sci.iod_id AS edge_iod_id,
              sci.resolution AS edge_resolution,
              sci.resolution_warning AS edge_resolution_warning,
              sci.source_ref_id AS edge_source_ref_id,
              edge_sr.part AS edge_source_part,
              edge_sr.section AS edge_source_section,
              edge_sr.table_id AS edge_source_table_id,
              edge_sr.xml_id AS edge_source_xml_id,
              edge_sr.title AS edge_source_title,
              edge_sr.canonical_url AS edge_source_url,
              i.id AS iod_id,
              i.edition_id AS iod_edition_id,
              i.name AS iod_name,
              i.keyword AS iod_keyword,
              i.iod_type AS iod_iod_type,
              i.part AS iod_part,
              i.section AS iod_section,
              i.source_ref_id AS iod_source_ref_id,
              iod_sr.part AS iod_source_part,
              iod_sr.section AS iod_source_section,
              iod_sr.table_id AS iod_source_table_id,
              iod_sr.xml_id AS iod_source_xml_id,
              iod_sr.title AS iod_source_title,
              iod_sr.canonical_url AS iod_source_url
            FROM sop_class_iod sci
            JOIN source_ref edge_sr ON edge_sr.id = sci.source_ref_id
            JOIN iod i ON i.id = sci.iod_id
            JOIN source_ref iod_sr ON iod_sr.id = i.source_ref_id
            WHERE sci.edition_id = ? AND sci.sop_class_id = ?
            ORDER BY sci.id
            """,
            (edition, sop_class_id),
        ).fetchall()
        return [
            SOPClassIODRecord(
                edge=_sop_class_iod_from_prefixed_row(row, "edge"),
                iod=_iod_from_prefixed_row(row, "iod"),
            )
            for row in sorted(rows, key=lambda row: _id_order(str(row["edge_id"])))
        ]


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


def _id_order(value: str) -> int:
    suffix = value.rsplit(".", maxsplit=1)[-1]
    return int(suffix) if suffix.isdigit() else 0


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
