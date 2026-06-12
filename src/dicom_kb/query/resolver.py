"""SQLite-backed deterministic query resolvers."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from dicom_kb.db.repositories import (
    AttributeUseRecord,
    DataElementRepository,
    IODModuleUseRecord,
    Part03Repository,
    Part04Repository,
    UIDRepository,
)
from dicom_kb.ir.models import IOD, AttributeUse, DataElement, Module
from dicom_kb.ir.validators import (
    IdentifierValidationError,
    normalize_tag,
    normalize_uid,
)
from dicom_kb.query.answer_contracts import (
    ResponseTrace,
    StandardRef,
    ToolResponse,
    attribute_context_result,
    data_element_result,
    iod_modules_result,
    iod_result,
    module_attributes_result,
    sop_class_result,
    standard_ref,
    uid_result,
)


@dataclass(frozen=True)
class _AttributeContextMatch:
    payload: dict[str, Any]
    type_designation: str | None


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


def lookup_iod(
    connection: sqlite3.Connection,
    *,
    iod_name: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve a PS3.3 IOD by name or keyword."""
    trace = _trace(
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
    trace = _trace(
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
    refs = _unique_refs(
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
    trace = _trace(
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
    refs = _unique_refs(
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
    trace = _trace(
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
        records, warnings = _expand_macro_includes(
            repository,
            records,
            edition=edition,
        )
    refs = _unique_refs(
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
    trace = _trace(
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

    element, element_warning = DataElementRepository(
        connection
    ).find_by_tag_or_keyword(attribute, edition=edition)
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
    context = _resolve_context_iods(
        connection,
        part03,
        iod_name=iod_name,
        sop_class=sop_class,
        edition=edition,
    )
    if isinstance(context, ToolResponse):
        return context.model_copy(update={"input": response_input, "trace": trace})

    context_iods, context_refs, context_warnings = context
    uses, use_refs, expansion_warnings = _attribute_context_uses(
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
    effective_type, explanation, type_warnings = _effective_type_summary(uses)
    warnings.extend(type_warnings)
    refs = _unique_refs(
        [standard_ref(element.source_ref)] + context_refs + use_refs
    )
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


def _context_input(
    attribute: str, *, iod_name: str | None, sop_class: str | None
) -> dict[str, str]:
    response_input = {"attribute": attribute}
    if iod_name is not None:
        response_input["iod_name"] = iod_name
    if sop_class is not None:
        response_input["sop_class"] = sop_class
    return response_input


def _resolve_context_iods(
    connection: sqlite3.Connection,
    part03: Part03Repository,
    *,
    iod_name: str | None,
    sop_class: str | None,
    edition: str,
) -> (
    tuple[list[IOD], list[StandardRef], list[str]]
    | ToolResponse
):
    if iod_name is not None:
        iod = part03.find_iod_by_name_or_keyword(iod_name, edition=edition)
        if iod is None:
            return ToolResponse(
                edition=edition,
                tool="resolve_attribute_context",
                input={"attribute": "", "iod_name": iod_name},
                status="not_found",
                result={"message": "No DICOM IOD matched the context input."},
            )
        return [iod], [standard_ref(iod.source_ref)], []

    assert sop_class is not None
    part04 = Part04Repository(connection)
    found = part04.find_sop_class_by_uid_or_name(sop_class, edition=edition)
    if found is None:
        return ToolResponse(
            edition=edition,
            tool="resolve_attribute_context",
            input={"attribute": "", "sop_class": sop_class},
            status="not_found",
            result={"message": "No DICOM SOP Class matched the context input."},
        )
    resolved_sop_class, service_class = found
    iod_records = part04.list_iods_for_sop_class(
        resolved_sop_class.id, edition=edition
    )
    if not iod_records:
        return ToolResponse(
            edition=edition,
            tool="resolve_attribute_context",
            input={"attribute": "", "sop_class": sop_class},
            status="not_found",
            result={"message": "No IODs are linked to the SOP Class context."},
        )
    refs = _unique_refs(
        [standard_ref(resolved_sop_class.source_ref)]
        + (
            [standard_ref(service_class.source_ref)]
            if service_class is not None
            else []
        )
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
    return [record.iod for record in iod_records], refs, warnings


def _attribute_context_uses(
    repository: Part03Repository,
    iods: list[IOD],
    element: DataElement,
    *,
    edition: str,
) -> tuple[list[_AttributeContextMatch], list[StandardRef], list[str]]:
    uses: list[_AttributeContextMatch] = []
    refs: list[StandardRef] = []
    warnings: list[str] = []
    for iod in iods:
        module_records = repository.list_module_uses_for_iod(iod.id, edition=edition)
        for module_record in module_records:
            records = repository.list_attribute_uses(
                owner_type="module",
                owner_id=module_record.module.id,
                edition=edition,
            )
            expanded_records, expansion_warnings = _expand_macro_includes(
                repository,
                records,
                edition=edition,
            )
            warnings.extend(expansion_warnings)
            record_by_id = {
                record.attribute_use.id: record.attribute_use
                for record in expanded_records
            }
            for record in expanded_records:
                attribute_use = record.attribute_use
                if attribute_use.row_kind != "attribute":
                    continue
                if not _attribute_use_matches(element, attribute_use):
                    continue
                uses.append(
                    _AttributeContextMatch(
                        payload=_attribute_context_use_payload(
                            iod,
                            module_record.module,
                            module_record,
                            record,
                            record_by_id,
                        ),
                        type_designation=attribute_use.type_designation,
                    )
                )
                refs.extend(
                    [
                        standard_ref(iod.source_ref),
                        standard_ref(module_record.use.source_ref),
                        standard_ref(module_record.module.source_ref),
                        standard_ref(attribute_use.source_ref),
                    ]
                )
                if record.expanded_from_include is not None:
                    refs.append(standard_ref(record.expanded_from_include.source_ref))
                if record.included_macro is not None:
                    refs.append(standard_ref(record.included_macro.source_ref))
    return uses, _unique_refs(refs), warnings


def _attribute_use_matches(element: DataElement, attribute_use: AttributeUse) -> bool:
    if attribute_use.attribute_tag == element.tag:
        return True
    if attribute_use.attribute_name and attribute_use.attribute_name.lower() == (
        element.name.lower()
    ):
        return True
    if element.keyword and attribute_use.attribute_keyword:
        return attribute_use.attribute_keyword.lower() == element.keyword.lower()
    return False


def _attribute_context_use_payload(
    iod: IOD,
    module: Module,
    module_record: IODModuleUseRecord,
    record: AttributeUseRecord,
    record_by_id: dict[str, AttributeUse],
) -> dict[str, Any]:
    attribute_use = record.attribute_use
    module_use = module_record.use
    condition = None
    if (
        attribute_use.type_designation is not None
        and attribute_use.type_designation.endswith("C")
        and attribute_use.description_text
    ):
        condition = {
            "source_text": attribute_use.description_text,
            "machine_status": "raw_text",
        }
    return {
        "iod": iod.name,
        "module": module.name,
        "information_entity": module_use.information_entity,
        "module_usage": module_use.usage,
        "module_usage_condition_text": module_use.usage_condition_text,
        "attribute_use_id": attribute_use.id,
        "type_designation": attribute_use.type_designation,
        "sequence_path": _sequence_path(attribute_use, record_by_id),
        "via_macro": list(record.macro_path) if record.macro_path else None,
        "condition": condition,
    }


def _sequence_path(
    attribute_use: AttributeUse, record_by_id: dict[str, AttributeUse]
) -> list[str]:
    path: list[str] = []
    parent_id = attribute_use.parent_attribute_use_id
    while parent_id is not None:
        parent = record_by_id.get(parent_id)
        if parent is None:
            break
        path.append(parent.attribute_name or parent.attribute_tag or parent.id)
        parent_id = parent.parent_attribute_use_id
    return list(reversed(path))


_TYPE_RANK = {
    "1": 0,
    "1C": 1,
    "2": 2,
    "2C": 3,
    "3": 4,
}


def _effective_type_summary(
    uses: list[_AttributeContextMatch],
) -> tuple[str | None, str, list[str]]:
    if not uses:
        return (
            None,
            "Attribute is not listed in the resolved context.",
            [],
        )
    type_values = [
        use.type_designation
        for use in uses
        if use.type_designation is not None
    ]
    if not type_values:
        return None, "Matched uses do not declare a type designation.", []

    ranked = [
        value
        for value in type_values
        if value in _TYPE_RANK
    ]
    if not ranked:
        return (
            None,
            "Matched uses only declare unrecognized type designations.",
            [
                "could not compute effective type from unrecognized "
                f"type designations: {', '.join(sorted(set(type_values)))}"
            ],
        )
    effective_type = min(ranked, key=lambda value: _TYPE_RANK[value])
    if len(type_values) == 1:
        return (
            effective_type,
            "Single applicable use in resolved context.",
            [],
        )
    explanation = (
        "Multiple applicable uses in resolved context; selected the lowest "
        "DICOM type value among recognized designations."
    )
    warnings = [
        "effective type assumes no attribute description overrides the "
        "multiple-module lowest-type rule"
    ]
    unrecognized = sorted(set(type_values) - set(ranked))
    if unrecognized:
        warnings.append(
            "ignored unrecognized type designations while computing effective "
            f"type: {', '.join(unrecognized)}"
        )
    return effective_type, explanation, warnings


def _expand_macro_includes(
    repository: Part03Repository,
    records: list[AttributeUseRecord],
    *,
    edition: str,
) -> tuple[list[AttributeUseRecord], list[str]]:
    expanded: list[AttributeUseRecord] = []
    warnings: list[str] = []
    for record in records:
        expanded.append(record)
        if record.attribute_use.row_kind != "include" or record.included_macro is None:
            continue
        expanded.extend(
            _expand_macro_record(
                repository,
                include_record=record,
                edition=edition,
                depth_offset=record.attribute_use.sequence_depth,
                macro_stack=(record.included_macro.id,),
                warnings=warnings,
            )
        )
    return expanded, warnings


def _expand_macro_record(
    repository: Part03Repository,
    *,
    include_record: AttributeUseRecord,
    edition: str,
    depth_offset: int,
    macro_stack: tuple[str, ...],
    warnings: list[str],
) -> list[AttributeUseRecord]:
    if include_record.included_macro is None:
        return []

    expanded: list[AttributeUseRecord] = []
    macro_records = repository.list_attribute_uses(
        owner_type="macro",
        owner_id=include_record.included_macro.id,
        edition=edition,
    )
    for macro_record in macro_records:
        effective_record = _effective_macro_record(
            macro_record,
            macro_name=include_record.included_macro.name,
            expanded_from_include=include_record.attribute_use,
            depth_offset=depth_offset,
        )
        expanded.append(effective_record)
        if (
            effective_record.attribute_use.row_kind != "include"
            or effective_record.included_macro is None
        ):
            continue
        if effective_record.included_macro.id in macro_stack:
            warnings.append(
                "skipped recursive macro include cycle: "
                + " -> ".join((*macro_stack, effective_record.included_macro.id))
            )
            continue
        expanded.extend(
            _expand_macro_record(
                repository,
                include_record=effective_record,
                edition=edition,
                depth_offset=effective_record.attribute_use.sequence_depth,
                macro_stack=(*macro_stack, effective_record.included_macro.id),
                warnings=warnings,
            )
        )
    return expanded


def _effective_macro_record(
    record: AttributeUseRecord,
    *,
    macro_name: str,
    expanded_from_include: AttributeUse,
    depth_offset: int,
) -> AttributeUseRecord:
    return AttributeUseRecord(
        attribute_use=record.attribute_use.model_copy(
            update={
                "sequence_depth": record.attribute_use.sequence_depth + depth_offset
            }
        ),
        owner_type="macro",
        owner_name=macro_name,
        included_macro=record.included_macro,
        expanded_from_include=expanded_from_include,
        macro_path=(*record.macro_path, macro_name),
    )


def _unique_refs(refs: list[StandardRef]) -> list[StandardRef]:
    unique: dict[tuple[tuple[str, object], ...], StandardRef] = {}
    for ref in refs:
        key = tuple(ref.model_dump(mode="json").items())
        unique[key] = ref
    return list(unique.values())
