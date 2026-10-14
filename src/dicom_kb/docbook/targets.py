"""Cross-part index of reference targets and how a reference to each reads."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lxml import etree

from dicom_kb.docbook.namespaces import DOCBOOK_NS, xml_id_name
from dicom_kb.docbook.text_chunks import normalize_text

# Elements a reference can name directly. Anything else that carries an id
# (a para, a list item) is reached through its nearest labelled ancestor.
TARGET_KINDS = frozenset(
    {
        "book",
        "chapter",
        "section",
        "table",
        "informaltable",
        "figure",
        "equation",
        "example",
        "biblioentry",
        "glossentry",
    }
)
_LETTER_LABEL_RE = re.compile(r"^[A-Z]{1,3}$")
_NAMED_LABEL_RE = re.compile(r"^(?:CID|TID)\s")
_KIND_WORDS = {
    "table": "Table",
    "informaltable": "Table",
    "figure": "Figure",
    "equation": "Equation",
    "example": "Example",
}


@dataclass(frozen=True)
class Target:
    """A referenceable element: where it is and how it is labelled."""

    part: str
    xml_id: str
    kind: str
    label: str | None
    title: str | None

    @property
    def name(self) -> str:
        """How the standard names it, e.g. `Table C.7-5a` or `Annex A`."""
        label = self.label
        if self.kind == "book":
            return self.part
        if not label:
            return self.title or self.xml_id
        if self.kind in _KIND_WORDS:
            return f"{_KIND_WORDS[self.kind]} {label}"
        if self.kind == "biblioentry":
            return f"[{label}]"
        if self.kind == "glossentry" or _NAMED_LABEL_RE.match(label):
            return label
        if self.kind == "chapter" and _LETTER_LABEL_RE.match(label):
            return f"Annex {label}"
        return f"Section {label}"

    @property
    def globally_unique(self) -> bool:
        """CIDs and TIDs need no part to be found, so references omit it."""
        return bool(self.label and _NAMED_LABEL_RE.match(self.label))


@dataclass
class TargetIndex:
    """Every labelled target in the parts being built, keyed by part and id."""

    _by_part: dict[str, dict[str, Target]] = field(default_factory=dict)

    def add_document(self, root: etree._Element, *, part: str) -> None:
        """Index one part's labelled elements."""
        targets = self._by_part.setdefault(part, {})
        for element in root.iter():
            if not isinstance(element.tag, str):
                continue
            xml_id = element.get(xml_id_name())
            if not xml_id:
                continue
            kind = etree.QName(element).localname
            if kind not in TARGET_KINDS:
                continue
            targets[xml_id] = Target(
                part=part,
                xml_id=xml_id,
                kind=kind,
                label=_label(element, kind),
                title=_title(element, kind) or (part if kind == "book" else None),
            )

    def get(self, part: str, xml_id: str) -> Target | None:
        """Return a target, or None when the part does not define it."""
        return self._by_part.get(part, {}).get(xml_id)

    def has_part(self, part: str) -> bool:
        """Report whether a part was indexed, to tell gaps from absent parts."""
        return part in self._by_part


def target_for_element(element: etree._Element, *, part: str) -> Target | None:
    """Describe an element, or its nearest labelled ancestor, as a target."""
    current: etree._Element | None = element
    while current is not None:
        kind = etree.QName(current).localname if isinstance(current.tag, str) else ""
        xml_id = current.get(xml_id_name())
        if kind in TARGET_KINDS and xml_id:
            return Target(
                part=part,
                xml_id=xml_id,
                kind=kind,
                label=_label(current, kind),
                title=_title(current, kind) or (part if kind == "book" else None),
            )
        current = current.getparent()
    return None


def element_label(element: etree._Element) -> str | None:
    """Return a section or table label such as `C.7.3.1`, or None."""
    return _label(element, etree.QName(element).localname)


def element_title(element: etree._Element) -> str | None:
    """Return the title or caption of a section, table, or figure."""
    return _title(element, etree.QName(element).localname)


def _label(element: etree._Element, kind: str) -> str | None:
    if kind == "biblioentry":
        return _child_text(element, "abbrev") or None
    if kind == "glossentry":
        return _child_text(element, "glossterm") or None
    label = normalize_text(element.get("label") or "")
    if label:
        return label
    return _label_from_id(element.get(xml_id_name()) or "", kind)


_ID_PREFIXES = {
    "section": "sect_",
    "chapter": "chapter_",
    "table": "table_",
    "informaltable": "table_",
    "figure": "figure_",
    "equation": "equation_",
    "example": "example_",
}


def _label_from_id(xml_id: str, kind: str) -> str | None:
    """Fall back to the label NEMA encodes in ids, e.g. sect_C.7.3.1."""
    prefix = _ID_PREFIXES.get(kind)
    if prefix is None or not xml_id.startswith(prefix):
        return None
    label = xml_id.removeprefix(prefix)
    if label.startswith(("CID_", "TID_")):
        return label.replace("_", " ", 1)
    # chapter_Notice and similar unnumbered front matter carry no label.
    if kind == "chapter" and not re.fullmatch(r"[A-Z]{1,3}|\d+", label):
        return None
    return label or None


def _title(element: etree._Element, kind: str) -> str | None:
    if kind in {"table", "informaltable"}:
        return _child_text(element, "caption") or _child_text(element, "title")
    if kind == "book":
        return None
    return _child_text(element, "title") or None


def _child_text(element: etree._Element, local_name: str) -> str | None:
    child = element.find(f"{{{DOCBOOK_NS}}}{local_name}")
    if child is None:
        return None
    return normalize_text("".join(child.itertext())) or None
