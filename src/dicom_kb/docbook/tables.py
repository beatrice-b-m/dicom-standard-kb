"""DocBook table parsing into raw table IR."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from lxml import etree

from dicom_kb.docbook.namespaces import NSMAP, xml_id_name
from dicom_kb.docbook.text_chunks import normalize_text

INCLUDE_TABLE_RE = re.compile(
    r"^Include\s+Table\s+(?P<table_ref>[A-Za-z0-9_.-]+)\s*(?P<title>.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedCell:
    """A normalized DocBook table cell."""

    text: str
    row: int
    column: int
    colspan: int = 1
    rowspan: int = 1
    xrefs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedRow:
    """A normalized DocBook table row."""

    cells: tuple[ParsedCell, ...]
    row_index: int
    section: str
    row_kind: str = "data"
    include_table_ref: str | None = None
    include_title: str | None = None


@dataclass(frozen=True)
class ParsedTable:
    """Raw table IR preserving caption, ID, row order, and warnings."""

    xml_id: str | None
    title: str | None
    rows: tuple[ParsedRow, ...]
    warnings: tuple[str, ...] = ()
    parent_xml_id: str | None = None
    ordinal: int = 0


@dataclass
class _Occupancy:
    used: dict[tuple[int, int], bool] = field(default_factory=dict)

    def next_column(self, row: int, start: int = 0) -> int:
        column = start
        while self.used.get((row, column), False):
            column += 1
        return column

    def mark(self, row: int, column: int, rowspan: int, colspan: int) -> None:
        for row_offset in range(rowspan):
            for column_offset in range(colspan):
                self.used[(row + row_offset, column + column_offset)] = True


def parse_tables(root: etree._Element) -> list[ParsedTable]:
    """Parse DocBook tables and informaltables from a document root."""
    tables: list[ParsedTable] = []
    for ordinal, table in enumerate(
        root.xpath(".//db:table | .//db:informaltable", namespaces=NSMAP)
    ):
        if isinstance(table, etree._Element):
            parsed = parse_table(table)
            tables.append(
                replace(
                    parsed,
                    parent_xml_id=_parent_section_xml_id(table),
                    ordinal=ordinal,
                )
            )
    return tables


def parse_table(table: etree._Element) -> ParsedTable:
    """Parse one DocBook table-like element."""
    title = _first_text(table, "db:title")
    warnings: list[str] = []
    rows: list[ParsedRow] = []
    occupancy = _Occupancy()
    row_index = 0

    for section_name in ("thead", "tbody", "tfoot"):
        for row in table.xpath(f".//db:{section_name}/db:row", namespaces=NSMAP):
            if not isinstance(row, etree._Element):
                continue
            parsed_cells = _parse_row(row, row_index, occupancy, warnings)
            rows.append(_classify_row(parsed_cells, row_index, section_name))
            row_index += 1

    if not rows:
        for row in table.xpath(".//db:row", namespaces=NSMAP):
            if not isinstance(row, etree._Element):
                continue
            parsed_cells = _parse_row(row, row_index, occupancy, warnings)
            rows.append(_classify_row(parsed_cells, row_index, "tbody"))
            row_index += 1

    return ParsedTable(
        xml_id=table.get(xml_id_name()),
        title=title,
        rows=tuple(rows),
        warnings=tuple(warnings),
    )


def _parse_row(
    row: etree._Element,
    row_index: int,
    occupancy: _Occupancy,
    warnings: list[str],
) -> tuple[ParsedCell, ...]:
    cells: list[ParsedCell] = []
    column = 0
    for entry in row.xpath("./db:entry", namespaces=NSMAP):
        if not isinstance(entry, etree._Element):
            continue
        column = occupancy.next_column(row_index, column)
        colspan = _colspan(entry)
        rowspan = _rowspan(entry)
        if colspan < 1 or rowspan < 1:
            warnings.append(f"invalid span at row {row_index}, column {column}")
            colspan = max(colspan, 1)
            rowspan = max(rowspan, 1)
        occupancy.mark(row_index, column, rowspan, colspan)
        cells.append(
            ParsedCell(
                text=normalize_text("".join(entry.itertext())),
                row=row_index,
                column=column,
                colspan=colspan,
                rowspan=rowspan,
                xrefs=tuple(_entry_refs(entry)),
            )
        )
        column += colspan
    return tuple(cells)


def _classify_row(
    cells: tuple[ParsedCell, ...], row_index: int, section_name: str
) -> ParsedRow:
    row_text = normalize_text(" ".join(cell.text for cell in cells))
    include_match = INCLUDE_TABLE_RE.match(row_text)
    if include_match:
        include_title = include_match.group("title").strip().strip('"')
        return ParsedRow(
            cells=cells,
            row_index=row_index,
            section=section_name,
            row_kind="include",
            include_table_ref=include_match.group("table_ref"),
            include_title=include_title or None,
        )
    return ParsedRow(cells=cells, row_index=row_index, section=section_name)


def _colspan(entry: etree._Element) -> int:
    namest = entry.get("namest")
    nameend = entry.get("nameend")
    if namest and nameend:
        start = _column_number(namest)
        end = _column_number(nameend)
        if start is not None and end is not None:
            return max(end - start + 1, 1)
    return 1


def _rowspan(entry: etree._Element) -> int:
    morerows = entry.get("morerows")
    if morerows is None:
        return 1
    try:
        return int(morerows) + 1
    except ValueError:
        return 1


def _column_number(name: str) -> int | None:
    match = re.search(r"(\d+)$", name)
    if not match:
        return None
    return int(match.group(1))


def _entry_refs(entry: etree._Element) -> list[str]:
    refs: list[str] = []
    for xref in entry.xpath(".//db:xref | .//db:link | .//db:olink", namespaces=NSMAP):
        if isinstance(xref, etree._Element):
            target = (
                xref.get("linkend") or xref.get("targetptr") or xref.get("targetdoc")
            )
            if target:
                refs.append(target)
    return refs


def _parent_section_xml_id(table: etree._Element) -> str | None:
    current = table.getparent()
    while current is not None:
        if etree.QName(current).localname in {"chapter", "section"}:
            value = current.get(xml_id_name())
            if value:
                return str(value)
        current = current.getparent()
    return None


def _first_text(element: etree._Element, path: str) -> str | None:
    values = element.xpath(f"./{path}", namespaces=NSMAP)
    if not values:
        return None
    first = values[0]
    if not isinstance(first, etree._Element):
        return None
    text = normalize_text("".join(first.itertext()))
    return text or None
