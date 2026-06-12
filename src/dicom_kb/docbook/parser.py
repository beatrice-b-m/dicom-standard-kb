"""DocBook document parser."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from dicom_kb.docbook.namespaces import NSMAP, xml_id_name
from dicom_kb.docbook.tables import ParsedTable, parse_tables
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.docbook.xrefs import ParsedXref, extract_xrefs


@dataclass(frozen=True)
class ParsedSection:
    """A DocBook section-like node with stable source identity."""

    xml_id: str | None
    title: str | None
    number: str | None
    depth: int
    plain_text: str


@dataclass(frozen=True)
class ParsedDocument:
    """Parsed DocBook document IR."""

    part: str
    sections: tuple[ParsedSection, ...]
    tables: tuple[ParsedTable, ...]
    xrefs: tuple[ParsedXref, ...]
    warnings: tuple[str, ...]


def parse_docbook_file(path: Path, *, part: str) -> ParsedDocument:
    """Parse a DocBook XML file from disk."""
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    root = etree.parse(str(path), parser).getroot()
    return parse_docbook_root(root, part=part)


def parse_docbook_xml(xml: str | bytes, *, part: str) -> ParsedDocument:
    """Parse a DocBook XML string."""
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    root = etree.fromstring(xml, parser=parser)
    return parse_docbook_root(root, part=part)


def parse_docbook_root(root: etree._Element, *, part: str) -> ParsedDocument:
    """Parse section, table, and xref structures from a DocBook root."""
    xrefs = tuple(extract_xrefs(root))
    warnings = tuple(xref.warning for xref in xrefs if xref.warning is not None)
    return ParsedDocument(
        part=part,
        sections=tuple(_parse_sections(root)),
        tables=tuple(parse_tables(root)),
        xrefs=xrefs,
        warnings=warnings,
    )


def _parse_sections(root: etree._Element) -> list[ParsedSection]:
    sections: list[ParsedSection] = []
    for section in root.xpath(".//db:chapter | .//db:section", namespaces=NSMAP):
        if not isinstance(section, etree._Element):
            continue
        sections.append(
            ParsedSection(
                xml_id=section.get(xml_id_name()),
                title=_first_child_text(section, "title"),
                number=_first_child_text(section, "label"),
                depth=_section_depth(section),
                plain_text=normalize_text(_section_body_text(section)),
            )
        )
    return sections


def _section_depth(section: etree._Element) -> int:
    depth = 0
    current = section.getparent()
    while current is not None:
        if etree.QName(current).localname in {"chapter", "section"}:
            depth += 1
        current = current.getparent()
    return depth


def _first_child_text(element: etree._Element, local_name: str) -> str | None:
    values = element.xpath(f"./db:{local_name}", namespaces=NSMAP)
    if not values:
        return None
    first = values[0]
    if not isinstance(first, etree._Element):
        return None
    text = normalize_text("".join(first.itertext()))
    return text or None


def _section_body_text(section: etree._Element) -> str:
    parts: list[str] = []
    for child in section:
        if etree.QName(child).localname in {"title", "label", "section"}:
            continue
        parts.append("".join(child.itertext()))
    return " ".join(parts)
