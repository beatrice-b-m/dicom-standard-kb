"""DocBook cross-reference extraction and local resolution."""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

from dicom_kb.docbook.namespaces import NSMAP
from dicom_kb.docbook.text_chunks import normalize_text


@dataclass(frozen=True)
class ParsedXref:
    """A parsed local or external DocBook reference."""

    source_xml_id: str | None
    target_ref: str
    link_type: str
    resolved: bool
    text: str
    warning: str | None = None


def extract_xrefs(root: etree._Element) -> list[ParsedXref]:
    """Extract xref-like elements and record unresolved local targets."""
    xml_ids = {
        value
        for value in root.xpath("//*[@xml:id]/@xml:id", namespaces=NSMAP)
        if isinstance(value, str)
    }
    parsed: list[ParsedXref] = []
    for element in root.xpath(
        ".//db:xref | .//db:link | .//db:olink", namespaces=NSMAP
    ):
        if not isinstance(element, etree._Element):
            continue
        link_type = etree.QName(element).localname
        target = _target_ref(element)
        if target is None:
            continue
        source = _nearest_xml_id(element)
        resolved = link_type == "olink" or target in xml_ids
        warning = None if resolved else f"unresolved {link_type} target: {target}"
        parsed.append(
            ParsedXref(
                source_xml_id=source,
                target_ref=target,
                link_type=link_type,
                resolved=resolved,
                text=normalize_text("".join(element.itertext())),
                warning=warning,
            )
        )
    return parsed


def _target_ref(element: etree._Element) -> str | None:
    target = (
        element.get("linkend")
        or element.get("targetptr")
        or element.get("targetdoc")
        or element.get("xlink:href")
    )
    return str(target) if target is not None else None


def _nearest_xml_id(element: etree._Element) -> str | None:
    current: etree._Element | None = element
    while current is not None:
        value = current.get("{http://www.w3.org/XML/1998/namespace}id")
        if value:
            return str(value)
        current = current.getparent()
    return None
