"""Helpers for public citation and trace assembly."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from dicom_kb.ir.models import SourceRef
from dicom_kb.query.answer_contracts import ResponseTrace, StandardRef, standard_ref
from dicom_kb.sources.official_urls import official_standard_ref_url


def build_trace(
    connection: sqlite3.Connection,
    *,
    edition: str,
    query_id: str | None,
    resolved_at: datetime | None,
) -> ResponseTrace:
    """Build the standard response trace for a resolved edition."""
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


def unique_refs(refs: list[StandardRef]) -> list[StandardRef]:
    """Preserve first-seen order while removing duplicate refs."""
    unique: dict[tuple[tuple[str, object], ...], StandardRef] = {}
    for ref in refs:
        key = tuple(ref.model_dump(mode="json").items())
        unique.setdefault(key, ref)
    return list(unique.values())


CitationInput = SourceRef | StandardRef | None


def official_source_url(source_ref: SourceRef) -> str | None:
    """Derive the official CHTML URL for a source ref when possible."""
    return official_standard_ref_url(
        edition=source_ref.edition_id,
        part=source_ref.part,
        anchor=source_ref.xml_id or source_ref.table_id,
    )


@dataclass(frozen=True)
class CitationGroup:
    """A named group of evidence refs for one fact family in a response."""

    label: str
    refs: tuple[StandardRef, ...]


@dataclass
class CitationBuilder:
    """Assemble citation refs from grouped structured evidence."""

    _groups: list[CitationGroup] = field(default_factory=list)

    def add(self, *refs: CitationInput) -> CitationBuilder:
        """Add unlabelled refs to the citation set."""
        return self.add_group("source", refs)

    def add_group(
        self,
        label: str,
        refs: Iterable[CitationInput],
    ) -> CitationBuilder:
        """Add a labelled evidence group, ignoring null refs."""
        group_refs = tuple(
            ref for ref in (_standard_ref(item) for item in refs) if ref is not None
        )
        if group_refs:
            self._groups.append(CitationGroup(label=label, refs=group_refs))
        return self

    def refs(self) -> list[StandardRef]:
        """Return flattened, deduplicated refs for the public envelope."""
        return unique_refs([ref for group in self._groups for ref in group.refs])

    def groups(self) -> tuple[CitationGroup, ...]:
        """Return grouped evidence for future richer citation surfaces."""
        return tuple(self._groups)


def citation_refs(*groups: Iterable[CitationInput]) -> list[StandardRef]:
    """Build public refs from one or more evidence groups."""
    builder = CitationBuilder()
    for group in groups:
        builder.add_group("source", group)
    return builder.refs()


def _standard_ref(ref: CitationInput) -> StandardRef | None:
    if ref is None:
        return None
    if isinstance(ref, StandardRef):
        return ref
    return standard_ref(ref)
