"""Attribute value terms linked to registry entries."""

from __future__ import annotations

import sqlite3

from dicom_kb.db.repositories._rows import (
    _attribute_value_term_from_prefixed_row,
    _data_element_from_prefixed_row,
)
from dicom_kb.db.repositories.records import AttributeValueTermRecord
from dicom_kb.db.repositories.registry import DataElementRepository


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
        attribute_use_ids: tuple[str, ...] | None = None,
    ) -> list[AttributeValueTermRecord]:
        """Return value terms linked to a PS3.6 attribute identity."""
        element, _warning = DataElementRepository(
            self.connection
        ).find_by_tag_or_keyword(attribute, edition=edition)
        if element is None:
            return []
        if attribute_use_ids is not None and not attribute_use_ids:
            return []

        context_clause = """
              AND (
                ? IS NULL
                OR lower(avt.context_label) LIKE '%' || lower(?) || '%'
                OR lower(m.name) = lower(?)
                OR lower(ma.name) = lower(?)
              )
        """
        params: list[object] = [edition, term_kind, element.id]
        if attribute_use_ids is not None:
            placeholders = ", ".join("?" for _ in attribute_use_ids)
            context_clause = f"AND avt.attribute_use_id IN ({placeholders})"
            params.extend(attribute_use_ids)
        else:
            params.extend([context, context, context, context])

        rows = self.connection.execute(
            f"""
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
              {context_clause}
            ORDER BY avt.context_label, avt.value, avt.id
            """,
            params,
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
