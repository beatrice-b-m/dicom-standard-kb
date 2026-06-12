"""Transactional import of parsed IR records into SQLite."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

from dicom_kb.ir.models import DataElement, SourceRef, UIDRegistryEntry
from dicom_kb.sources.manifest import SourceManifest


@dataclass(frozen=True)
class ImportSummary:
    """Counts emitted after an import transaction."""

    edition: str
    source_refs: int
    data_elements: int = 0
    uid_registry_entries: int = 0


def import_manifest(connection: sqlite3.Connection, manifest: SourceManifest) -> None:
    """Import edition and artifact metadata from a source manifest."""
    with connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO standard_edition (
              id, source_label, resolved_from, acquired_at, is_default, manifest_sha256
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                manifest.edition,
                f"DICOM PS3 {manifest.edition}",
                manifest.resolved_from,
                manifest.acquired_at.isoformat(),
                0,
                manifest.source_manifest_sha256,
            ),
        )
        for artifact in manifest.artifacts:
            artifact_id = (
                f"{manifest.edition}.{artifact.part}.{artifact.format}."
                f"{artifact.sha256[:12]}"
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO source_artifact (
                  id, edition_id, part, format, local_path, source_url, sha256,
                  byte_size, acquired_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    manifest.edition,
                    artifact.part,
                    artifact.format,
                    artifact.local_path,
                    artifact.source_url,
                    artifact.sha256,
                    artifact.byte_size,
                    manifest.acquired_at.isoformat(),
                ),
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


def _unique_source_refs(source_refs: Iterable[SourceRef]) -> tuple[SourceRef, ...]:
    unique: dict[str, SourceRef] = {}
    for source_ref in source_refs:
        unique[source_ref.id] = source_ref
    return tuple(unique.values())


def _insert_source_ref(connection: sqlite3.Connection, source_ref: SourceRef) -> None:
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
            source_ref.canonical_url,
        ),
    )


def _insert_data_element(
    connection: sqlite3.Connection, element: DataElement
) -> None:
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
