"""PS3.6 data element and UID registry import."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from dicom_kb.db.importers._shared import (
    ImportSummary,
    _insert_source_ref,
    _unique_source_refs,
)
from dicom_kb.ir.models import (
    DataElement,
    UIDRegistryEntry,
)


def import_part06(
    connection: sqlite3.Connection,
    *,
    edition: str,
    data_elements: Iterable[DataElement],
    uid_registry_entries: Iterable[UIDRegistryEntry],
) -> ImportSummary:
    """Import parsed PS3.6 records transactionally."""
    elements = tuple(data_elements)
    uids = tuple(uid_registry_entries)
    source_refs = _unique_source_refs(
        [record.source_ref for record in elements]
        + [record.source_ref for record in uids]
    )

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for element in elements:
                _insert_data_element(connection, element)
            for uid in uids:
                _insert_uid(connection, uid)
    except sqlite3.IntegrityError as exc:
        raise ImportError(f"failed to import PS3.6 records for {edition}") from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        data_elements=len(elements),
        uid_registry_entries=len(uids),
    )


def _insert_data_element(connection: sqlite3.Connection, element: DataElement) -> None:
    connection.execute(
        """
        INSERT INTO data_element (
          id, edition_id, tag, group_pattern, element_pattern, is_range, name,
          keyword, vr, vm, retired, retired_in_or_last_seen, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            element.id,
            element.edition_id,
            element.tag,
            element.group_pattern,
            element.element_pattern,
            int(element.is_range),
            element.name,
            element.keyword,
            element.vr,
            element.vm,
            int(element.retired),
            element.retired_in_or_last_seen,
            element.source_ref.id,
        ),
    )


def _insert_uid(connection: sqlite3.Connection, uid: UIDRegistryEntry) -> None:
    connection.execute(
        """
        INSERT INTO uid_registry_entry (
          id, edition_id, uid_value, uid_name, uid_keyword, uid_type, part,
          retired, retired_in_or_last_seen, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uid.id,
            uid.edition_id,
            uid.uid_value,
            uid.uid_name,
            uid.uid_keyword,
            uid.uid_type,
            uid.part,
            int(uid.retired),
            uid.retired_in_or_last_seen,
            uid.source_ref.id,
        ),
    )
