"""Context-aware enumerated value and defined term queries."""

from __future__ import annotations

import sqlite3

from dicom_kb.db.repositories import (
    AttributeValueTermRecord,
    AttributeValueTermRepository,
    DataElementRepository,
    Part03Repository,
)
from dicom_kb.ir.models import (
    DataElement,
)
from dicom_kb.ir.validators import (
    IdentifierValidationError,
    normalize_tag,
)
from dicom_kb.query.answer_contracts import (
    StandardRef,
    ToolResponse,
    attribute_value_terms_result,
    data_element_result,
    standard_ref,
    tool_response,
)
from dicom_kb.query.citations import citation_refs
from dicom_kb.query.graph import (
    attribute_context_uses,
    resolve_context_iods,
)
from dicom_kb.query.resolver._identifiers import _looks_like_tag


def lookup_enumerated_values(
    connection: sqlite3.Connection,
    *,
    attribute: str,
    edition: str,
    context: str | None = None,
) -> ToolResponse:
    """Return parsed enumerated values for a DICOM attribute."""
    return _lookup_attribute_value_terms(
        connection,
        attribute=attribute,
        edition=edition,
        term_kind="enumerated_value",
        context=context,
    )


def lookup_defined_terms(
    connection: sqlite3.Connection,
    *,
    attribute: str,
    edition: str,
    context: str | None = None,
) -> ToolResponse:
    """Return parsed defined terms for a DICOM attribute."""
    return _lookup_attribute_value_terms(
        connection,
        attribute=attribute,
        edition=edition,
        term_kind="defined_term",
        context=context,
    )


def _lookup_attribute_value_terms(
    connection: sqlite3.Connection,
    *,
    attribute: str,
    edition: str,
    term_kind: str,
    context: str | None,
) -> ToolResponse:
    if _looks_like_tag(attribute):
        try:
            normalize_tag(attribute)
        except IdentifierValidationError as exc:
            return tool_response(
                status="validation_error",
                result={"message": str(exc)},
            )

    element, element_warning = DataElementRepository(connection).find_by_tag_or_keyword(
        attribute,
        edition=edition,
    )
    if element is None:
        return tool_response(
            status="not_found",
            result={"message": "No DICOM data element matched the attribute input."},
        )

    context_attribute_use_ids: tuple[str, ...] | None = None
    context_refs: list[StandardRef] = []
    context_warnings: list[str] = []
    if context is not None:
        (
            context_attribute_use_ids,
            context_refs,
            context_warnings,
        ) = _value_term_context_attribute_use_ids(
            connection,
            element=element,
            context=context,
            edition=edition,
        )

    records = AttributeValueTermRepository(connection).list_terms_for_attribute(
        attribute=attribute,
        term_kind=term_kind,
        edition=edition,
        context=context,
        attribute_use_ids=context_attribute_use_ids,
    )
    warnings = [
        warning
        for warning in [element_warning, *context_warnings]
        if warning is not None
    ]
    if not records:
        return tool_response(
            status="not_found",
            result={"message": "No parsed value terms matched the input."},
            refs=citation_refs((element.source_ref,), context_refs),
            warnings=warnings,
        )

    refs = citation_refs(
        (element.source_ref,),
        context_refs,
        (record.term.source_ref for record in records),
    )
    if context is not None:
        candidates = _attribute_value_term_context_candidates(records)
        if len(candidates) > 1:
            return tool_response(
                status="validation_error",
                result={
                    "message": "Context input matched multiple value-term contexts.",
                    "attribute": data_element_result(element),
                    "candidates": candidates,
                },
                refs=refs,
                warnings=warnings,
            )

    return tool_response(
        status="ok",
        result=attribute_value_terms_result(element, records),
        refs=refs,
        warnings=warnings,
    )


def _attribute_value_term_context_candidates(
    records: list[AttributeValueTermRecord],
) -> list[dict[str, object]]:
    grouped_records: dict[tuple[str | None, str | None], list[AttributeValueTermRecord]]
    grouped_records = {}
    for record in records:
        key = (record.term.attribute_use_id, record.term.context_label)
        grouped_records.setdefault(key, []).append(record)

    candidates: list[dict[str, object]] = []
    for attribute_use_id, context_label in grouped_records:
        candidate_records = grouped_records[(attribute_use_id, context_label)]
        candidates.append(
            {
                "context_label": context_label,
                "attribute_use_id": attribute_use_id,
                "terms": [
                    {
                        "value": record.term.value,
                        "meaning": record.term.meaning,
                        "term_kind": record.term.term_kind,
                    }
                    for record in candidate_records
                ],
            }
        )
    return candidates


def _value_term_context_attribute_use_ids(
    connection: sqlite3.Connection,
    *,
    element: DataElement,
    context: str,
    edition: str,
) -> tuple[tuple[str, ...] | None, list[StandardRef], list[str]]:
    part03 = Part03Repository(connection)
    iod = part03.find_iod_by_name_or_keyword(context, edition=edition)
    if iod is not None:
        context_iods = [iod]
        context_refs = [standard_ref(iod.source_ref)]
        context_warnings: list[str] = []
    else:
        resolved_context = resolve_context_iods(
            connection,
            part03,
            iod_name=None,
            sop_class=context,
            edition=edition,
        )
        if isinstance(resolved_context, ToolResponse):
            return None, [], []
        context_iods, context_refs, context_warnings = resolved_context

    uses, use_refs, expansion_warnings = attribute_context_uses(
        part03,
        context_iods,
        element,
        edition=edition,
    )
    attribute_use_ids = tuple(
        dict.fromkeys(
            str(use.payload["attribute_use_id"])
            for use in uses
            if use.payload.get("attribute_use_id") is not None
        )
    )
    return (
        attribute_use_ids,
        citation_refs(context_refs, use_refs),
        [*context_warnings, *expansion_warnings],
    )
