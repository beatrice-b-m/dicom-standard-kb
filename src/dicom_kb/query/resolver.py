"""SQLite-backed deterministic query resolvers."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from dicom_kb.db.repositories import (
    AttributeValueTermRepository,
    DataElementRepository,
    DocumentRepository,
    Part03Repository,
    Part04Repository,
    Part05Repository,
    Part10Repository,
    UIDRepository,
)
from dicom_kb.ir.models import DicomMediaType, TransferSyntaxDetail, VRDefinition
from dicom_kb.ir.validators import (
    IdentifierValidationError,
    normalize_tag,
    normalize_uid,
)
from dicom_kb.query.answer_contracts import (
    ToolResponse,
    attribute_context_result,
    attribute_value_terms_result,
    data_element_result,
    dicom_media_type_result,
    encoding_rule_explanation_result,
    iod_modules_result,
    iod_result,
    module_attributes_result,
    sop_class_result,
    standard_ref,
    standard_text_result,
    standard_text_search_result,
    tool_response,
    transfer_syntax_detail_result,
    uid_result,
    vr_definition_result,
)
from dicom_kb.query.citations import CitationBuilder, build_trace, citation_refs
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
            return tool_response(
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
        return tool_response(
            edition=edition,
            tool="lookup_data_element",
            input=response_input,
            status="not_found",
            result={"message": "No DICOM data element matched the input."},
            trace=trace,
        )

    warnings = [warning] if warning else []
    return tool_response(
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
            return tool_response(
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
        return tool_response(
            edition=edition,
            tool="lookup_uid",
            input=response_input,
            status="not_found",
            result={"message": "No DICOM UID registry entry matched the input."},
            trace=trace,
        )

    return tool_response(
        edition=edition,
        tool="lookup_uid",
        input=response_input,
        status="ok",
        result=uid_result(uid),
        refs=[standard_ref(uid.source_ref)],
        trace=trace,
    )


def lookup_vr(
    connection: sqlite3.Connection,
    *,
    vr: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve a PS3.5 Value Representation definition by VR code."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"vr": vr}
    normalized_vr = vr.strip().upper()
    if not _is_vr_code(normalized_vr):
        return tool_response(
            edition=edition,
            tool="lookup_vr",
            input=response_input,
            status="validation_error",
            result={"message": "vr must be a two-letter DICOM VR code."},
            trace=trace,
        )

    definition = Part05Repository(connection).find_vr(normalized_vr, edition=edition)
    if definition is None:
        return tool_response(
            edition=edition,
            tool="lookup_vr",
            input=response_input,
            status="not_found",
            result={"message": "No PS3.5 VR definition matched the input."},
            trace=trace,
        )

    return tool_response(
        edition=edition,
        tool="lookup_vr",
        input=response_input,
        status="ok",
        result=vr_definition_result(
            vr=definition.vr,
            name=definition.name,
            value_representation_class=definition.value_representation_class,
            length_notes=list(definition.length_notes),
            padding_behavior=definition.padding_behavior,
            character_repertoire_notes=list(definition.character_repertoire_notes),
            binary_or_text=definition.binary_or_text,
        ),
        refs=[standard_ref(definition.source_ref)],
        trace=trace,
    )


def lookup_transfer_syntax(
    connection: sqlite3.Connection,
    *,
    uid_or_keyword: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve a transfer syntax UID with deterministic encoding details."""
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
            return tool_response(
                edition=edition,
                tool="lookup_transfer_syntax",
                input=response_input,
                status="validation_error",
                result={"message": str(exc)},
                trace=trace,
            )

    record = Part05Repository(connection).find_transfer_syntax(
        uid_or_keyword,
        edition=edition,
    )
    if record is None:
        return tool_response(
            edition=edition,
            tool="lookup_transfer_syntax",
            input=response_input,
            status="not_found",
            result={"message": "No transfer syntax detail matched the input."},
            trace=trace,
        )

    return tool_response(
        edition=edition,
        tool="lookup_transfer_syntax",
        input=response_input,
        status="ok",
        result=transfer_syntax_detail_result(
            uid_value=record.uid.uid_value,
            uid_name=record.uid.uid_name,
            uid_keyword=record.uid.uid_keyword,
            explicit_vr=record.detail.explicit_vr,
            endian=record.detail.endian,
            encapsulated=record.detail.encapsulated,
            compression_family=record.detail.compression_family,
            retired=record.uid.retired,
            encoding_notes=list(record.detail.encoding_notes),
        ),
        refs=citation_refs(
            (record.uid.source_ref,),
            (record.detail.source_ref,),
        ),
        trace=trace,
    )


def explain_encoding_rule(
    connection: sqlite3.Connection,
    *,
    topic: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Explain a PS3.5 encoding topic using parsed rows or cited text."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"topic": topic}
    normalized_topic = topic.strip()
    if not normalized_topic:
        return tool_response(
            edition=edition,
            tool="explain_encoding_rule",
            input=response_input,
            status="validation_error",
            result={"message": "topic must not be empty."},
            trace=trace,
        )

    repository = Part05Repository(connection)
    normalized_vr = normalized_topic.upper()
    if _is_vr_code(normalized_vr):
        definition = repository.find_vr(normalized_vr, edition=edition)
        if definition is not None:
            return tool_response(
                edition=edition,
                tool="explain_encoding_rule",
                input=response_input,
                status="ok",
                result=encoding_rule_explanation_result(
                    topic=topic,
                    summary=f"{definition.vr} is the {definition.name} VR.",
                    structured_facts=_vr_structured_facts(definition),
                ),
                refs=[standard_ref(definition.source_ref)],
                trace=trace,
            )

    transfer_syntax = repository.find_transfer_syntax(
        normalized_topic,
        edition=edition,
    )
    if transfer_syntax is not None:
        return tool_response(
            edition=edition,
            tool="explain_encoding_rule",
            input=response_input,
            status="ok",
            result=encoding_rule_explanation_result(
                topic=topic,
                summary=(
                    f"{transfer_syntax.uid.uid_name} is a transfer syntax "
                    "with parsed encoding details."
                ),
                structured_facts=_transfer_syntax_structured_facts(
                    transfer_syntax.detail
                ),
            ),
            refs=citation_refs(
                (transfer_syntax.uid.source_ref,),
                (transfer_syntax.detail.source_ref,),
            ),
            trace=trace,
        )

    fts_query = build_fts_query(normalized_topic)
    if fts_query is None:
        return tool_response(
            edition=edition,
            tool="explain_encoding_rule",
            input=response_input,
            status="validation_error",
            result={"message": "topic must contain at least one searchable term."},
            trace=trace,
        )

    matches = DocumentRepository(connection).search_text(
        fts_query=fts_query,
        edition=edition,
        part_filter="PS3.5",
        limit=1,
    )
    if not matches:
        return tool_response(
            edition=edition,
            tool="explain_encoding_rule",
            input=response_input,
            status="not_found",
            result={"message": "No PS3.5 encoding rule matched the topic."},
            trace=trace,
        )

    match = matches[0]
    excerpt = (match.node.plain_text or match.snippet)[:800]
    return tool_response(
        edition=edition,
        tool="explain_encoding_rule",
        input=response_input,
        status="ok",
        result=encoding_rule_explanation_result(
            topic=topic,
            summary=f"Retrieved PS3.5 text for {normalized_topic}.",
            text_excerpt=excerpt,
        ),
        refs=[standard_ref(match.node.source_ref)],
        trace=trace,
    )


def lookup_media_type(
    connection: sqlite3.Connection,
    *,
    media_type_or_context: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve a PS3.10 DICOM media-type row by media type or context."""
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


def lookup_enumerated_values(
    connection: sqlite3.Connection,
    *,
    attribute: str,
    edition: str,
    context: str | None = None,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Return parsed enumerated values for a DICOM attribute."""
    return _lookup_attribute_value_terms(
        connection,
        attribute=attribute,
        edition=edition,
        term_kind="enumerated_value",
        tool="lookup_enumerated_values",
        context=context,
        query_id=query_id,
        resolved_at=resolved_at,
    )


def lookup_defined_terms(
    connection: sqlite3.Connection,
    *,
    attribute: str,
    edition: str,
    context: str | None = None,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Return parsed defined terms for a DICOM attribute."""
    return _lookup_attribute_value_terms(
        connection,
        attribute=attribute,
        edition=edition,
        term_kind="defined_term",
        tool="lookup_defined_terms",
        context=context,
        query_id=query_id,
        resolved_at=resolved_at,
    )


def _lookup_attribute_value_terms(
    connection: sqlite3.Connection,
    *,
    attribute: str,
    edition: str,
    term_kind: str,
    tool: str,
    context: str | None,
    query_id: str | None,
    resolved_at: datetime | None,
) -> ToolResponse:
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"attribute": attribute}
    if context is not None:
        response_input["context"] = context
    if _looks_like_tag(attribute):
        try:
            normalize_tag(attribute)
        except IdentifierValidationError as exc:
            return tool_response(
                edition=edition,
                tool=tool,
                input=response_input,
                status="validation_error",
                result={"message": str(exc)},
                trace=trace,
            )

    element, element_warning = DataElementRepository(connection).find_by_tag_or_keyword(
        attribute,
        edition=edition,
    )
    if element is None:
        return tool_response(
            edition=edition,
            tool=tool,
            input=response_input,
            status="not_found",
            result={"message": "No DICOM data element matched the attribute input."},
            trace=trace,
        )

    records = AttributeValueTermRepository(connection).list_terms_for_attribute(
        attribute=attribute,
        term_kind=term_kind,
        edition=edition,
        context=context,
    )
    if not records:
        return tool_response(
            edition=edition,
            tool=tool,
            input=response_input,
            status="not_found",
            result={"message": "No parsed value terms matched the input."},
            refs=[standard_ref(element.source_ref)],
            warnings=[element_warning] if element_warning else [],
            trace=trace,
        )

    refs = citation_refs(
        (element.source_ref,),
        (record.term.source_ref for record in records),
    )
    return tool_response(
        edition=edition,
        tool=tool,
        input=response_input,
        status="ok",
        result=attribute_value_terms_result(element, records),
        refs=refs,
        warnings=[element_warning] if element_warning else [],
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
        return tool_response(
            edition=edition,
            tool="retrieve_standard_text",
            input=response_input,
            status="validation_error",
            result={"message": "part must be a DICOM part label such as PS3.3."},
            trace=trace,
        )
    if max_chars < 1 or max_chars > 4000:
        return tool_response(
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
        return tool_response(
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
    refs = citation_refs(
        (node.source_ref,),
        (table.source_ref for table in tables),
    )
    return tool_response(
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
        return tool_response(
            edition=edition,
            tool="search_standard_text",
            input=response_input,
            status="validation_error",
            result={"message": "query must not be empty."},
            trace=trace,
        )
    if len(query) > 200:
        return tool_response(
            edition=edition,
            tool="search_standard_text",
            input=response_input,
            status="validation_error",
            result={"message": "query must be 200 characters or fewer."},
            trace=trace,
        )
    if part_filter is not None and not part_filter.startswith("PS3."):
        return tool_response(
            edition=edition,
            tool="search_standard_text",
            input=response_input,
            status="validation_error",
            result={"message": "part_filter must be a DICOM part label such as PS3.3."},
            trace=trace,
        )
    if limit < 1 or limit > 50:
        return tool_response(
            edition=edition,
            tool="search_standard_text",
            input=response_input,
            status="validation_error",
            result={"message": "limit must be between 1 and 50."},
            trace=trace,
        )

    fts_query = build_fts_query(query)
    if fts_query is None:
        return tool_response(
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
        return tool_response(
            edition=edition,
            tool="search_standard_text",
            input=response_input,
            status="not_found",
            result={"message": "No standard text matched the query."},
            trace=trace,
        )

    return tool_response(
        edition=edition,
        tool="search_standard_text",
        input=response_input,
        status="ok",
        result=standard_text_search_result(records),
        refs=citation_refs(record.node.source_ref for record in records),
        trace=trace,
    )


def _looks_like_tag(value: str) -> bool:
    return any(marker in value for marker in ("(", ")", ","))


def _looks_like_uid(value: str) -> bool:
    return bool(value) and "." in value and value[0].isdigit()


def _is_vr_code(value: str) -> bool:
    return len(value) == 2 and value.isalpha() and value.isupper()


def _vr_structured_facts(definition: VRDefinition) -> list[str]:
    facts = [f"name: {definition.name}"]
    if definition.value_representation_class is not None:
        facts.append(
            f"value representation class: {definition.value_representation_class}"
        )
    if definition.binary_or_text is not None:
        facts.append(f"binary or text: {definition.binary_or_text}")
    if definition.padding_behavior is not None:
        facts.append(f"padding behavior: {definition.padding_behavior}")
    facts.extend(f"length note: {note}" for note in definition.length_notes)
    facts.extend(
        f"character repertoire note: {note}"
        for note in definition.character_repertoire_notes
    )
    return facts


def _transfer_syntax_structured_facts(
    detail: TransferSyntaxDetail,
) -> list[str]:
    facts: list[str] = []
    if detail.explicit_vr is not None:
        facts.append(f"explicit VR: {str(detail.explicit_vr).lower()}")
    if detail.endian is not None:
        facts.append(f"endian: {detail.endian}")
    if detail.encapsulated is not None:
        facts.append(f"encapsulated: {str(detail.encapsulated).lower()}")
    if detail.compression_family is not None:
        facts.append(f"compression family: {detail.compression_family}")
    facts.extend(f"encoding note: {note}" for note in detail.encoding_notes)
    return facts


def _media_type_result(record: DicomMediaType) -> dict[str, object]:
    return dicom_media_type_result(
        media_type=record.media_type,
        service_context=record.service_context,
        transfer_syntax_constraints=list(record.transfer_syntax_constraints),
        directions=list(record.directions),
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
