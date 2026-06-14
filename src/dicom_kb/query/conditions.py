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
from dicom_kb.query.answer_contracts import standard_ref


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
        "condition_id": condition.id,
        "source_text": condition.raw_text,
        "condition_kind": condition.condition_kind,
        "machine_status": condition.machine_status,
        "dependencies": [],
        "evaluator": {"available": False},
        "refs": [standard_ref(condition.source_ref).model_dump(mode="json")],
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


def _normalize_type_designation(value: str) -> str:
    return value.upper()


def _match_source_id(use: AttributeContextMatch) -> str:
    return use.source_ref_id or str(use.payload.get("attribute_use_id", "unknown"))


def _override_candidates(
    uses: list[AttributeContextMatch],
) -> tuple[list[_TypeOverrideCandidate], list[str]]:
    explicit: list[_TypeOverrideCandidate] = []
    ambiguous_source_refs: list[str] = []
    for use in uses:
        source_ref_id = _match_source_id(use)
        for text in (use.description_text, use.condition_text):
            if not text:
                continue
            explicit_matches = [
                _normalize_type_designation(match.group(1))
                for match in _EXPLICIT_TYPE_OVERRIDE_RE.finditer(text)
            ]
            explicit.extend(
                _TypeOverrideCandidate(
                    type_designation=value,
                    source_ref_id=source_ref_id,
                )
                for value in explicit_matches
            )
            if explicit_matches:
                continue
            type_mentions = [
                _normalize_type_designation(match.group(1))
                for match in _TYPE_MENTION_RE.finditer(text)
            ]
            if type_mentions and (
                len(set(type_mentions)) > 1 or _AMBIGUOUS_TYPE_CUE_RE.search(text)
            ):
                ambiguous_source_refs.append(source_ref_id)
    return explicit, sorted(set(ambiguous_source_refs))


def _format_override_candidates(candidates: list[_TypeOverrideCandidate]) -> str:
    return ", ".join(
        f"Type {candidate.type_designation} in {candidate.source_ref_id}"
        for candidate in candidates
    )


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
        use.type_designation for use in uses if use.type_designation is not None
    ]
    if not type_values:
        return None, "Matched uses do not declare a type designation.", []

    explicit_overrides, ambiguous_source_refs = _override_candidates(uses)
    if ambiguous_source_refs:
        return (
            None,
            "Ambiguous type override language was found in matched row text.",
            [
                "ambiguous type override language found in source refs: "
                f"{', '.join(ambiguous_source_refs)}"
            ],
        )
    if explicit_overrides:
        override_types = {
            candidate.type_designation for candidate in explicit_overrides
        }
        if len(override_types) == 1:
            effective_type = next(iter(override_types))
            source_refs = sorted(
                {candidate.source_ref_id for candidate in explicit_overrides}
            )
            return (
                effective_type,
                "Explicit type override language selected Type "
                f"{effective_type} from source refs: {', '.join(source_refs)}.",
                [],
            )
        return (
            None,
            "Conflicting explicit type override language was found in matched "
            "row text.",
            [
                "conflicting explicit type overrides found: "
                f"{_format_override_candidates(explicit_overrides)}"
            ],
        )

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
    warnings: list[str] = []
    unrecognized = sorted(set(type_values) - set(ranked))
    if unrecognized:
        warnings.append(
            "ignored unrecognized type designations while computing effective "
            f"type: {', '.join(unrecognized)}"
        )
    return effective_type, explanation, warnings
