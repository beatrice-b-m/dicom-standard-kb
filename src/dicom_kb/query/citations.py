"""Helpers for assembling source refs."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from dicom_kb.ir.models import SourceRef
from dicom_kb.query.answer_contracts import StandardRef, standard_ref


def unique_refs(refs: list[StandardRef]) -> list[StandardRef]:
    """Preserve first-seen order while removing duplicate refs."""
    unique: dict[tuple[tuple[str, object], ...], StandardRef] = {}
    for ref in refs:
        key = tuple(ref.model_dump(mode="json").items())
        unique.setdefault(key, ref)
    return list(unique.values())


CitationInput = SourceRef | StandardRef | None


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
