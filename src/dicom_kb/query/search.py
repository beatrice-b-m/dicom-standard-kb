"""Helpers for DocBook text search queries."""

from __future__ import annotations

import re


def build_fts_query(query: str) -> str | None:
    """Convert user text into a conservative SQLite FTS5 AND query."""
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]*", query)
    if not tokens:
        return None
    quoted_tokens = [f'"{token}"' for token in tokens]
    return " AND ".join(quoted_tokens)
