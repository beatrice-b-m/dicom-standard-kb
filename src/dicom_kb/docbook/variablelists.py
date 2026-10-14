"""DocBook variablelist parsing into term/definition IR."""

from __future__ import annotations

import re
from dataclasses import dataclass

from lxml import etree

from dicom_kb.docbook.markdown import MarkdownRenderer
from dicom_kb.docbook.namespaces import NSMAP, xml_id_name
from dicom_kb.docbook.text_chunks import normalize_text

_TAG_RE = re.compile(r"^\([0-9A-Fa-fxX]{4},[0-9A-Fa-fxX]{4}\)$")


@dataclass(frozen=True)
class ParsedVariableEntry:
    """One DocBook variable-list entry, rendered as one line of markdown."""

    terms: tuple[str, ...]
    # Paragraphs are kept apart by <br>, and references keep their targets.
    definition: str
    entry_xml_id: str | None = None
    xrefs: tuple[str, ...] = ()
    entry_index: int = 0


@dataclass(frozen=True)
class ParsedVariableList:
    """A DocBook variablelist and where it sits: a section, or a table row."""

    xml_id: str | None
    title: str | None
    entries: tuple[ParsedVariableEntry, ...]
    parent_xml_id: str | None = None
    # The paragraph a list item opens with when the list sits in that item,
    # e.g. "Value 1 shall identify the Pixel Data Characteristics".
    lead: str | None = None
    ordinal: int = 0
    section_title: str | None = None
    # Set when the list is inside a table cell.
    table_xml_id: str | None = None
    # The tag in the list's table row, and how many earlier rows of the
    # table carry the same tag (a module can list an attribute twice).
    row_tag: str | None = None
    row_tag_index: int = 0


def parse_variablelists(
    root: etree._Element, renderer: MarkdownRenderer
) -> list[ParsedVariableList]:
    """Parse every DocBook variablelist of a document, with its context."""
    variablelists: list[ParsedVariableList] = []
    for ordinal, variablelist in enumerate(
        root.xpath(".//db:variablelist", namespaces=NSMAP)
    ):
        if not isinstance(variablelist, etree._Element):
            continue
        section = _ancestor(variablelist, {"chapter", "section"})
        table, row_tag, row_tag_index = _table_row_context(variablelist)
        variablelists.append(
            ParsedVariableList(
                xml_id=variablelist.get(xml_id_name()),
                title=renderer.title(variablelist),
                entries=tuple(_entries(variablelist, renderer)),
                lead=_lead(variablelist, renderer),
                parent_xml_id=section.get(xml_id_name())
                if section is not None
                else None,
                ordinal=ordinal,
                section_title=renderer.title(section) if section is not None else None,
                table_xml_id=table.get(xml_id_name()) if table is not None else None,
                row_tag=row_tag,
                row_tag_index=row_tag_index,
            )
        )
    return variablelists


def _entries(
    variablelist: etree._Element, renderer: MarkdownRenderer
) -> list[ParsedVariableEntry]:
    entries: list[ParsedVariableEntry] = []
    for entry_index, entry in enumerate(
        variablelist.xpath("./db:varlistentry", namespaces=NSMAP)
    ):
        if not isinstance(entry, etree._Element):
            continue
        terms = tuple(
            term
            for term in (
                renderer.inline_text(term).rstrip(":").strip()
                for term in entry.xpath("./db:term", namespaces=NSMAP)
                if isinstance(term, etree._Element)
            )
            if term
        )
        listitem = _first_child(entry, "listitem")
        entries.append(
            ParsedVariableEntry(
                terms=terms,
                definition=(
                    renderer.inline_text(listitem) if listitem is not None else ""
                ),
                entry_xml_id=entry.get(xml_id_name()),
                xrefs=tuple(_entry_refs(entry)),
                entry_index=entry_index,
            )
        )
    return entries


def _lead(variablelist: etree._Element, renderer: MarkdownRenderer) -> str | None:
    parent = variablelist.getparent()
    if parent is None or etree.QName(parent).localname != "listitem":
        return None
    for sibling in parent:
        if sibling is variablelist:
            break
        if isinstance(sibling.tag, str) and etree.QName(sibling).localname == "para":
            return renderer.inline_text(sibling) or None
    return None


def _table_row_context(
    element: etree._Element,
) -> tuple[etree._Element | None, str | None, int]:
    """Return the table a list's cell is in, its row's tag and that tag's count."""
    row = _ancestor(element, {"tr", "row"}, stop={"section", "chapter"})
    if row is None:
        return None, None, 0
    table = _ancestor(row, {"table", "informaltable"})
    tag = _row_tag(row)
    if table is None or tag is None:
        return table, tag, 0
    earlier = 0
    for other in table.iter(row.tag):
        if other is row:
            break
        if _row_tag(other) == tag:
            earlier += 1
    return table, tag, earlier


def _row_tag(row: etree._Element) -> str | None:
    for cell in row:
        if not isinstance(cell.tag, str):
            continue
        text = normalize_text("".join(cell.itertext()))
        if _TAG_RE.match(text):
            return text
    return None


def _entry_refs(entry: etree._Element) -> list[str]:
    refs: list[str] = []
    for xref in entry.xpath(".//db:xref | .//db:link | .//db:olink", namespaces=NSMAP):
        if not isinstance(xref, etree._Element):
            continue
        target = xref.get("linkend") or xref.get("targetptr") or xref.get("targetdoc")
        if target:
            refs.append(str(target))
    return refs


def _ancestor(
    element: etree._Element, names: set[str], *, stop: set[str] | None = None
) -> etree._Element | None:
    current = element.getparent()
    while current is not None:
        name = etree.QName(current).localname
        if name in names:
            return current
        if stop and name in stop:
            return None
        current = current.getparent()
    return None


def _first_child(element: etree._Element, local_name: str) -> etree._Element | None:
    values = element.xpath(f"./db:{local_name}", namespaces=NSMAP)
    if not values:
        return None
    first = values[0]
    return first if isinstance(first, etree._Element) else None
