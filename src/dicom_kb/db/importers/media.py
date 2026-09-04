"""PS3.10 media requirements and PS3.18 transaction import."""

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
    DicomMediaType,
    DicomwebTransaction,
    FileMetaRequirement,
)


def import_file_meta_requirements(
    connection: sqlite3.Connection,
    *,
    edition: str,
    file_meta_requirements: Iterable[FileMetaRequirement],
) -> ImportSummary:
    """Import parsed PS3.10 file meta information requirements."""
    records = tuple(file_meta_requirements)
    source_refs = _unique_source_refs(record.source_ref for record in records)

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for record in records:
                _insert_file_meta_requirement(
                    connection,
                    _with_resolved_data_element_id(connection, record),
                )
    except sqlite3.IntegrityError as exc:
        raise ImportError(
            f"failed to import PS3.10 file meta requirements for {edition}"
        ) from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        file_meta_requirements=len(records),
    )


def import_dicom_media_types(
    connection: sqlite3.Connection,
    *,
    edition: str,
    media_types: Iterable[DicomMediaType],
) -> ImportSummary:
    """Import parsed DICOM media type rows."""
    records = tuple(media_types)
    source_refs = _unique_source_refs(record.source_ref for record in records)

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for record in records:
                _insert_dicom_media_type(connection, record)
    except sqlite3.IntegrityError as exc:
        raise ImportError(f"failed to import DICOM media types for {edition}") from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        dicom_media_types=len(records),
    )


def import_dicomweb_transactions(
    connection: sqlite3.Connection,
    *,
    edition: str,
    transactions: Iterable[DicomwebTransaction],
) -> ImportSummary:
    """Import parsed PS3.18 DICOMweb transaction rows."""
    records = tuple(transactions)
    source_refs = _unique_source_refs(record.source_ref for record in records)

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for record in records:
                _insert_dicomweb_transaction(connection, record)
    except sqlite3.IntegrityError as exc:
        raise ImportError(
            f"failed to import PS3.18 DICOMweb transactions for {edition}"
        ) from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        dicomweb_transactions=len(records),
    )


def _insert_file_meta_requirement(
    connection: sqlite3.Connection, record: FileMetaRequirement
) -> None:
    connection.execute(
        """
        INSERT INTO file_meta_requirement (
          id, edition_id, data_element_id, attribute_tag, attribute_keyword,
          type_designation, rule_context, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.edition_id,
            record.data_element_id,
            record.attribute_tag,
            record.attribute_keyword,
            record.type_designation,
            record.rule_context,
            record.source_ref.id,
        ),
    )


def _with_resolved_data_element_id(
    connection: sqlite3.Connection, record: FileMetaRequirement
) -> FileMetaRequirement:
    if record.data_element_id is not None and record.attribute_keyword is not None:
        return record
    row = connection.execute(
        """
        SELECT id, keyword
        FROM data_element
        WHERE edition_id = ? AND tag = ?
        """,
        (record.edition_id, record.attribute_tag),
    ).fetchone()
    if row is None:
        return record
    return record.model_copy(
        update={
            "data_element_id": record.data_element_id or row["id"],
            "attribute_keyword": record.attribute_keyword or row["keyword"],
        }
    )


def _insert_dicom_media_type(
    connection: sqlite3.Connection, record: DicomMediaType
) -> None:
    connection.execute(
        """
        INSERT INTO dicom_media_type (
          id, edition_id, media_type, service_context,
          transfer_syntax_constraints_json, directions_json, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.edition_id,
            record.media_type,
            record.service_context,
            json.dumps(
                record.transfer_syntax_constraints,
                sort_keys=True,
                separators=(",", ":"),
            ),
            json.dumps(record.directions, sort_keys=True, separators=(",", ":")),
            record.source_ref.id,
        ),
    )


def _insert_dicomweb_transaction(
    connection: sqlite3.Connection, record: DicomwebTransaction
) -> None:
    connection.execute(
        """
        INSERT INTO dicomweb_transaction (
          id, edition_id, transaction_name, resource_category, http_method,
          route_template, request_constraints_json, response_constraints_json,
          status_codes_json, media_type_refs_json, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.edition_id,
            record.transaction_name,
            record.resource_category,
            record.http_method,
            record.route_template,
            json.dumps(
                record.request_constraints,
                sort_keys=True,
                separators=(",", ":"),
            ),
            json.dumps(
                record.response_constraints,
                sort_keys=True,
                separators=(",", ":"),
            ),
            json.dumps(record.status_codes, sort_keys=True, separators=(",", ":")),
            json.dumps(
                record.media_type_refs,
                sort_keys=True,
                separators=(",", ":"),
            ),
            record.source_ref.id,
        ),
    )
