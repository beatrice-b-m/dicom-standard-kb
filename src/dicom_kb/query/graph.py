"""Graph and macro-expansion helpers for PS3.3 query traversal."""

from __future__ import annotations

import sqlite3

from dicom_kb.db.repositories import (
    AttributeUseRecord,
    DataElementRepository,
    Part03Repository,
    Part04Repository,
)
from dicom_kb.ir.models import IOD, AttributeUse, DataElement
from dicom_kb.query.answer_contracts import StandardRef, ToolResponse, standard_ref
from dicom_kb.query.citations import unique_refs
from dicom_kb.query.conditions import (
    AttributeContextMatch,
    build_attribute_context_use_payload,
)


def expand_macro_includes(
    repository: Part03Repository,
    records: list[AttributeUseRecord],
    *,
    edition: str,
) -> tuple[list[AttributeUseRecord], list[str]]:
    """Expand module or macro include rows into a flat attribute-use stream."""
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


def resolve_context_iods(
    connection: sqlite3.Connection,
    part03: Part03Repository,
    *,
    iod_name: str | None,
    sop_class: str | None,
    edition: str,
) -> tuple[list[IOD], list[StandardRef], list[str]] | ToolResponse:
    """Resolve the IOD set for either an IOD or SOP Class context input."""
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
    refs = unique_refs(
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


def attribute_context_uses(
    repository: Part03Repository,
    iods: list[IOD],
    element: DataElement,
    *,
    edition: str,
) -> tuple[list[AttributeContextMatch], list[StandardRef], list[str]]:
    """Collect matching attribute uses across resolved IOD contexts."""
    uses: list[AttributeContextMatch] = []
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
            expanded_records, expansion_warnings = expand_macro_includes(
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
                if not attribute_use_matches(element, attribute_use):
                    continue
                uses.append(
                    AttributeContextMatch(
                        payload=build_attribute_context_use_payload(
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
    return uses, unique_refs(refs), warnings


def find_attribute_element(
    connection: sqlite3.Connection,
    *,
    attribute: str,
    edition: str,
) -> tuple[DataElement | None, str | None]:
    """Resolve the attribute identifier through the PS3.6 dictionary."""
    return DataElementRepository(connection).find_by_tag_or_keyword(
        attribute, edition=edition
    )


def attribute_use_matches(element: DataElement, attribute_use: AttributeUse) -> bool:
    """Match an attribute-use row to a PS3.6 data element identity."""
    if attribute_use.attribute_tag == element.tag:
        return True
    if attribute_use.attribute_name and attribute_use.attribute_name.lower() == (
        element.name.lower()
    ):
        return True
    if element.keyword and attribute_use.attribute_keyword:
        return attribute_use.attribute_keyword.lower() == element.keyword.lower()
    return False


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
