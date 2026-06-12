"""Condition and type-summary helpers for query responses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dicom_kb.db.repositories import (
    AttributeUseRecord,
    IODFunctionalGroupUseRecord,
    IODModuleUseRecord,
)
from dicom_kb.ir.models import IOD, AttributeUse, Module


@dataclass(frozen=True)
class AttributeContextMatch:
    """One matching attribute-use row in a resolved IOD/module context."""

    payload: dict[str, Any]
    type_designation: str | None


def build_attribute_context_use_payload(
    iod: IOD,
    module: Module,
    module_record: IODModuleUseRecord,
    record: AttributeUseRecord,
    record_by_id: dict[str, AttributeUse],
) -> dict[str, Any]:
    """Assemble the public payload for one contextual attribute use."""
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
        "sequence_path": sequence_path(attribute_use, record_by_id),
        "via_macro": list(record.macro_path) if record.macro_path else None,
        "condition": condition,
    }


def build_functional_group_context_use_payload(
    iod: IOD,
    functional_group_record: IODFunctionalGroupUseRecord,
    record: AttributeUseRecord,
    record_by_id: dict[str, AttributeUse],
) -> dict[str, Any]:
    """Assemble the public payload for a functional-group macro attribute use."""
    attribute_use = record.attribute_use
    functional_group_use = functional_group_record.use
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
        "module": None,
        "functional_group_macro": functional_group_record.macro.name,
        "information_entity": None,
        "module_usage": functional_group_use.usage,
        "module_usage_condition_text": functional_group_use.usage_condition_text,
        "attribute_use_id": attribute_use.id,
        "type_designation": attribute_use.type_designation,
        "sequence_path": sequence_path(attribute_use, record_by_id),
        "via_macro": list(record.macro_path) if record.macro_path else None,
        "condition": condition,
    }


def sequence_path(
    attribute_use: AttributeUse, record_by_id: dict[str, AttributeUse]
) -> list[str]:
    """Return the parent sequence chain for one attribute-use row."""
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


def effective_type_summary(
    uses: list[AttributeContextMatch],
) -> tuple[str | None, str, list[str]]:
    """Summarize the effective DICOM type across matching uses."""
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

    ranked = [value for value in type_values if value in _TYPE_RANK]
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
