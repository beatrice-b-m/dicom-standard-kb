"""PS3.16 templates, context groups, and coded concept lookups."""

from __future__ import annotations

import sqlite3

from dicom_kb.db.repositories._rows import (
    _coded_concept_from_row,
    _context_group_from_row,
    _context_group_row_from_row,
    _sr_template_from_row,
    _sr_template_row_from_row,
)
from dicom_kb.db.repositories.records import (
    CodeMeaningRecord,
    ContextGroupRecord,
    SRTemplateRecord,
)
from dicom_kb.ir.models import (
    ContextGroupRow,
    SRTemplateRow,
)


class Part16Repository:
    """Lookup imported PS3.16 content mapping semantics."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def list_code_meanings(
        self, code_value: str, *, edition: str, scheme: str | None = None
    ) -> list[CodeMeaningRecord]:
        """Return coded concepts matching a code value and optional scheme."""
        normalized_scheme = scheme.strip() if scheme is not None else None
        rows = self.connection.execute(
            """
            SELECT concept.*, sr.part AS source_part,
                   sr.section AS source_section,
                   sr.table_id AS source_table_id,
                   sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM coded_concept concept
            JOIN source_ref sr ON sr.id = concept.source_ref_id
            WHERE concept.edition_id = ?
              AND concept.code_value = ?
              AND (
                ? IS NULL
                OR lower(concept.coding_scheme_designator) = lower(?)
              )
            ORDER BY concept.coding_scheme_designator,
                     concept.coding_scheme_version,
                     concept.code_meaning,
                     concept.id
            """,
            (edition, code_value.strip(), normalized_scheme, normalized_scheme),
        ).fetchall()
        return [
            CodeMeaningRecord(
                concept=_coded_concept_from_row(row),
                context_groups=self._context_groups_for_code(row, edition=edition),
            )
            for row in rows
        ]

    def list_context_groups(
        self, cid_or_name: str, *, edition: str
    ) -> list[ContextGroupRecord]:
        """Return context groups matching an exact CID, bare CID number, or name."""
        normalized = cid_or_name.strip()
        normalized_label = _context_group_label(normalized)
        group_rows = self.connection.execute(
            """
            SELECT context_group.*, sr.part AS source_part,
                   sr.section AS source_section,
                   sr.table_id AS source_table_id,
                   sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM context_group
            JOIN source_ref sr ON sr.id = context_group.source_ref_id
            WHERE context_group.edition_id = ?
              AND (
                lower(context_group.cid) = lower(?)
                OR lower(context_group.cid) = lower(?)
                OR lower(context_group.name) = lower(?)
              )
            ORDER BY context_group.cid, context_group.name, context_group.id
            """,
            (edition, normalized, normalized_label, normalized),
        ).fetchall()
        return [
            ContextGroupRecord(
                group=_context_group_from_row(row),
                rows=self._rows_for_context_group(str(row["id"]), edition=edition),
            )
            for row in group_rows
        ]

    def list_sr_templates(
        self, tid_or_name: str, *, edition: str
    ) -> list[SRTemplateRecord]:
        """Return SR templates matching an exact TID, bare TID number, or name."""
        normalized = tid_or_name.strip()
        normalized_label = _sr_template_label(normalized)
        template_rows = self.connection.execute(
            """
            SELECT template.*, sr.part AS source_part,
                   sr.section AS source_section,
                   sr.table_id AS source_table_id,
                   sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM sr_template template
            JOIN source_ref sr ON sr.id = template.source_ref_id
            WHERE template.edition_id = ?
              AND (
                lower(template.tid) = lower(?)
                OR lower(template.tid) = lower(?)
                OR lower(template.name) = lower(?)
              )
            ORDER BY template.tid, template.name, template.id
            """,
            (edition, normalized, normalized_label, normalized),
        ).fetchall()
        return [
            SRTemplateRecord(
                template=_sr_template_from_row(row),
                rows=self._rows_for_sr_template(str(row["id"]), edition=edition),
            )
            for row in template_rows
        ]

    def _rows_for_sr_template(
        self, sr_template_id: str, *, edition: str
    ) -> tuple[SRTemplateRow, ...]:
        rows = self.connection.execute(
            """
            SELECT row.*, sr.part AS source_part,
                   sr.section AS source_section,
                   sr.table_id AS source_table_id,
                   sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM sr_template_row row
            JOIN source_ref sr ON sr.id = row.source_ref_id
            WHERE row.edition_id = ?
              AND row.sr_template_id = ?
            ORDER BY row.row_order, row.id
            """,
            (edition, sr_template_id),
        ).fetchall()
        return tuple(_sr_template_row_from_row(row) for row in rows)

    def _rows_for_context_group(
        self, context_group_id: str, *, edition: str
    ) -> tuple[ContextGroupRow, ...]:
        rows = self.connection.execute(
            """
            SELECT row.*, sr.part AS source_part,
                   sr.section AS source_section,
                   sr.table_id AS source_table_id,
                   sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM context_group_row row
            JOIN source_ref sr ON sr.id = row.source_ref_id
            WHERE row.edition_id = ?
              AND row.context_group_id = ?
            ORDER BY row.row_order, row.id
            """,
            (edition, context_group_id),
        ).fetchall()
        return tuple(_context_group_row_from_row(row) for row in rows)

    def _context_groups_for_code(
        self, row: sqlite3.Row, *, edition: str
    ) -> tuple[str, ...]:
        groups = self.connection.execute(
            """
            SELECT DISTINCT context_group.cid
            FROM context_group_row row
            JOIN context_group ON context_group.id = row.context_group_id
            WHERE row.edition_id = ?
              AND row.code_value = ?
              AND row.coding_scheme_designator = ?
              AND COALESCE(row.coding_scheme_version, '') = ?
              AND row.code_meaning = ?
            ORDER BY context_group.cid
            """,
            (
                edition,
                row["code_value"],
                row["coding_scheme_designator"],
                row["coding_scheme_version"],
                row["code_meaning"],
            ),
        ).fetchall()
        return tuple(_context_group_label(str(group["cid"])) for group in groups)


def _sr_template_label(tid: str) -> str:
    return tid if tid.casefold().startswith("tid ") else f"TID {tid}"


def _context_group_label(cid: str) -> str:
    return cid if cid.casefold().startswith("cid ") else f"CID {cid}"
