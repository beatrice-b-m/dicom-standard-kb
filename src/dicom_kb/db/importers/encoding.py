"""Import the transfer syntax encoding facts read from PS3.5."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable

from dicom_kb.db.importers._shared import ImportSummary
from dicom_kb.ir.models import TransferSyntaxDetail


def import_transfer_syntax_details(
    connection: sqlite3.Connection,
    *,
    edition: str,
    transfer_syntax_details: Iterable[TransferSyntaxDetail],
) -> ImportSummary:
    """Import one row of encoding facts per transfer syntax."""
    records = tuple(transfer_syntax_details)
    try:
        with connection:
            connection.executemany(
                """
                INSERT INTO transfer_syntax_detail (
                  id, edition_id, uid_value, vr_encoding, byte_order,
                  pixel_data, deflate, section_xml_id, see_also_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        record.id,
                        record.edition_id,
                        record.uid_value,
                        record.vr_encoding,
                        record.byte_order,
                        record.pixel_data,
                        record.deflate,
                        record.section_xml_id,
                        json.dumps(record.see_also),
                    )
                    for record in records
                ],
            )
    except sqlite3.IntegrityError as exc:
        raise ImportError(
            f"failed to import transfer syntax details for {edition}"
        ) from exc
    return ImportSummary(
        edition=edition, source_refs=0, transfer_syntax_details=len(records)
    )
