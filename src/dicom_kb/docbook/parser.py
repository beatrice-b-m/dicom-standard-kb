"""DocBook document parser."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from dicom_kb.docbook.markdown import (
    TABLE_PLACEHOLDER_RE,
    MarkdownRenderer,
    plain_text,
)
from dicom_kb.docbook.namespaces import NSMAP, xml_id_name
from dicom_kb.docbook.tables import ParsedTable, parse_tables
from dicom_kb.docbook.targets import TargetIndex, element_label
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.docbook.variablelists import ParsedVariableList, parse_variablelists
from dicom_kb.docbook.xrefs import ParsedXref, extract_xrefs


@dataclass(frozen=True)
class ParsedSection:
    """A DocBook section-like node with stable source identity."""

    xml_id: str | None
    title: str | None
    number: str | None
    depth: int
    plain_text: str
    node_type: str = "section"
    parent_xml_id: str | None = None
    ordinal: int = 0
    markdown: str = ""
    informative: bool = False


@dataclass(frozen=True)
class ParsedDocument:
    """Parsed DocBook document IR."""

    part: str
    sections: tuple[ParsedSection, ...]
    tables: tuple[ParsedTable, ...]
    variablelists: tuple[ParsedVariableList, ...]
    xrefs: tuple[ParsedXref, ...]
    warnings: tuple[str, ...]
    unresolved_references: tuple[str, ...] = ()


def read_docbook_root(path: Path) -> etree._Element:
    """Read a DocBook XML file without resolving entities."""
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    return etree.parse(str(path), parser).getroot()


def parse_docbook_file(
    path: Path, *, part: str, targets: TargetIndex | None = None
) -> ParsedDocument:
    """Parse a DocBook XML file from disk.

    Pass the index of every part being built so references into other parts
    resolve to their labels; without it only this part's targets resolve.
    """
    return parse_docbook_root(read_docbook_root(path), part=part, targets=targets)


def parse_docbook_xml(
    xml: str | bytes, *, part: str, targets: TargetIndex | None = None
) -> ParsedDocument:
    """Parse a DocBook XML string."""
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False)
    root = etree.fromstring(xml, parser=parser)
    return parse_docbook_root(root, part=part, targets=targets)


def parse_docbook_root(
    root: etree._Element, *, part: str, targets: TargetIndex | None = None
) -> ParsedDocument:
    """Parse section, table, and xref structures from a DocBook root."""
    renderer = MarkdownRenderer.for_document(root, part=part, targets=targets)
    xrefs = tuple(extract_xrefs(root))
    warnings = tuple(xref.warning for xref in xrefs if xref.warning is not None)
    tables = tuple(parse_tables(root, renderer))
    return ParsedDocument(
        part=part,
        sections=tuple(_parse_sections(root, renderer, tables)),
        tables=tables,
        variablelists=tuple(parse_variablelists(root, renderer)),
        xrefs=xrefs,
        warnings=warnings,
        # Cells render twice (parsed text and table markdown); log each once.
        unresolved_references=tuple(dict.fromkeys(renderer.log.unresolved)),
    )


def _parse_sections(
    root: etree._Element,
    renderer: MarkdownRenderer,
    tables: tuple[ParsedTable, ...],
) -> list[ParsedSection]:
    table_markdown = {table.xml_id: table.markdown for table in tables}
    sections: list[ParsedSection] = []
    for ordinal, section in enumerate(
        root.xpath(".//db:chapter | .//db:section", namespaces=NSMAP)
    ):
        if not isinstance(section, etree._Element):
            continue
        markdown = renderer.section_body(section)
        title = renderer.title(section)
        sections.append(
            ParsedSection(
                xml_id=section.get(xml_id_name()),
                title=title,
                number=element_label(section),
                depth=_section_depth(section),
                # Parsers read a section's words with its tables in place.
                plain_text=plain_text(
                    TABLE_PLACEHOLDER_RE.sub(
                        lambda match: table_markdown.get(match["xml_id"], ""),
                        markdown,
                    )
                ),
                node_type=etree.QName(section).localname,
                parent_xml_id=_parent_section_xml_id(section),
                ordinal=ordinal,
                markdown=markdown,
                informative=_is_informative(section),
            )
        )
    return sections


def is_informative_title(title: str | None) -> bool:
    """Informative annexes say so in their title; examples are informative."""
    text = (title or "").lower()
    return "(informative)" in text or text.startswith("example")


def _is_informative(section: etree._Element) -> bool:
    """Report whether a section is, or sits inside, informative text."""
    current: etree._Element | None = section
    while current is not None:
        if etree.QName(current).localname in {
            "chapter",
            "section",
        } and is_informative_title(_first_child_text(current, "title")):
            return True
        current = current.getparent()
    return False


def _section_depth(section: etree._Element) -> int:
    depth = 0
    current = section.getparent()
    while current is not None:
        if etree.QName(current).localname in {"chapter", "section"}:
            depth += 1
        current = current.getparent()
    return depth


def _parent_section_xml_id(section: etree._Element) -> str | None:
    current = section.getparent()
    while current is not None:
        if etree.QName(current).localname in {"chapter", "section"}:
            value = current.get(xml_id_name())
            if value:
                return str(value)
        current = current.getparent()
    return None


def _first_child_text(element: etree._Element, local_name: str) -> str | None:
    values = element.xpath(f"./db:{local_name}", namespaces=NSMAP)
    if not values:
        return None
    first = values[0]
    if not isinstance(first, etree._Element):
        return None
    text = normalize_text("".join(first.itertext()))
    return text or None
