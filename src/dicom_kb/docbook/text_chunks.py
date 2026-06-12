"""Text normalization and chunk extraction helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable

ZERO_WIDTH_CHARS = "\u200b\u200c\u200d\ufeff"
ZERO_WIDTH_TRANSLATION = str.maketrans("", "", ZERO_WIDTH_CHARS)
WHITESPACE_RE = re.compile(r"\s+")


def strip_zero_width(text: str) -> str:
    """Remove zero-width formatting characters from literal tokens."""
    return text.translate(ZERO_WIDTH_TRANSLATION)


def normalize_text(text: str) -> str:
    """Normalize DocBook-rendered text to a compact single-line string."""
    return WHITESPACE_RE.sub(" ", strip_zero_width(text)).strip()


def normalize_parts(parts: Iterable[str]) -> str:
    """Normalize a sequence of text fragments."""
    return normalize_text(" ".join(part for part in parts if part))
