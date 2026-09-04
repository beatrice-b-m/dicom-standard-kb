"""SR templates, context groups, and coded concept query responses."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from dicom_kb.db.repositories import (
    CodeMeaningRecord,
    ContextGroupRecord,
    Part16Repository,
    SRTemplateRecord,
)
from dicom_kb.query.answer_contracts import (
    ContextGroupRowResult,
    SRTemplateRowResult,
    StandardRef,
    ToolResponse,
    code_meaning_result,
    context_group_result,
    sr_template_result,
    standard_ref,
    tool_response,
)
from dicom_kb.query.citations import build_trace


def lookup_code_meaning(
    connection: sqlite3.Connection,
    *,
    code_value: str,
    edition: str,
    scheme: str | None = None,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve an imported PS3.16 coded concept by value and optional scheme."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"code_value": code_value}
    if scheme is not None:
        response_input["scheme"] = scheme
    normalized_code_value = code_value.strip()
    normalized_scheme = scheme.strip() if scheme is not None else None
    if not normalized_code_value:
        return tool_response(
            edition=edition,
            tool="lookup_code_meaning",
            input=response_input,
            status="validation_error",
            result={"message": "code_value must not be empty."},
            trace=trace,
        )
    if normalized_scheme == "":
        return tool_response(
            edition=edition,
            tool="lookup_code_meaning",
            input=response_input,
            status="validation_error",
            result={"message": "scheme must not be empty when provided."},
            trace=trace,
        )

    records = Part16Repository(connection).list_code_meanings(
        normalized_code_value,
        edition=edition,
        scheme=normalized_scheme,
    )
    if not records:
        return tool_response(
            edition=edition,
            tool="lookup_code_meaning",
            input=response_input,
            status="not_found",
            result={"message": "No PS3.16 coded concept matched the input."},
            trace=trace,
        )
    if len(records) > 1:
        return tool_response(
            edition=edition,
            tool="lookup_code_meaning",
            input=response_input,
            status="validation_error",
            result={
                "message": "Code value input matched multiple coded concepts.",
                "candidates": [_code_meaning_result(record) for record in records],
            },
            refs=[standard_ref(record.concept.source_ref) for record in records],
            trace=trace,
        )

    record = records[0]
    return tool_response(
        edition=edition,
        tool="lookup_code_meaning",
        input=response_input,
        status="ok",
        result=_code_meaning_result(record),
        refs=[standard_ref(record.concept.source_ref)],
        trace=trace,
    )


def lookup_context_group(
    connection: sqlite3.Connection,
    *,
    cid_or_name: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve an imported PS3.16 context group by CID or exact name."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"cid_or_name": cid_or_name}
    normalized_input = cid_or_name.strip()
    if not normalized_input:
        return tool_response(
            edition=edition,
            tool="lookup_context_group",
            input=response_input,
            status="validation_error",
            result={"message": "cid_or_name must not be empty."},
            trace=trace,
        )

    records = Part16Repository(connection).list_context_groups(
        normalized_input,
        edition=edition,
    )
    if not records:
        return tool_response(
            edition=edition,
            tool="lookup_context_group",
            input=response_input,
            status="not_found",
            result={"message": "No PS3.16 context group matched the input."},
            trace=trace,
        )
    if len(records) > 1:
        return tool_response(
            edition=edition,
            tool="lookup_context_group",
            input=response_input,
            status="validation_error",
            result={
                "message": "Context group input matched multiple rows.",
                "candidates": [_context_group_result(record) for record in records],
            },
            refs=_context_group_refs(records),
            trace=trace,
        )

    record = records[0]
    return tool_response(
        edition=edition,
        tool="lookup_context_group",
        input=response_input,
        status="ok",
        result=_context_group_result(record),
        refs=_context_group_refs([record]),
        trace=trace,
    )


def lookup_sr_template(
    connection: sqlite3.Connection,
    *,
    tid_or_name: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve an imported PS3.16 SR template by TID or exact name."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"tid_or_name": tid_or_name}
    normalized_input = tid_or_name.strip()
    if not normalized_input:
        return tool_response(
            edition=edition,
            tool="lookup_sr_template",
            input=response_input,
            status="validation_error",
            result={"message": "tid_or_name must not be empty."},
            trace=trace,
        )

    records = Part16Repository(connection).list_sr_templates(
        normalized_input,
        edition=edition,
    )
    if not records:
        return tool_response(
            edition=edition,
            tool="lookup_sr_template",
            input=response_input,
            status="not_found",
            result={"message": "No PS3.16 SR template matched the input."},
            trace=trace,
        )
    if len(records) > 1:
        return tool_response(
            edition=edition,
            tool="lookup_sr_template",
            input=response_input,
            status="validation_error",
            result={
                "message": "SR template input matched multiple rows.",
                "candidates": [_sr_template_result(record) for record in records],
            },
            refs=_sr_template_refs(records),
            trace=trace,
        )

    record = records[0]
    return tool_response(
        edition=edition,
        tool="lookup_sr_template",
        input=response_input,
        status="ok",
        result=_sr_template_result(record),
        refs=_sr_template_refs([record]),
        trace=trace,
    )


def _context_group_result(record: ContextGroupRecord) -> dict[str, object]:
    group = record.group
    return context_group_result(
        cid=group.cid,
        name=group.name,
        extensibility=group.extensibility,
        version=group.version,
        rows=[
            ContextGroupRowResult(
                order=row.row_order,
                coding_scheme_designator=row.coding_scheme_designator,
                coding_scheme_version=row.coding_scheme_version,
                code_value=row.code_value,
                code_meaning=row.code_meaning,
                include_cid=row.include_cid,
            )
            for row in record.rows
        ],
    )


def _sr_template_result(record: SRTemplateRecord) -> dict[str, object]:
    template = record.template
    return sr_template_result(
        tid=template.tid,
        name=template.name,
        extensibility=template.extensibility,
        rows=[
            SRTemplateRowResult(
                order=row.row_order,
                relationship_type=row.relationship_type,
                value_type=row.value_type,
                concept_name=row.concept_name,
                cardinality=row.cardinality,
                condition=row.condition_text,
                include_tid=row.include_tid,
            )
            for row in record.rows
        ],
    )


def _context_group_refs(records: list[ContextGroupRecord]) -> list[StandardRef]:
    source_refs = []
    seen: set[str] = set()
    for record in records:
        for source_ref in [
            record.group.source_ref,
            *[row.source_ref for row in record.rows],
        ]:
            if source_ref.id in seen:
                continue
            seen.add(source_ref.id)
            source_refs.append(standard_ref(source_ref))
    return source_refs


def _sr_template_refs(records: list[SRTemplateRecord]) -> list[StandardRef]:
    source_refs = []
    seen: set[str] = set()
    for record in records:
        for source_ref in [
            record.template.source_ref,
            *[row.source_ref for row in record.rows],
        ]:
            if source_ref.id in seen:
                continue
            seen.add(source_ref.id)
            source_refs.append(standard_ref(source_ref))
    return source_refs


def _code_meaning_result(record: CodeMeaningRecord) -> dict[str, object]:
    concept = record.concept
    return code_meaning_result(
        code_value=concept.code_value,
        coding_scheme_designator=concept.coding_scheme_designator,
        coding_scheme_version=concept.coding_scheme_version or None,
        code_meaning=concept.code_meaning,
        context_groups=list(record.context_groups),
    )
