"""Data element and UID query responses."""

from __future__ import annotations

import sqlite3

from dicom_kb.db.repositories import (
    DataElementRepository,
    UIDRepository,
)
from dicom_kb.ir.validators import (
    IdentifierValidationError,
    normalize_tag,
    normalize_uid,
)
from dicom_kb.query.answer_contracts import (
    ToolResponse,
    data_element_result,
    standard_ref,
    tool_response,
    uid_result,
)
from dicom_kb.query.resolver._identifiers import _looks_like_tag, _looks_like_uid


def lookup_data_element(
    connection: sqlite3.Connection,
    *,
    tag_or_keyword: str,
    edition: str,
) -> ToolResponse:
    """Resolve a PS3.6 data element by tag, range tag, or keyword."""
    if _looks_like_tag(tag_or_keyword):
        try:
            normalize_tag(tag_or_keyword)
        except IdentifierValidationError as exc:
            return tool_response(
                status="validation_error",
                result={"message": str(exc)},
            )

    element, warning = DataElementRepository(connection).find_by_tag_or_keyword(
        tag_or_keyword,
        edition=edition,
    )
    if element is None:
        return tool_response(
            status="not_found",
            result={"message": "No DICOM data element matched the input."},
        )

    warnings = [warning] if warning else []
    return tool_response(
        status="ok",
        result=data_element_result(element),
        refs=[standard_ref(element.source_ref)],
        warnings=warnings,
    )


def lookup_uid(
    connection: sqlite3.Connection,
    *,
    uid_or_keyword: str,
    edition: str,
) -> ToolResponse:
    """Resolve a PS3.6 UID registry entry by UID value or keyword."""
    if _looks_like_uid(uid_or_keyword):
        try:
            normalize_uid(uid_or_keyword)
        except IdentifierValidationError as exc:
            return tool_response(
                status="validation_error",
                result={"message": str(exc)},
            )

    uid = UIDRepository(connection).find_by_uid_or_keyword(
        uid_or_keyword,
        edition=edition,
    )
    if uid is None:
        return tool_response(
            status="not_found",
            result={"message": "No DICOM UID registry entry matched the input."},
        )

    return tool_response(
        status="ok",
        result=uid_result(uid),
        refs=[standard_ref(uid.source_ref)],
    )
