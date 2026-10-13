"""Capped standard text retrieval and full-text search responses."""

from __future__ import annotations

import sqlite3

from dicom_kb.db.repositories import (
    DocumentRepository,
)
from dicom_kb.query.answer_contracts import (
    ToolResponse,
    standard_text_result,
    standard_text_search_result,
    tool_response,
)
from dicom_kb.query.citations import citation_refs
from dicom_kb.query.search import build_fts_query


def retrieve_standard_text(
    connection: sqlite3.Connection,
    *,
    part: str,
    section_or_anchor: str,
    edition: str,
    max_chars: int = 800,
) -> ToolResponse:
    """Retrieve a capped excerpt from persisted DocBook structure."""
    if not part.startswith("PS3."):
        return tool_response(
            status="validation_error",
            result={"message": "part must be a DICOM part label such as PS3.3."},
        )
    if max_chars < 1 or max_chars > 4000:
        return tool_response(
            status="validation_error",
            result={"message": "max_chars must be between 1 and 4000."},
        )

    repository = DocumentRepository(connection)
    node = repository.find_node(
        part=part,
        section_or_anchor=section_or_anchor,
        edition=edition,
    )
    if node is None:
        return tool_response(
            status="not_found",
            result={"message": "No standard text node matched the input."},
        )

    tables = repository.list_tables_under_node(node, edition=edition)
    plain_text = node.plain_text or ""
    text_excerpt = plain_text[:max_chars]
    warnings = (
        [f"text excerpt truncated to {max_chars} characters"]
        if len(plain_text) > max_chars
        else []
    )
    refs = citation_refs(
        (node.source_ref,),
        (table.source_ref for table in tables),
    )
    return tool_response(
        status="ok",
        result=standard_text_result(
            node,
            tables,
            text_excerpt=text_excerpt,
        ),
        refs=refs,
        warnings=warnings,
    )


def search_standard_text(
    connection: sqlite3.Connection,
    *,
    query: str,
    edition: str,
    part_filter: str | None = None,
    limit: int = 10,
) -> ToolResponse:
    """Search persisted DocBook text with SQLite FTS5."""
    if not query.strip():
        return tool_response(
            status="validation_error",
            result={"message": "query must not be empty."},
        )
    if len(query) > 200:
        return tool_response(
            status="validation_error",
            result={"message": "query must be 200 characters or fewer."},
        )
    if part_filter is not None and not part_filter.startswith("PS3."):
        return tool_response(
            status="validation_error",
            result={"message": "part_filter must be a DICOM part label such as PS3.3."},
        )
    if limit < 1 or limit > 50:
        return tool_response(
            status="validation_error",
            result={"message": "limit must be between 1 and 50."},
        )

    fts_query = build_fts_query(query)
    if fts_query is None:
        return tool_response(
            status="validation_error",
            result={"message": "query must contain at least one searchable term."},
        )

    records = DocumentRepository(connection).search_text(
        fts_query=fts_query,
        edition=edition,
        part_filter=part_filter,
        limit=limit,
    )
    if not records:
        return tool_response(
            status="not_found",
            result={"message": "No standard text matched the query."},
        )

    return tool_response(
        status="ok",
        result=standard_text_search_result(records),
        refs=citation_refs(record.node.source_ref for record in records),
    )
