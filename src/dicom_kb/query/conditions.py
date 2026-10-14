"""Condition and type-summary helpers for query responses."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from dicom_kb.db.repositories import (
    AttributeUseRecord,
    IODFunctionalGroupUseRecord,
    IODModuleUseRecord,
)
from dicom_kb.ir.models import IOD, AttributeUse, Condition, Module


@dataclass(frozen=True)
class AttributeContextMatch:
    """One matching attribute-use row in a resolved IOD/module context."""

    payload: dict[str, Any]
    type_designation: str | None
    description_text: str | None = None
    condition_text: str | None = None
    source_ref_id: str | None = None


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
    condition = condition_payload(record.condition)
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
    condition = condition_payload(record.condition)
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


def condition_payload(condition: Condition | None) -> dict[str, Any] | None:
    """Return the public raw condition payload for an unresolved condition."""
    if condition is None:
        return None
    return {
        "source_text": condition.raw_text,
        "condition_kind": condition.condition_kind,
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

_EXPLICIT_TYPE_OVERRIDE_RE = re.compile(
    r"\b(?:shall\s+be|is|are)\s+Type\s+(1C|2C|1|2|3)\b"
    r"(?:\s+in\s+this\s+module)?",
    re.IGNORECASE,
)
_TYPE_MENTION_RE = re.compile(r"\bType\s+(1C|2C|1|2|3)\b", re.IGNORECASE)
_AMBIGUOUS_TYPE_CUE_RE = re.compile(
    r"\b(?:and|or|and/or|may|might|could|except|unless|depending|otherwise)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _TypeOverrideCandidate:
    """Potential effective-type override language in stored row text."""

    type_designation: str
    source_ref_id: str
