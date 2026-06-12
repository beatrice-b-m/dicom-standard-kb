"""DocBook target database loading.

v1 preserves unresolved olink targets as warnings unless a target database is
provided. This module keeps the adapter boundary explicit for later full
target database support.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetEntry:
    """A DocBook target database entry."""

    target_id: str
    href: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class TargetDatabase:
    """Minimal lookup wrapper for cross-document targets."""

    entries: dict[str, TargetEntry]

    def resolve(self, target_id: str) -> TargetEntry | None:
        """Return a target entry if it exists."""
        return self.entries.get(target_id)
