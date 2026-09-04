"""PS3.16 templates, context groups, and coded concept import."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from dicom_kb.db.importers._shared import (
    ImportSummary,
    _insert_source_ref,
    _unique_source_refs,
)
from dicom_kb.ir.models import (
    CodedConcept,
    ContextGroup,
    ContextGroupRow,
    SRTemplate,
    SRTemplateRow,
)


def import_sr_templates(
    connection: sqlite3.Connection,
    *,
    edition: str,
    templates: Iterable[SRTemplate],
    rows: Iterable[SRTemplateRow],
) -> ImportSummary:
    """Import parsed PS3.16 SR template metadata and rows."""
    template_records = tuple(templates)
    row_records = tuple(rows)
    source_refs = _unique_source_refs(
        [record.source_ref for record in template_records]
        + [record.source_ref for record in row_records]
    )

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for template in template_records:
                _insert_sr_template(connection, template)
            for row in row_records:
                _insert_sr_template_row(connection, row)
    except sqlite3.IntegrityError as exc:
        raise ImportError(
            f"failed to import PS3.16 SR templates for {edition}"
        ) from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        sr_templates=len(template_records),
        sr_template_rows=len(row_records),
    )


def import_context_groups(
    connection: sqlite3.Connection,
    *,
    edition: str,
    context_groups: Iterable[ContextGroup],
    rows: Iterable[ContextGroupRow],
) -> ImportSummary:
    """Import parsed PS3.16 context group metadata and rows."""
    group_records = tuple(context_groups)
    row_records = tuple(rows)
    source_refs = _unique_source_refs(
        [record.source_ref for record in group_records]
        + [record.source_ref for record in row_records]
    )

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for group in group_records:
                _insert_context_group(connection, group)
            for row in row_records:
                _insert_context_group_row(connection, row)
    except sqlite3.IntegrityError as exc:
        raise ImportError(
            f"failed to import PS3.16 context groups for {edition}"
        ) from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        context_groups=len(group_records),
        context_group_rows=len(row_records),
    )


def import_coded_concepts(
    connection: sqlite3.Connection,
    *,
    edition: str,
    coded_concepts: Iterable[CodedConcept],
) -> ImportSummary:
    """Import unique PS3.16 coded concepts derived from context group rows."""
    records = tuple(coded_concepts)
    source_refs = _unique_source_refs(record.source_ref for record in records)

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for record in records:
                _insert_coded_concept(connection, record)
    except sqlite3.IntegrityError as exc:
        raise ImportError(
            f"failed to import PS3.16 coded concepts for {edition}"
        ) from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        coded_concepts=len(records),
    )


def _insert_sr_template(connection: sqlite3.Connection, record: SRTemplate) -> None:
    connection.execute(
        """
        INSERT INTO sr_template (
          id, edition_id, tid, name, extensibility, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.edition_id,
            record.tid,
            record.name,
            record.extensibility,
            record.source_ref.id,
        ),
    )


def _insert_sr_template_row(
    connection: sqlite3.Connection, record: SRTemplateRow
) -> None:
    connection.execute(
        """
        INSERT INTO sr_template_row (
          id, edition_id, sr_template_id, row_order, relationship_type,
          value_type, concept_name, cardinality, condition_text, condition_id,
          include_tid, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.edition_id,
            record.sr_template_id,
            record.row_order,
            record.relationship_type,
            record.value_type,
            record.concept_name,
            record.cardinality,
            record.condition_text,
            record.condition_id,
            record.include_tid,
            record.source_ref.id,
        ),
    )


def _insert_context_group(connection: sqlite3.Connection, record: ContextGroup) -> None:
    connection.execute(
        """
        INSERT INTO context_group (
          id, edition_id, cid, name, extensibility, version, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.edition_id,
            record.cid,
            record.name,
            record.extensibility,
            record.version,
            record.source_ref.id,
        ),
    )


def _insert_context_group_row(
    connection: sqlite3.Connection, record: ContextGroupRow
) -> None:
    connection.execute(
        """
        INSERT INTO context_group_row (
          id, edition_id, context_group_id, row_order, coding_scheme_designator,
          coding_scheme_version, code_value, code_meaning, include_cid,
          source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.edition_id,
            record.context_group_id,
            record.row_order,
            record.coding_scheme_designator,
            record.coding_scheme_version,
            record.code_value,
            record.code_meaning,
            record.include_cid,
            record.source_ref.id,
        ),
    )


def _insert_coded_concept(connection: sqlite3.Connection, record: CodedConcept) -> None:
    connection.execute(
        """
        INSERT INTO coded_concept (
          id, edition_id, code_value, coding_scheme_designator,
          coding_scheme_version, code_meaning, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.edition_id,
            record.code_value,
            record.coding_scheme_designator,
            record.coding_scheme_version,
            record.code_meaning,
            record.source_ref.id,
        ),
    )
