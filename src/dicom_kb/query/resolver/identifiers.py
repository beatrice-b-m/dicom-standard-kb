"""Read a UID or a VR the way dicom_read reads a section.

A UID answers with its PS3.6 registry row and, for a transfer syntax, how it
encodes the Data Set according to PS3.5 Annex A. A VR answers with its row of
PS3.5 Table 6.2-1 and the shape of its Explicit VR header.
"""

from __future__ import annotations

import re
import sqlite3

from dicom_kb.db.repositories import (
    DocumentRepository,
    TransferSyntaxRepository,
    UIDRepository,
)
from dicom_kb.ir.models import DocNode, UIDRegistryEntry
from dicom_kb.query.answer_contracts import StandardRef, ToolResponse, tool_response
from dicom_kb.query.resolver._refs import _reference, node_ref

_UID_RE = re.compile(r"^\d+(?:\.\d+)+$")
_VR_RE = re.compile(r"^(?:VR\s+([A-Za-z]{2})|([A-Z]{2}))$")
_VR_TABLE_TITLE = "DICOM Value Representations"
_SHORT_HEADER_TITLE = "Data Element with Explicit VR of "
_LONG_HEADER_TITLE = "Data Element with Explicit VR other than"
_CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")


def read_identifier(
    connection: sqlite3.Connection, *, reference: str, edition: str
) -> ToolResponse | None:
    """Answer a VR code or a registered UID; None when it is neither."""
    text = " ".join(reference.split())
    vr = _VR_RE.match(text)
    if vr:
        answer = _read_vr(connection, (vr.group(1) or vr.group(2)).upper(), edition)
        if answer is not None or vr.group(1):
            return answer or tool_response(
                status="not_found",
                result={"message": f"{text} is not in PS3.5 Table 6.2-1."},
            )
    if _UID_RE.match(text):
        # A dotted number that is not a registered UID is a section label.
        return read_uid(connection, reference=text, edition=edition)
    return None


def read_uid(
    connection: sqlite3.Connection, *, reference: str, edition: str
) -> ToolResponse | None:
    """Answer a UID, UID keyword or exact UID name from the PS3.6 registry."""
    entry = UIDRepository(connection).find_by_uid_or_keyword(
        reference.strip(), edition=edition
    )
    if entry is None:
        return None
    lines = [_uid_heading(entry)]
    refs = [_registry_ref(entry, edition)]
    if entry.uid_type == "Transfer Syntax":
        encoding, encoding_refs = _transfer_syntax(connection, entry, edition)
        lines += ["", *encoding]
        refs += encoding_refs
    elif entry.uid_type in {"SOP Class", "Meta SOP Class"}:
        lines += ["", f'Its IOD and modules: dicom_iod("{entry.uid_value}").']
    return tool_response(status="ok", result={"markdown": "\n".join(lines)}, refs=refs)


def _uid_heading(entry: UIDRegistryEntry) -> str:
    facts = [entry.uid_type]
    if entry.uid_keyword:
        facts.insert(0, f"`{entry.uid_keyword}`")
    if entry.part:
        facts.append(entry.part)
    named = "retired" in entry.uid_name.lower()
    retired = " (retired)" if entry.retired and not named else ""
    return f"**{entry.uid_value}** {entry.uid_name}{retired}\n{' · '.join(facts)}"


def _transfer_syntax(
    connection: sqlite3.Connection, entry: UIDRegistryEntry, edition: str
) -> tuple[list[str], list[StandardRef]]:
    detail = TransferSyntaxRepository(connection).find(entry.uid_value, edition=edition)
    if detail is None:
        if entry.retired:
            return [f"Retired: PS3.5 ({edition}) no longer specifies its encoding."], []
        return [
            "Warning: no PS3.5 Annex A section of this edition defines its "
            "encoding; see the build's gap log."
        ], []
    documents = DocumentRepository(connection)
    section = _ps35_node(documents, detail.section_xml_id, edition)
    lines = [
        "| VR | Byte order | Pixel Data | Deflate |",
        "|---|---|---|---|",
        f"| {detail.vr_encoding} | {detail.byte_order} | {detail.pixel_data} "
        f"| {detail.deflate or 'No'} |",
    ]
    refs: list[StandardRef] = []
    if section is not None:
        lines += ["", f"Rules: {_reference(section)} {section.title or ''}".rstrip()]
        refs.append(node_ref(section, edition))
    others = [
        node
        for node in (
            _ps35_node(documents, xml_id, edition) for xml_id in detail.see_also
        )
        if node is not None
    ]
    if others:
        lines.append("Also named in: " + ", ".join(_reference(n) for n in others))
    return lines, refs


def _read_vr(
    connection: sqlite3.Connection, vr: str, edition: str
) -> ToolResponse | None:
    documents = DocumentRepository(connection)
    tables = documents.nodes_by_title(
        title=_VR_TABLE_TITLE, node_types=("table",), edition=edition, part="PS3.5"
    )
    if not tables or not tables[0].markdown:
        return None
    table = tables[0]
    header, row = _table_row(table.markdown or "", vr)
    if row is None:
        return None
    name = row[0].split("<br>", 1)[1] if "<br>" in row[0] else ""
    lines = [f"**{vr}** {name}".rstrip(), ""]
    # One field per line, so the cell's own line breaks become spaces.
    lines += [
        f"**{label}:** {value.replace('<br>', ' ')}"
        for label, value in zip(header[1:], row[1:], strict=False)
        if value
    ]
    refs = [node_ref(table, edition)]
    explicit = _explicit_header(documents, vr, edition)
    if explicit is not None:
        sentence, node = explicit
        lines.append(f"**Explicit VR header:** {sentence} ({_reference(node)})")
        refs.append(node_ref(node, edition))
    return tool_response(status="ok", result={"markdown": "\n".join(lines)}, refs=refs)


def _table_row(markdown: str, vr: str) -> tuple[list[str], list[str] | None]:
    header: list[str] = []
    for line in markdown.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in _CELL_SPLIT_RE.split(line)[1:-1]]
        if not header:
            header = cells
        elif cells and re.match(rf"^{vr}(?:<br>|$)", cells[0]):
            return header, cells
    return header, None


def _explicit_header(
    documents: DocumentRepository, vr: str, edition: str
) -> tuple[str, DocNode] | None:
    """Which Explicit VR layout PS3.5 7.1.2 gives this VR, from table titles."""
    short = documents.nodes_by_title_prefix(
        prefix=_SHORT_HEADER_TITLE, node_types=("table",), edition=edition, part="PS3.5"
    )
    long = documents.nodes_by_title_prefix(
        prefix=_LONG_HEADER_TITLE, node_types=("table",), edition=edition, part="PS3.5"
    )
    if not short or not long:
        return None
    title = (short[0].title or "")[len(_SHORT_HEADER_TITLE) :]
    listed = re.findall(r"\b[A-Z]{2}\b", title)
    if vr in listed:
        return "VR, then a 16-bit Value Length", short[0]
    return "VR, 2 reserved bytes (0000H), then a 32-bit Value Length", long[0]


def _ps35_node(
    documents: DocumentRepository, xml_id: str, edition: str
) -> DocNode | None:
    nodes = documents.nodes_by_xml_id(xml_id=xml_id, edition=edition, part="PS3.5")
    return nodes[0] if nodes else None


def _registry_ref(entry: UIDRegistryEntry, edition: str) -> StandardRef:
    source = entry.source_ref
    table = (source.table_id or "").removeprefix("table_")
    return StandardRef(
        part=source.part,
        table=source.table_id,
        anchor=source.xml_id,
        edition=edition,
        label=f"{source.part} Table {table}" if table else source.part,
    )
