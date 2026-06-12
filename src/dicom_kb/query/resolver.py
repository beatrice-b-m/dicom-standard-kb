"""SQLite-backed deterministic query resolvers."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from dicom_kb.db.repositories import DataElementRepository, UIDRepository
from dicom_kb.ir.validators import (
    IdentifierValidationError,
    normalize_tag,
    normalize_uid,
)
from dicom_kb.query.answer_contracts import (
    ResponseTrace,
    ToolResponse,
    data_element_result,
    standard_ref,
    uid_result,
)


def lookup_data_element(
    connection: sqlite3.Connection,
    *,
    tag_or_keyword: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve a PS3.6 data element by tag, range tag, or keyword."""
    trace = _trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"tag_or_keyword": tag_or_keyword}
    if _looks_like_tag(tag_or_keyword):
        try:
            normalize_tag(tag_or_keyword)
        except IdentifierValidationError as exc:
            return ToolResponse(
                edition=edition,
                tool="lookup_data_element",
                input=response_input,
                status="validation_error",
                result={"message": str(exc)},
                trace=trace,
            )

    element, warning = DataElementRepository(connection).find_by_tag_or_keyword(
        tag_or_keyword,
        edition=edition,
    )
    if element is None:
        return ToolResponse(
            edition=edition,
            tool="lookup_data_element",
            input=response_input,
            status="not_found",
            result={"message": "No DICOM data element matched the input."},
            trace=trace,
        )

    warnings = [warning] if warning else []
    return ToolResponse(
        edition=edition,
        tool="lookup_data_element",
        input=response_input,
        status="ok",
        result=data_element_result(element),
        refs=[standard_ref(element.source_ref)],
        warnings=warnings,
        trace=trace,
    )


def lookup_uid(
    connection: sqlite3.Connection,
    *,
    uid_or_keyword: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve a PS3.6 UID registry entry by UID value or keyword."""
    trace = _trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"uid_or_keyword": uid_or_keyword}
    if _looks_like_uid(uid_or_keyword):
        try:
            normalize_uid(uid_or_keyword)
        except IdentifierValidationError as exc:
            return ToolResponse(
                edition=edition,
                tool="lookup_uid",
                input=response_input,
                status="validation_error",
                result={"message": str(exc)},
                trace=trace,
            )

    uid = UIDRepository(connection).find_by_uid_or_keyword(
        uid_or_keyword,
        edition=edition,
    )
    if uid is None:
        return ToolResponse(
            edition=edition,
            tool="lookup_uid",
            input=response_input,
            status="not_found",
            result={"message": "No DICOM UID registry entry matched the input."},
            trace=trace,
        )

    return ToolResponse(
        edition=edition,
        tool="lookup_uid",
        input=response_input,
        status="ok",
        result=uid_result(uid),
        refs=[standard_ref(uid.source_ref)],
        trace=trace,
    )


def _looks_like_tag(value: str) -> bool:
    return any(marker in value for marker in ("(", ")", ","))


def _looks_like_uid(value: str) -> bool:
    return bool(value) and "." in value and value[0].isdigit()


def _trace(
    connection: sqlite3.Connection,
    *,
    edition: str,
    query_id: str | None,
    resolved_at: datetime | None,
) -> ResponseTrace:
    row = connection.execute(
        "SELECT manifest_sha256 FROM standard_edition WHERE id = ?",
        (edition,),
    ).fetchone()
    manifest_sha256 = str(row["manifest_sha256"]) if row else None
    if query_id is not None and resolved_at is not None:
        return ResponseTrace(
            query_id=query_id,
            resolved_at=resolved_at,
            source_manifest_sha256=manifest_sha256,
        )
    if query_id is not None:
        return ResponseTrace(
            query_id=query_id,
            source_manifest_sha256=manifest_sha256,
        )
    if resolved_at is not None:
        return ResponseTrace(
            resolved_at=resolved_at,
            source_manifest_sha256=manifest_sha256,
        )
    return ResponseTrace(source_manifest_sha256=manifest_sha256)
