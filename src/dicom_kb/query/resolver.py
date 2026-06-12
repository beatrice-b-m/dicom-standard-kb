"""SQLite-backed deterministic query resolvers."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from dicom_kb.db.repositories import (
    DataElementRepository,
    DocumentRepository,
    Part03Repository,
    Part04Repository,
    UIDRepository,
)
from dicom_kb.ir.validators import (
    IdentifierValidationError,
    normalize_tag,
    normalize_uid,
)
from dicom_kb.query.answer_contracts import (
    ToolResponse,
    attribute_context_result,
    data_element_result,
    iod_modules_result,
    iod_result,
    module_attributes_result,
    sop_class_result,
    standard_ref,
    standard_text_result,
    standard_text_search_result,
    uid_result,
)
from dicom_kb.query.citations import build_trace, unique_refs
from dicom_kb.query.conditions import effective_type_summary
from dicom_kb.query.graph import (
    attribute_context_uses,
    expand_macro_includes,
    find_attribute_element,
    resolve_context_iods,
)
from dicom_kb.query.search import build_fts_query


def lookup_data_element(
    connection: sqlite3.Connection,
    *,
    tag_or_keyword: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve a PS3.6 data element by tag, range tag, or keyword."""
    trace = build_trace(
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
    trace = build_trace(
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


def lookup_iod(
    connection: sqlite3.Connection,
    *,
    iod_name: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve a PS3.3 IOD by name or keyword."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"iod_name": iod_name}
    iod = Part03Repository(connection).find_iod_by_name_or_keyword(
        iod_name, edition=edition
    )
    if iod is None:
        return ToolResponse(
            edition=edition,
            tool="lookup_iod",
            input=response_input,
            status="not_found",
            result={"message": "No DICOM IOD matched the input."},
            trace=trace,
        )

    return ToolResponse(
        edition=edition,
        tool="lookup_iod",
        input=response_input,
        status="ok",
        result=iod_result(iod),
        refs=[standard_ref(iod.source_ref)],
        trace=trace,
    )


def lookup_sop_class(
    connection: sqlite3.Connection,
    *,
    uid_or_name_or_keyword: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve a PS3.4 SOP Class and linked IODs."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"uid_or_name_or_keyword": uid_or_name_or_keyword}
    if _looks_like_uid(uid_or_name_or_keyword):
        try:
            normalize_uid(uid_or_name_or_keyword)
        except IdentifierValidationError as exc:
            return ToolResponse(
                edition=edition,
                tool="lookup_sop_class",
                input=response_input,
                status="validation_error",
                result={"message": str(exc)},
                trace=trace,
            )

    repository = Part04Repository(connection)
    found = repository.find_sop_class_by_uid_or_name(
        uid_or_name_or_keyword,
        edition=edition,
    )
    if found is None:
        return ToolResponse(
            edition=edition,
            tool="lookup_sop_class",
            input=response_input,
            status="not_found",
            result={"message": "No DICOM SOP Class matched the input."},
            trace=trace,
        )

    sop_class, service_class = found
    iod_records = repository.list_iods_for_sop_class(sop_class.id, edition=edition)
    refs = unique_refs(
        [standard_ref(sop_class.source_ref)]
        + ([standard_ref(service_class.source_ref)] if service_class else [])
        + [
            ref
            for record in iod_records
            for ref in (
                standard_ref(record.edge.source_ref),
                standard_ref(record.iod.source_ref),
            )
        ]
    )
    warnings = [
        record.edge.resolution_warning
        for record in iod_records
        if record.edge.resolution_warning is not None
    ]
    return ToolResponse(
        edition=edition,
        tool="lookup_sop_class",
        input=response_input,
        status="ok",
        result=sop_class_result(sop_class, service_class, iod_records),
        refs=refs,
        warnings=warnings,
        trace=trace,
    )


def list_modules_for_iod(
    connection: sqlite3.Connection,
    *,
    iod_name: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """List PS3.3 modules attached to an IOD."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"iod_name": iod_name}
    repository = Part03Repository(connection)
    iod = repository.find_iod_by_name_or_keyword(iod_name, edition=edition)
    if iod is None:
        return ToolResponse(
            edition=edition,
            tool="list_modules_for_iod",
            input=response_input,
            status="not_found",
            result={"message": "No DICOM IOD matched the input."},
            trace=trace,
        )

    records = repository.list_module_uses_for_iod(iod.id, edition=edition)
    refs = unique_refs(
        [standard_ref(iod.source_ref)]
        + [
            ref
            for record in records
            for ref in (
                standard_ref(record.use.source_ref),
                standard_ref(record.module.source_ref),
            )
        ]
    )
    return ToolResponse(
        edition=edition,
        tool="list_modules_for_iod",
        input=response_input,
        status="ok",
        result=iod_modules_result(iod, records),
        refs=refs,
        trace=trace,
    )


def list_attributes_for_module(
    connection: sqlite3.Connection,
    *,
    module_name: str,
    edition: str,
    expand_macros: bool = False,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """List PS3.3 attributes attached to a module."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {
        "module_name": module_name,
        "expand_macros": str(expand_macros).lower(),
    }
    repository = Part03Repository(connection)
    module = repository.find_module_by_name(module_name, edition=edition)
    if module is None:
        return ToolResponse(
            edition=edition,
            tool="list_attributes_for_module",
            input=response_input,
            status="not_found",
            result={"message": "No DICOM module matched the input."},
            trace=trace,
        )

    records = repository.list_attribute_uses(
        owner_type="module",
        owner_id=module.id,
        edition=edition,
    )
    warnings: list[str] = []
    if expand_macros:
        records, warnings = expand_macro_includes(
            repository,
            records,
            edition=edition,
        )
    refs = unique_refs(
        [standard_ref(module.source_ref)]
        + [standard_ref(record.attribute_use.source_ref) for record in records]
        + [
            standard_ref(record.included_macro.source_ref)
            for record in records
            if record.included_macro is not None
        ]
        + [
            standard_ref(record.expanded_from_include.source_ref)
            for record in records
            if record.expanded_from_include is not None
        ]
    )
    return ToolResponse(
        edition=edition,
        tool="list_attributes_for_module",
        input=response_input,
        status="ok",
        result=module_attributes_result(module, records),
        refs=refs,
        warnings=warnings,
        trace=trace,
    )


def resolve_attribute_context(
    connection: sqlite3.Connection,
    *,
    attribute: str,
    edition: str,
    iod_name: str | None = None,
    sop_class: str | None = None,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve an attribute's effective PS3.3 type in an IOD/SOP context."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = _context_input(attribute, iod_name=iod_name, sop_class=sop_class)
    if (iod_name is None) == (sop_class is None):
        return ToolResponse(
            edition=edition,
            tool="resolve_attribute_context",
            input=response_input,
            status="validation_error",
            result={"message": "Provide exactly one context: iod_name or sop_class."},
            trace=trace,
        )
    if _looks_like_tag(attribute):
        try:
            normalize_tag(attribute)
        except IdentifierValidationError as exc:
            return ToolResponse(
                edition=edition,
                tool="resolve_attribute_context",
                input=response_input,
                status="validation_error",
                result={"message": str(exc)},
                trace=trace,
            )
    if sop_class is not None and _looks_like_uid(sop_class):
        try:
            normalize_uid(sop_class)
        except IdentifierValidationError as exc:
            return ToolResponse(
                edition=edition,
                tool="resolve_attribute_context",
                input=response_input,
                status="validation_error",
                result={"message": str(exc)},
                trace=trace,
            )

    element, element_warning = find_attribute_element(
        connection, attribute=attribute, edition=edition
    )
    if element is None:
        return ToolResponse(
            edition=edition,
            tool="resolve_attribute_context",
            input=response_input,
            status="not_found",
            result={"message": "No DICOM data element matched the attribute input."},
            trace=trace,
        )

    part03 = Part03Repository(connection)
    context = resolve_context_iods(
        connection,
        part03,
        iod_name=iod_name,
        sop_class=sop_class,
        edition=edition,
    )
    if isinstance(context, ToolResponse):
        return context.model_copy(update={"input": response_input, "trace": trace})

    context_iods, context_refs, context_warnings = context
    uses, use_refs, expansion_warnings = attribute_context_uses(
        part03,
        context_iods,
        element,
        edition=edition,
    )
    warnings = [
        warning
        for warning in [element_warning, *context_warnings, *expansion_warnings]
        if warning is not None
    ]
    effective_type, explanation, type_warnings = effective_type_summary(uses)
    warnings.extend(type_warnings)
    refs = unique_refs([standard_ref(element.source_ref)] + context_refs + use_refs)
    return ToolResponse(
        edition=edition,
        tool="resolve_attribute_context",
        input=response_input,
        status="ok",
        result=attribute_context_result(
            element,
            [use.payload for use in uses],
            effective_type=effective_type,
            effective_type_explanation=explanation,
        ),
        refs=refs,
        warnings=warnings,
        trace=trace,
    )


def retrieve_standard_text(
    connection: sqlite3.Connection,
    *,
    part: str,
    section_or_anchor: str,
    edition: str,
    max_chars: int = 800,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Retrieve a capped excerpt from persisted DocBook structure."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {
        "part": part,
        "section_or_anchor": section_or_anchor,
        "max_chars": str(max_chars),
    }
    if not part.startswith("PS3."):
        return ToolResponse(
            edition=edition,
            tool="retrieve_standard_text",
            input=response_input,
            status="validation_error",
            result={"message": "part must be a DICOM part label such as PS3.3."},
            trace=trace,
        )
    if max_chars < 1 or max_chars > 4000:
        return ToolResponse(
            edition=edition,
            tool="retrieve_standard_text",
            input=response_input,
            status="validation_error",
            result={"message": "max_chars must be between 1 and 4000."},
            trace=trace,
        )

    repository = DocumentRepository(connection)
    node = repository.find_node(
        part=part,
        section_or_anchor=section_or_anchor,
        edition=edition,
    )
    if node is None:
        return ToolResponse(
            edition=edition,
            tool="retrieve_standard_text",
            input=response_input,
            status="not_found",
            result={"message": "No standard text node matched the input."},
            trace=trace,
        )

    tables = repository.list_tables_under_node(node, edition=edition)
    plain_text = node.plain_text or ""
    text_excerpt = plain_text[:max_chars]
    warnings = (
        [f"text excerpt truncated to {max_chars} characters"]
        if len(plain_text) > max_chars
        else []
    )
    refs = unique_refs(
        [standard_ref(node.source_ref)]
        + [standard_ref(table.source_ref) for table in tables]
    )
    return ToolResponse(
        edition=edition,
        tool="retrieve_standard_text",
        input=response_input,
        status="ok",
        result=standard_text_result(
            node,
            tables,
            text_excerpt=text_excerpt,
        ),
        refs=refs,
        warnings=warnings,
        trace=trace,
    )


def search_standard_text(
    connection: sqlite3.Connection,
    *,
    query: str,
    edition: str,
    part_filter: str | None = None,
    limit: int = 10,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Search persisted DocBook text with SQLite FTS5."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"query": query, "limit": str(limit)}
    if part_filter is not None:
        response_input["part_filter"] = part_filter
    if not query.strip():
        return ToolResponse(
            edition=edition,
            tool="search_standard_text",
            input=response_input,
            status="validation_error",
            result={"message": "query must not be empty."},
            trace=trace,
        )
    if len(query) > 200:
        return ToolResponse(
            edition=edition,
            tool="search_standard_text",
            input=response_input,
            status="validation_error",
            result={"message": "query must be 200 characters or fewer."},
            trace=trace,
        )
    if part_filter is not None and not part_filter.startswith("PS3."):
        return ToolResponse(
            edition=edition,
            tool="search_standard_text",
            input=response_input,
            status="validation_error",
            result={"message": "part_filter must be a DICOM part label such as PS3.3."},
            trace=trace,
        )
    if limit < 1 or limit > 50:
        return ToolResponse(
            edition=edition,
            tool="search_standard_text",
            input=response_input,
            status="validation_error",
            result={"message": "limit must be between 1 and 50."},
            trace=trace,
        )

    fts_query = build_fts_query(query)
    if fts_query is None:
        return ToolResponse(
            edition=edition,
            tool="search_standard_text",
            input=response_input,
            status="validation_error",
            result={"message": "query must contain at least one searchable term."},
            trace=trace,
        )

    records = DocumentRepository(connection).search_text(
        fts_query=fts_query,
        edition=edition,
        part_filter=part_filter,
        limit=limit,
    )
    if not records:
        return ToolResponse(
            edition=edition,
            tool="search_standard_text",
            input=response_input,
            status="not_found",
            result={"message": "No standard text matched the query."},
            trace=trace,
        )

    return ToolResponse(
        edition=edition,
        tool="search_standard_text",
        input=response_input,
        status="ok",
        result=standard_text_search_result(records),
        refs=unique_refs([standard_ref(record.node.source_ref) for record in records]),
        trace=trace,
    )


def _looks_like_tag(value: str) -> bool:
    return any(marker in value for marker in ("(", ")", ","))


def _looks_like_uid(value: str) -> bool:
    return bool(value) and "." in value and value[0].isdigit()


def _context_input(
    attribute: str, *, iod_name: str | None, sop_class: str | None
) -> dict[str, str]:
    response_input = {"attribute": attribute}
    if iod_name is not None:
        response_input["iod_name"] = iod_name
    if sop_class is not None:
        response_input["sop_class"] = sop_class
    return response_input
