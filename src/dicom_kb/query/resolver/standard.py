"""Read any section or table of the standard, and search all of it."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from dicom_kb.db.repositories import DocumentRepository
from dicom_kb.docbook.markdown import TABLE_PLACEHOLDER_RE
from dicom_kb.ir.models import DocNode
from dicom_kb.query.answer_contracts import ToolResponse, tool_response
from dicom_kb.query.resolver._refs import (
    _has_canonical_id,
    _reference,
    _target,
    node_ref,
)
from dicom_kb.query.resolver.identifiers import read_identifier, read_uid
from dicom_kb.query.search import build_fts_query

# About 4k tokens at the usual four characters per token.
PAGE_CHARS = 16_000
_SECTION_TYPES = ("chapter", "section")
_PART_RE = re.compile(r"^\s*(?:PS\s*3\s*\.\s*(\d+)|part\s*(\d+))\b[\s,:]*", re.I)
_KIND_RE = re.compile(
    r"^(section|sect\.?|§|annex|appendix|chapter|table|figure)(?:\s+|(?=\d))(.+)$",
    re.I,
)
_NAMED_RE = re.compile(r"^(CID|TID)\s*[-_ ]?\s*(\w+)$", re.I)
_XML_ID_RE = re.compile(r"^(?:sect|table|chapter)_\S+$")
_TABLE_ROW_RE = re.compile(r"^\|")


@dataclass(frozen=True)
class _Reference:
    """What a caller asked to read, parsed from text like `PS3.5 7.5.2`."""

    part: str | None
    label: str | None
    xml_id: str | None
    node_types: tuple[str, ...]
    text: str
    explicit_kind: bool = False


def read_standard(
    connection: sqlite3.Connection,
    *,
    reference: str,
    edition: str,
    page: int = 1,
) -> ToolResponse:
    """Return one section or table as markdown, in pages of about 4k tokens.

    A UID, UID keyword or VR code reads as its registry or VR table row.
    """
    identified = read_identifier(connection, reference=reference, edition=edition)
    if identified is not None:
        return identified
    parsed = _parse_reference(reference)
    if parsed is None:
        return tool_response(
            status="validation_error",
            result={
                "message": "Give a section or table, e.g. `PS3.5 7.5.2`, "
                "`Table C.7-5a`, `Annex A` or `CID 7010`."
            },
        )
    if page < 1:
        return tool_response(
            status="validation_error", result={"message": "page starts at 1."}
        )
    repository = DocumentRepository(connection)
    nodes = _find_nodes(repository, parsed, edition=edition)
    if not nodes:
        named = read_uid(connection, reference=reference, edition=edition)
        return named or _not_found(repository, parsed, edition=edition)
    if len(nodes) > 1:
        return tool_response(
            status="not_found",
            result={
                "message": f"{parsed.text} is in several parts; name one, "
                f"e.g. `{_reference(nodes[0])}`.",
                "candidates": [_candidate(node) for node in nodes],
            },
        )

    node = nodes[0]
    text = _render_node(repository, node, edition=edition)
    pages = paginate(text)
    if page > len(pages):
        return tool_response(
            status="validation_error",
            result={
                "message": f"{_reference(node)} has {len(pages)} page"
                f"{'s' if len(pages) != 1 else ''}."
            },
        )
    body = pages[page - 1]
    if len(pages) > 1:
        footer = f"Page {page} of {len(pages)}."
        if page < len(pages):
            footer += f' Next: dicom_read("{_reference(node)}", page={page + 1}).'
        body = f"{body}\n\n{footer}"
    return tool_response(
        status="ok",
        result={"markdown": body},
        refs=[node_ref(node, edition)],
    )


def search_standard(
    connection: sqlite3.Connection,
    *,
    query: str,
    edition: str,
    part: str | None = None,
    limit: int = 10,
) -> ToolResponse:
    """Rank sections and tables for a query, normative text first."""
    if not query.strip() or len(query) > 200:
        return tool_response(
            status="validation_error",
            result={"message": "query must be 1 to 200 characters."},
        )
    part_filter = _part_label(part) if part else None
    if part and part_filter is None:
        return tool_response(
            status="validation_error",
            result={"message": "part must look like PS3.5."},
        )
    limit = min(max(limit, 1), 30)
    fts_query = build_fts_query(query)
    if fts_query is None:
        return tool_response(
            status="validation_error",
            result={"message": "query must contain at least one word."},
        )
    repository = DocumentRepository(connection)
    records = repository.search_text(
        fts_query=fts_query, edition=edition, part_filter=part_filter, limit=limit
    )
    note = None
    if not records:
        # No node has every word; ranking nodes with any of them still
        # points the next call somewhere useful.
        records = repository.search_text(
            fts_query=fts_query.replace(" AND ", " OR "),
            edition=edition,
            part_filter=part_filter,
            limit=limit,
        )
        note = "No section or table contains every word; closest matches:"
    if not records:
        return tool_response(
            status="not_found",
            result={"message": f"Nothing in the standard matches {query!r}."},
        )
    hits = [
        {
            "Ref": _reference(record.node)
            + (" (informative)" if record.node.informative else ""),
            "Title": record.node.title or "",
            "Context": _one_line(record.snippet),
        }
        for record in records
    ]
    return tool_response(
        status="ok",
        result={"hits": hits, **({"note": note} if note else {})},
        refs=[node_ref(record.node, edition) for record in records],
    )


def paginate(text: str, *, page_chars: int = PAGE_CHARS) -> list[str]:
    """Split markdown into pages at block boundaries.

    A table longer than a page is split between rows, and each later page
    repeats its caption and header so every page reads on its own.
    """
    pages: list[str] = []
    current: list[str] = []
    size = 0

    def flush() -> None:
        nonlocal size
        if current:
            pages.append("\n\n".join(current))
        current.clear()
        size = 0

    for block in _split_oversized(text.split("\n\n"), page_chars):
        if size and size + len(block) + 2 > page_chars:
            flush()
        current.append(block)
        size += len(block) + 2
    flush()
    return pages or [""]


def _split_oversized(blocks: list[str], page_chars: int) -> list[str]:
    pieces: list[str] = []
    for block in blocks:
        if len(block) <= page_chars:
            pieces.append(block)
            continue
        lines = block.split("\n")
        header: list[str] = []
        body = lines
        table_start = next(
            (i for i, line in enumerate(lines) if _TABLE_ROW_RE.match(line)), None
        )
        if table_start is not None and table_start + 1 < len(lines):
            header = lines[: table_start + 2]
            body = lines[table_start + 2 :]
        chunk: list[str] = list(header)
        chunk_size = sum(len(line) + 1 for line in chunk)
        for line in body:
            if chunk_size + len(line) + 1 > page_chars and len(chunk) > len(header):
                pieces.append("\n".join(chunk))
                chunk = list(header)
                chunk_size = sum(len(item) + 1 for item in chunk)
            while len(line) > page_chars:
                pieces.append(line[:page_chars])
                line = line[page_chars:]
            chunk.append(line)
            chunk_size += len(line) + 1
        if len(chunk) > len(header) or not pieces:
            pieces.append("\n".join(chunk))
    return pieces


def _render_node(repository: DocumentRepository, node: DocNode, *, edition: str) -> str:
    if node.node_type == "table":
        return node.markdown or ""
    heading = _heading(node, level=2)
    own = _expanded_body(repository, node, edition=edition)
    if len(own) + repository.subtree_chars(node) <= PAGE_CHARS:
        whole = [heading, own] if own else [heading]
        depth_by_id = {node.id: 0}
        for section in repository.descendant_sections(node, edition=edition):
            depth = depth_by_id.get(section.parent_id or "", 0) + 1
            depth_by_id[section.id] = depth
            whole.append(_heading(section, level=min(2 + depth, 6)))
            body = _expanded_body(repository, section, edition=edition)
            if body:
                whole.append(body)
        return "\n\n".join(whole)
    # Too long to read whole: give this node's own text and a table of
    # contents, so the caller reads only the subsection it needs.
    children = repository.child_sections(node)
    parts = [heading]
    if own:
        parts.append(own)
    if children:
        contents = "\n".join(
            f"- {_reference(section)} {section.title or ''}".rstrip()
            for section in children
        )
        parts.append(f"Subsections (read each with dicom_read):\n{contents}")
    return "\n\n".join(parts)


def _expanded_body(
    repository: DocumentRepository, node: DocNode, *, edition: str
) -> str:
    markdown = node.markdown or ""
    xml_ids = TABLE_PLACEHOLDER_RE.findall(markdown)
    if not xml_ids:
        return markdown
    tables = repository.table_markdown(part=node.part, xml_ids=xml_ids, edition=edition)
    return TABLE_PLACEHOLDER_RE.sub(
        lambda match: tables.get(match["xml_id"], ""), markdown
    ).strip()


def _heading(node: DocNode, *, level: int) -> str:
    name = _target(node).name
    title = node.title or ""
    if name == title or not node.number:
        return f"{'#' * level} {title}".rstrip()
    return f"{'#' * level} {name} {title}".rstrip()


def _find_nodes(
    repository: DocumentRepository, parsed: _Reference, *, edition: str
) -> list[DocNode]:
    if parsed.node_types == ("book",) and parsed.part:
        root = repository.node_by_id(f"{edition}.{parsed.part}.book")
        return [root] if root is not None else []
    if parsed.xml_id:
        return repository.nodes_by_xml_id(
            xml_id=parsed.xml_id, edition=edition, part=parsed.part
        )
    assert parsed.label is not None
    nodes = repository.nodes_by_label(
        label=parsed.label,
        node_types=parsed.node_types,
        edition=edition,
        part=parsed.part,
    )
    if len({node.part for node in nodes}) == 1 and len(nodes) > 1:
        # A few labels repeat inside one part (TID parameter tables, label
        # typos in the source); the node whose id spells the label wins.
        canonical = [node for node in nodes if _has_canonical_id(node)]
        if len(canonical) == 1:
            return canonical
    if not nodes and not parsed.explicit_kind:
        nodes = repository.nodes_by_title(
            title=parsed.label,
            node_types=(*_SECTION_TYPES, "table"),
            edition=edition,
            part=parsed.part,
        )
    return nodes


def _not_found(
    repository: DocumentRepository, parsed: _Reference, *, edition: str
) -> ToolResponse:
    candidates: list[DocNode] = []
    label = parsed.label or ""
    # Walk up the numbering (C.7.3.1.9 -> C.7.3.1) to the nearest real node.
    while label and not candidates:
        parent = re.sub(r"[.\-][^.\-]*$", "", label)
        label = parent if parent != label else ""
        if label:
            candidates = repository.nodes_by_label(
                label=label,
                node_types=_SECTION_TYPES,
                edition=edition,
                part=parsed.part,
            )
    if parsed.label:
        candidates += repository.labels_with_prefix(
            prefix=parsed.label, edition=edition, part=parsed.part
        )
    # Search for the label itself (a figure is found in the section that
    # shows it); the kind word alone would match everything.
    fts_query = build_fts_query(
        parsed.text if "figure" in parsed.node_types else parsed.label or parsed.text
    )
    if fts_query and len(candidates) < 5:
        candidates += [
            record.node
            for record in repository.search_text(
                fts_query=fts_query,
                edition=edition,
                part_filter=parsed.part,
                limit=5,
            )
        ]
    unique = list({node.id: node for node in candidates}.values())[:8]
    where = f" in {parsed.part}" if parsed.part else ""
    result: dict[str, object] = {"message": f"No {parsed.text}{where}."}
    if unique:
        result["candidates"] = [_candidate(node) for node in unique]
    return tool_response(status="not_found", result=result)


def _parse_reference(text: str) -> _Reference | None:
    cleaned = " ".join(text.replace(" ", " ").split()).strip(" .")
    if not cleaned:
        return None
    part = None
    match = _PART_RE.match(cleaned)
    if match:
        part = f"PS3.{int(match.group(1) or match.group(2))}"
        cleaned = cleaned[match.end() :].strip()
    if not cleaned:
        return _Reference(
            part=part,
            label=None,
            xml_id=part,
            node_types=("book",),
            text=part or text,
        )
    named = _NAMED_RE.match(cleaned)
    if named:
        label = f"{named.group(1).upper()} {named.group(2)}"
        return _Reference(
            part=part or "PS3.16",
            label=label,
            xml_id=None,
            node_types=_SECTION_TYPES,
            text=label,
        )
    if _XML_ID_RE.match(cleaned):
        return _Reference(
            part=part, label=None, xml_id=cleaned, node_types=(), text=cleaned
        )
    kind = None
    kind_match = _KIND_RE.match(cleaned)
    if kind_match:
        kind = kind_match.group(1).lower().rstrip(".")
        cleaned = kind_match.group(2).strip()
    label = cleaned
    named = _NAMED_RE.match(label)
    if named:
        # "Table TID 300": the template's own table lives in PS3.16; PS3.21
        # reuses the label for its mapping tables.
        label = f"{named.group(1).upper()} {named.group(2)}"
        part = part or "PS3.16"
    if kind == "table":
        node_types: tuple[str, ...] = ("table",)
        display = f"Table {label}"
    elif kind == "figure":
        # Figures are not stored on their own; the not-found answer points
        # to the sections that show them.
        node_types = ("figure",)
        display = f"Figure {label}"
    elif kind in {"annex", "appendix", "chapter"}:
        node_types = _SECTION_TYPES
        display = f"Annex {label}"
    elif kind is None and "-" in label:
        node_types = ("table",)
        display = f"Table {label}"
    else:
        node_types = _SECTION_TYPES
        display = f"Section {label}"
    return _Reference(
        part=part,
        label=label,
        xml_id=None,
        node_types=node_types,
        text=display,
        explicit_kind=kind is not None,
    )


def _part_label(value: str) -> str | None:
    match = _PART_RE.match(value.strip())
    if match is None or value.strip()[match.end() :].strip():
        return None
    return f"PS3.{int(match.group(1) or match.group(2))}"


def _candidate(node: DocNode) -> dict[str, str]:
    return {"Ref": _reference(node), "Title": node.title or ""}


def _one_line(text: str) -> str:
    return " ".join(text.replace("|", " ").replace("<br>", " ").split())
