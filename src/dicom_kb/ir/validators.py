"""Validation helpers for normalized DICOM identifiers."""

from __future__ import annotations

import re

from dicom_kb.docbook.text_chunks import normalize_text

TAG_RE = re.compile(r"^\(([0-9A-Fa-fxX]{4}),([0-9A-Fa-fxX]{4})\)$")
UID_RE = re.compile(r"^\d+(?:\.\d+)*$")


class IdentifierValidationError(ValueError):
    """Raised when an identifier cannot be normalized."""


def normalize_tag(tag: str) -> str:
    """Normalize a DICOM tag, preserving lowercase x range placeholders."""
    compact = normalize_text(tag).replace(" ", "")
    match = TAG_RE.match(compact)
    if not match:
        raise IdentifierValidationError(f"malformed DICOM tag: {tag!r}")
    group = _normalize_tag_part(match.group(1))
    element = _normalize_tag_part(match.group(2))
    return f"({group},{element})"


def split_tag(tag: str) -> tuple[str, str, bool]:
    """Return normalized group, element, and range status for a tag."""
    normalized = normalize_tag(tag)
    group = normalized[1:5]
    element = normalized[6:10]
    return group, element, "x" in group or "x" in element


def normalize_uid(uid: str) -> str:
    """Normalize a DICOM UID string."""
    normalized = normalize_text(uid)
    if not UID_RE.match(normalized):
        raise IdentifierValidationError(f"malformed DICOM UID: {uid!r}")
    return normalized


def tag_matches(pattern: str, candidate: str) -> bool:
    """Return whether a concrete tag matches an exact or range tag pattern."""
    normalized_pattern = normalize_tag(pattern)
    normalized_candidate = normalize_tag(candidate)
    for pattern_char, candidate_char in zip(
        normalized_pattern, normalized_candidate, strict=True
    ):
        if pattern_char == "x":
            if candidate_char not in "0123456789ABCDEF":
                return False
            continue
        if pattern_char != candidate_char:
            return False
    return True


def _normalize_tag_part(value: str) -> str:
    return "".join("x" if char in {"x", "X"} else char.upper() for char in value)
