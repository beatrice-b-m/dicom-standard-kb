"""Helpers for public citation and trace assembly."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from dicom_kb.query.answer_contracts import ResponseTrace, StandardRef


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
