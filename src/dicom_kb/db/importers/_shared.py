"""Import summaries and shared source-reference persistence."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

from dicom_kb.ir.models import (
    SourceRef,
)
from dicom_kb.sources.official_urls import official_standard_ref_url


@dataclass(frozen=True)
class ImportSummary:
    """Counts emitted after an import transaction."""

    edition: str
    source_refs: int
    data_elements: int = 0
    uid_registry_entries: int = 0
    iods: int = 0
    modules: int = 0
    macros: int = 0
    iod_module_uses: int = 0
    iod_functional_group_uses: int = 0
    attribute_uses: int = 0
    conditions: int = 0
    service_classes: int = 0
    sop_classes: int = 0
    sop_class_iods: int = 0
    doc_nodes: int = 0
    xrefs: int = 0
    xrefs_unresolved: int = 0
    raw_table_irs: int = 0
    attribute_value_terms: int = 0
    vr_definitions: int = 0
    transfer_syntax_details: int = 0
    file_meta_requirements: int = 0
    dicom_media_types: int = 0
    dicomweb_transactions: int = 0
    sr_templates: int = 0
    sr_template_rows: int = 0
    context_groups: int = 0
    context_group_rows: int = 0
    coded_concepts: int = 0
    include_rows_resolved: int = 0
    include_rows_unresolved: int = 0


def _unique_source_refs(source_refs: Iterable[SourceRef]) -> tuple[SourceRef, ...]:
    unique: dict[str, SourceRef] = {}
    for source_ref in source_refs:
        unique[source_ref.id] = source_ref
    return tuple(unique.values())


def _insert_source_ref(connection: sqlite3.Connection, source_ref: SourceRef) -> None:
    canonical_url = source_ref.canonical_url or official_standard_ref_url(
        edition=source_ref.edition_id,
        part=source_ref.part,
        anchor=source_ref.xml_id or source_ref.table_id,
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO source_ref (
          id, edition_id, part, section, table_id, xml_id, title, canonical_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_ref.id,
            source_ref.edition_id,
            source_ref.part,
            source_ref.section,
            source_ref.table_id,
            source_ref.xml_id,
            source_ref.title,
            canonical_url,
        ),
    )
