"""Resolve edition labels before artifacts are stored."""

from __future__ import annotations

import re
from dataclasses import dataclass

EDITION_RE = re.compile(r"^20\d{2}[a-z]$")


@dataclass(frozen=True)
class ResolvedEdition:
    """A concrete DICOM edition and the user-supplied label it came from."""

    edition: str
    resolved_from: str


class EditionResolutionError(ValueError):
    """Raised when an edition label cannot be resolved safely."""


class EditionResolver:
    """Resolve `current` through an explicit configured concrete edition."""

    def __init__(self, current_edition: str | None = None) -> None:
        self.current_edition = current_edition

    def resolve(self, edition: str) -> ResolvedEdition:
        """Resolve a user edition label into a concrete edition ID."""
        normalized = edition.strip().lower()
        if normalized == "current":
            if self.current_edition is None:
                msg = (
                    "current must be resolved from official release metadata "
                    "or configured explicitly before artifacts are stored"
                )
                raise EditionResolutionError(msg)
            concrete = self.current_edition.strip().lower()
            self._validate_concrete(concrete)
            return ResolvedEdition(edition=concrete, resolved_from="current")

        self._validate_concrete(normalized)
        return ResolvedEdition(edition=normalized, resolved_from=edition)

    @staticmethod
    def _validate_concrete(edition: str) -> None:
        if not EDITION_RE.match(edition):
            raise EditionResolutionError(
                f"edition must be concrete like '2026b', got {edition!r}"
            )
