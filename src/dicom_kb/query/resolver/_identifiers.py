"""Internal identifier-shape hints for response validation."""

from __future__ import annotations


def _looks_like_tag(value: str) -> bool:
    return any(marker in value for marker in ("(", ")", ","))


def _looks_like_uid(value: str) -> bool:
    return bool(value) and "." in value and value[0].isdigit()
