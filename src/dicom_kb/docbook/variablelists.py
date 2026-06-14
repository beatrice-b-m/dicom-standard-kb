"""DocBook variablelist parsing into term/definition IR."""

from __future__ import annotations

from dataclasses import dataclass, replace

from lxml import etree

from dicom_kb.docbook.namespaces import NSMAP, xml_id_name
from dicom_kb.docbook.text_chunks import normalize_text


@dataclass(frozen=True)
class ParsedVariableEntry:
    """One DocBook variable-list entry with normalized term text."""

    terms: tuple[str, ...]
    definition: str
    entry_xml_id: str | None = None
    term_xml_ids: tuple[str | None, ...] = ()
    definition_xml_id: str | None = None
    xrefs: tuple[str, ...] = ()
    entry_index: int = 0


@dataclass(frozen=True)
class ParsedVariableList:
    """A normalized DocBook variablelist with stable source context."""

    xml_id: str | None
    title: str | None
    entries: tuple[ParsedVariableEntry, ...]
    parent_xml_id: str | None = None
    ordinal: int = 0


def parse_variablelists(root: etree._Element) -> list[ParsedVariableList]:
    """Parse DocBook variablelists from a document root."""
    variablelists: list[ParsedVariableList] = []
    for ordinal, variablelist in enumerate(
        root.xpath(".//db:variablelist", namespaces=NSMAP)
    ):
        if not isinstance(variablelist, etree._Element):
            continue
        parsed = parse_variablelist(variablelist)
        variablelists.append(
            replace(
                parsed,
                parent_xml_id=_parent_section_xml_id(variablelist),
                ordinal=ordinal,
            )
        )
    return variablelists


def parse_variablelist(variablelist: etree._Element) -> ParsedVariableList:
    """Parse one DocBook variablelist element."""
    entries: list[ParsedVariableEntry] = []
    for entry_index, entry in enumerate(
        variablelist.xpath("./db:varlistentry", namespaces=NSMAP)
    ):
        if not isinstance(entry, etree._Element):
            continue
        terms = tuple(
            term
            for term in (
                normalize_text("".join(term.itertext()))
                for term in entry.xpath("./db:term", namespaces=NSMAP)
                if isinstance(term, etree._Element)
            )
            if term
        )
        listitem = _first_child(entry, "listitem")
        definition = (
            normalize_text("".join(listitem.itertext()))
            if listitem is not None
            else ""
        )
        entries.append(
            ParsedVariableEntry(
                terms=terms,
                definition=definition,
                entry_xml_id=entry.get(xml_id_name()),
                term_xml_ids=tuple(
                    term.get(xml_id_name())
                    for term in entry.xpath("./db:term", namespaces=NSMAP)
                    if isinstance(term, etree._Element)
                ),
                definition_xml_id=(
                    listitem.get(xml_id_name()) if listitem is not None else None
                ),
                xrefs=tuple(_entry_refs(entry)),
                entry_index=entry_index,
            )
        )
    return ParsedVariableList(
        xml_id=variablelist.get(xml_id_name()),
        title=_first_child_text(variablelist, "title"),
        entries=tuple(entries),
    )


def _entry_refs(entry: etree._Element) -> list[str]:
    refs: list[str] = []
    for xref in entry.xpath(".//db:xref | .//db:link | .//db:olink", namespaces=NSMAP):
        if not isinstance(xref, etree._Element):
            continue
        target = xref.get("linkend") or xref.get("targetptr") or xref.get("targetdoc")
        if target:
            refs.append(str(target))
    return refs


def _parent_section_xml_id(element: etree._Element) -> str | None:
    current = element.getparent()
    while current is not None:
        if etree.QName(current).localname in {"chapter", "section"}:
            value = current.get(xml_id_name())
            if value:
                return str(value)
        current = current.getparent()
    return None


def _first_child(element: etree._Element, local_name: str) -> etree._Element | None:
    values = element.xpath(f"./db:{local_name}", namespaces=NSMAP)
    if not values:
        return None
    first = values[0]
    return first if isinstance(first, etree._Element) else None


def _first_child_text(element: etree._Element, local_name: str) -> str | None:
    first = _first_child(element, local_name)
    if first is None:
        return None
    text = normalize_text("".join(first.itertext()))
    return text or None
