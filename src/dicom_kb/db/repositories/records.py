"""Joined query records shared by repository domains."""

from __future__ import annotations

from dataclasses import dataclass

from dicom_kb.ir.models import DocNode


@dataclass(frozen=True)
class DocumentSearchResult:
    """A matched DocBook node with a short full-text search snippet."""

    node: DocNode
    snippet: str
