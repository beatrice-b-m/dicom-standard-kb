"""SQLite-backed deterministic query resolvers."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from dicom_kb.db.repositories import (
    AttributeUseRecord,
    DataElementRepository,
    Part03Repository,
    UIDRepository,
)
from dicom_kb.ir.models import AttributeUse
from dicom_kb.ir.validators import (
    IdentifierValidationError,
    normalize_tag,
    normalize_uid,
)
from dicom_kb.query.answer_contracts import (
    ResponseTrace,
    StandardRef,
    ToolResponse,
    data_element_result,
    iod_modules_result,
    module_attributes_result,
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
    )


def _unique_refs(refs: list[StandardRef]) -> list[StandardRef]:
    unique: dict[tuple[tuple[str, object], ...], StandardRef] = {}
    for ref in refs:
        key = tuple(ref.model_dump(mode="json").items())
        unique[key] = ref
    return list(unique.values())
