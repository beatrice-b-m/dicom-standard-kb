"""IOD and SOP Class graph queries and attribute context resolution."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from dicom_kb.db.repositories import (
    Part03Repository,
    Part04Repository,
)
from dicom_kb.ir.validators import (
    IdentifierValidationError,
    normalize_tag,
    normalize_uid,
)
from dicom_kb.query.answer_contracts import (
    ToolResponse,
    attribute_context_result,
    iod_modules_result,
    iod_result,
    module_attributes_result,
    sop_class_result,
    standard_ref,
    tool_response,
)
from dicom_kb.query.citations import CitationBuilder, build_trace, citation_refs
from dicom_kb.query.conditions import effective_type_summary
from dicom_kb.query.graph import (
    attribute_context_uses,
    expand_macro_includes,
    find_attribute_element,
    resolve_context_iods,
)
from dicom_kb.query.resolver._identifiers import _looks_like_tag, _looks_like_uid


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
        return tool_response(
            edition=edition,
            tool="lookup_iod",
            input=response_input,
            status="not_found",
            result={"message": "No DICOM IOD matched the input."},
            trace=trace,
        )

    return tool_response(
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
            return tool_response(
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
        return tool_response(
            edition=edition,
            tool="lookup_sop_class",
            input=response_input,
            status="not_found",
            result={"message": "No DICOM SOP Class matched the input."},
            trace=trace,
        )

    sop_class, service_class = found
    iod_records = repository.list_iods_for_sop_class(sop_class.id, edition=edition)
    refs = (
        CitationBuilder()
        .add_group(
            "sop_class",
            (sop_class.source_ref, service_class.source_ref if service_class else None),
        )
        .add_group(
            "iod_links",
            (
                ref
                for record in iod_records
                for ref in (record.edge.source_ref, record.iod.source_ref)
            ),
        )
        .refs()
    )
    warnings = [
        record.edge.resolution_warning
        for record in iod_records
        if record.edge.resolution_warning is not None
    ]
    return tool_response(
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
        return tool_response(
            edition=edition,
            tool="list_modules_for_iod",
            input=response_input,
            status="not_found",
            result={"message": "No DICOM IOD matched the input."},
            trace=trace,
        )

    records = repository.list_module_uses_for_iod(iod.id, edition=edition)
    refs = (
        CitationBuilder()
        .add_group("iod", (iod.source_ref,))
        .add_group(
            "module_uses",
            (
                ref
                for record in records
                for ref in (
                    record.use.source_ref,
                    record.module.source_ref,
                    (
                        record.condition.source_ref
                        if record.condition is not None
                        else None
                    ),
                )
            ),
        )
        .refs()
    )
    return tool_response(
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
        return tool_response(
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
    refs = (
        CitationBuilder()
        .add_group("module", (module.source_ref,))
        .add_group(
            "attribute_uses",
            (
                ref
                for record in records
                for ref in (
                    record.attribute_use.source_ref,
                    (
                        record.condition.source_ref
                        if record.condition is not None
                        else None
                    ),
                    record.included_macro.source_ref
                    if record.included_macro is not None
                    else None,
                    record.expanded_from_include.source_ref
                    if record.expanded_from_include is not None
                    else None,
                )
            ),
        )
        .refs()
    )
    return tool_response(
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
        return tool_response(
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
            return tool_response(
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
            return tool_response(
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
        return tool_response(
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
    refs = citation_refs(
        (element.source_ref,),
        context_refs,
        use_refs,
    )
    return tool_response(
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


def _context_input(
    attribute: str, *, iod_name: str | None, sop_class: str | None
) -> dict[str, str]:
    response_input = {"attribute": attribute}
    if iod_name is not None:
        response_input["iod_name"] = iod_name
    if sop_class is not None:
        response_input["sop_class"] = sop_class
    return response_input
