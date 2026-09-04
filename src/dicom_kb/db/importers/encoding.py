"""PS3.5 VR and transfer syntax detail import."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable

from dicom_kb.db.importers._shared import (
    ImportSummary,
    _insert_source_ref,
    _unique_source_refs,
)
from dicom_kb.ir.models import (
    TransferSyntaxDetail,
    VRDefinition,
)


def import_vr_definitions(
    connection: sqlite3.Connection,
    *,
    edition: str,
    vr_definitions: Iterable[VRDefinition],
) -> ImportSummary:
    """Import parsed PS3.5 value representation definitions."""
    records = tuple(vr_definitions)
    source_refs = _unique_source_refs(record.source_ref for record in records)

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for record in records:
                _insert_vr_definition(connection, record)
    except sqlite3.IntegrityError as exc:
        raise ImportError(
            f"failed to import PS3.5 VR definitions for {edition}"
        ) from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        vr_definitions=len(records),
    )


def import_transfer_syntax_details(
    connection: sqlite3.Connection,
    *,
    edition: str,
    transfer_syntax_details: Iterable[TransferSyntaxDetail],
) -> ImportSummary:
    """Import deterministic transfer syntax encoding details."""
    records = tuple(transfer_syntax_details)
    source_refs = _unique_source_refs(record.source_ref for record in records)

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for record in records:
                _insert_transfer_syntax_detail(connection, record)
    except sqlite3.IntegrityError as exc:
        raise ImportError(
            f"failed to import transfer syntax details for {edition}"
        ) from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        transfer_syntax_details=len(records),
    )


def _insert_vr_definition(connection: sqlite3.Connection, record: VRDefinition) -> None:
    connection.execute(
        """
        INSERT INTO vr_definition (
          id, edition_id, vr, name, value_representation_class,
          length_notes_json, padding_behavior, character_repertoire_notes_json,
          binary_or_text, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.edition_id,
            record.vr,
            record.name,
            record.value_representation_class,
            json.dumps(record.length_notes, sort_keys=True, separators=(",", ":")),
            record.padding_behavior,
            json.dumps(
                record.character_repertoire_notes,
                sort_keys=True,
                separators=(",", ":"),
            ),
            record.binary_or_text,
            record.source_ref.id,
        ),
    )


def _insert_transfer_syntax_detail(
    connection: sqlite3.Connection, record: TransferSyntaxDetail
) -> None:
    connection.execute(
        """
        INSERT INTO transfer_syntax_detail (
          id, edition_id, uid_registry_entry_id, uid_value, explicit_vr, endian,
          encapsulated, compression_family, encoding_notes_json, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.edition_id,
            record.uid_registry_entry_id,
            record.uid_value,
            _optional_bool(record.explicit_vr),
            record.endian,
            _optional_bool(record.encapsulated),
            record.compression_family,
            json.dumps(record.encoding_notes, sort_keys=True, separators=(",", ":")),
            record.source_ref.id,
        ),
    )


def _optional_bool(value: bool | None) -> int | None:
    if value is None:
        return None
    return int(value)
