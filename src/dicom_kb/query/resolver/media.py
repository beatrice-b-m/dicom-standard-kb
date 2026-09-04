"""Media types and DICOMweb transaction query responses."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from dicom_kb.db.repositories import (
    DocumentRepository,
    Part10Repository,
    Part18Repository,
)
from dicom_kb.ir.models import (
    DicomMediaType,
    DicomwebTransaction,
)
from dicom_kb.query.answer_contracts import (
    ParseConfidence,
    ResponseClassification,
    ResponseTrace,
    ToolResponse,
    dicom_media_type_result,
    dicomweb_transaction_result,
    standard_ref,
    standard_text_result,
    tool_response,
)
from dicom_kb.query.citations import build_trace, citation_refs
from dicom_kb.query.search import build_fts_query


def lookup_media_type(
    connection: sqlite3.Connection,
    *,
    media_type_or_context: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve a DICOM media-type row by media type or service context."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"media_type_or_context": media_type_or_context}
    normalized_input = media_type_or_context.strip()
    if not normalized_input:
        return tool_response(
            edition=edition,
            tool="lookup_media_type",
            input=response_input,
            status="validation_error",
            result={"message": "media_type_or_context must not be empty."},
            trace=trace,
        )

    records = Part10Repository(connection).list_media_types(
        normalized_input,
        edition=edition,
    )
    if not records:
        fallback = _ps310_media_text_fallback(
            connection,
            edition=edition,
            topic=normalized_input,
            response_input=response_input,
            trace=trace,
        )
        if fallback is not None:
            return fallback
        return tool_response(
            edition=edition,
            tool="lookup_media_type",
            input=response_input,
            status="not_found",
            result={"message": "No DICOM media type matched the input."},
            trace=trace,
        )
    if len(records) > 1:
        return tool_response(
            edition=edition,
            tool="lookup_media_type",
            input=response_input,
            status="validation_error",
            result={
                "message": "Media type input matched multiple contexts.",
                "candidates": [_media_type_result(record) for record in records],
            },
            refs=[standard_ref(record.source_ref) for record in records],
            trace=trace,
        )

    record = records[0]
    return tool_response(
        edition=edition,
        tool="lookup_media_type",
        input=response_input,
        status="ok",
        result=_media_type_result(record),
        refs=[standard_ref(record.source_ref)],
        trace=trace,
    )


def lookup_dicomweb_transaction(
    connection: sqlite3.Connection,
    *,
    name_or_route: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve an imported PS3.18 DICOMweb transaction by name or route."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"name_or_route": name_or_route}
    normalized_input = name_or_route.strip()
    if not normalized_input:
        return tool_response(
            edition=edition,
            tool="lookup_dicomweb_transaction",
            input=response_input,
            status="validation_error",
            result={"message": "name_or_route must not be empty."},
            trace=trace,
        )

    records = Part18Repository(connection).list_dicomweb_transactions(
        normalized_input,
        edition=edition,
    )
    if not records:
        return tool_response(
            edition=edition,
            tool="lookup_dicomweb_transaction",
            input=response_input,
            status="not_found",
            result={"message": "No DICOMweb transaction matched the input."},
            trace=trace,
        )
    if len(records) > 1:
        return tool_response(
            edition=edition,
            tool="lookup_dicomweb_transaction",
            input=response_input,
            status="validation_error",
            result={
                "message": "DICOMweb transaction input matched multiple rows.",
                "candidates": [
                    _dicomweb_transaction_result(record) for record in records
                ],
            },
            refs=[standard_ref(record.source_ref) for record in records],
            trace=trace,
        )

    record = records[0]
    return tool_response(
        edition=edition,
        tool="lookup_dicomweb_transaction",
        input=response_input,
        status="ok",
        result=_dicomweb_transaction_result(record),
        refs=[standard_ref(record.source_ref)],
        trace=trace,
    )


def _media_type_result(record: DicomMediaType) -> dict[str, object]:
    return dicom_media_type_result(
        media_type=record.media_type,
        service_context=record.service_context,
        transfer_syntax_constraints=list(record.transfer_syntax_constraints),
        directions=list(record.directions),
    )


def _dicomweb_transaction_result(record: DicomwebTransaction) -> dict[str, object]:
    return dicomweb_transaction_result(
        transaction_name=record.transaction_name,
        resource_category=record.resource_category or "",
        http_method=record.http_method,
        route_template=record.route_template,
        request_constraints=list(record.request_constraints),
        response_constraints=list(record.response_constraints),
        status_codes=list(record.status_codes),
        media_type_refs=list(record.media_type_refs),
    )


def _ps310_media_text_fallback(
    connection: sqlite3.Connection,
    *,
    edition: str,
    topic: str,
    response_input: dict[str, str],
    trace: ResponseTrace,
) -> ToolResponse | None:
    fts_query = build_fts_query(topic)
    if fts_query is None:
        return None

    repository = DocumentRepository(connection)
    matches = repository.search_text(
        fts_query=fts_query,
        edition=edition,
        part_filter="PS3.10",
        limit=5,
    )
    if not matches:
        return None

    match = next(
        (candidate for candidate in matches if candidate.node.node_type == "table"),
        matches[0],
    )
    node = match.node
    tables = repository.list_tables_under_node(node, edition=edition)
    plain_text = node.plain_text or match.snippet
    max_chars = 800
    warnings = [
        "No parsed media-type row matched; returning bounded PS3.10 text fallback."
    ]
    if len(plain_text) > max_chars:
        warnings.append(f"text excerpt truncated to {max_chars} characters")

    return tool_response(
        edition=edition,
        tool="lookup_media_type",
        input=response_input,
        status="ok",
        result=standard_text_result(
            node,
            tables,
            text_excerpt=plain_text[:max_chars],
        ),
        refs=citation_refs(
            (node.source_ref,),
            (table.source_ref for table in tables),
        ),
        warnings=warnings,
        trace=trace,
        classification=ResponseClassification(
            normativity="explanatory",
            evidence_level="retrieved_text",
            machine_decidability="not_applicable",
        ),
        parse_confidence=ParseConfidence(level="low", source="retrieved_text"),
    )
