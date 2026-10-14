"""Transfer syntax encoding facts read from PS3.5 Annex A.

Each transfer syntax UID is defined by the Annex A section that names it. That
section, the section it says to encode by first (A.5 on A.2), or its parent
(A.4.1 on A.4) states the VR style and byte order of the Data Set and how Pixel
Data is carried. Nothing is guessed from the UID's name.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, replace

from dicom_kb.docbook.parser import ParsedDocument, ParsedSection
from dicom_kb.ir.models import ParserWarning, TransferSyntaxDetail

_UID_RE = re.compile(r"(?<![\d.])1\.2\.840\.10008(?:\.\d+)+(?!\d)")
_VR_RE = re.compile(r"encoded with (Implicit|Explicit) VR\b")
_BYTE_ORDER_RE = re.compile(
    r"Data Set structure \([^)]*\) shall be in (Little|Big) Endian"
)
_BASE_RE = re.compile(
    r"first encoded according to the rules specified in Section (A(?:\.\d+)+)"
)
_ENCAPSULATED_RE = re.compile(r"shall be Encapsulated Format")
_REFERENCED_RE = re.compile(
    r"shall not be present, but rather (?:integer )?Pixel Data shall be "
    r"referenced via (?:Data Element )?\(0028,7FE0\)"
)
_RTV_RE = re.compile(r"used in a DICOM-RTV Metadata Flow")
_DEFLATE_DATA_SET_RE = re.compile(
    r"entire byte stream is then compressed using the \W?Deflate", re.I
)
_DEFLATE_FRAME_RE = re.compile(
    r"each frame is separately compressed using the Deflate", re.I
)
# PS3.22 7.1: the RTV transfer syntaxes describe the video or audio Flow; the
# metadata itself always uses one fixed transfer syntax.
_RTV_METADATA_RE = re.compile(
    r"RTV Metadata which is encoded using the (Implicit|Explicit) VR "
    r"(Little|Big) Endian Transfer Syntax"
)

NATIVE = "Native"
ENCAPSULATED = "Encapsulated"
REFERENCED = "Not in the Data Set: referenced by Pixel Data Provider URL (0028,7FE0)"
RTV_FLOW = "Not in the Data Set: sent as a separate DICOM-RTV Flow"
DEFLATE_DATA_SET = "Whole Data Set"
DEFLATE_FRAMES = "Each frame"


@dataclass(frozen=True)
class TransferSyntaxUID:
    """A transfer syntax UID from the PS3.6 registry."""

    uid: str
    retired: bool


@dataclass(frozen=True)
class TransferSyntaxParseResult:
    """Encoding facts per transfer syntax and the UIDs left without them."""

    details: tuple[TransferSyntaxDetail, ...]
    warnings: tuple[ParserWarning, ...]


@dataclass(frozen=True)
class _Facts:
    vr_encoding: str | None = None
    byte_order: str | None = None
    pixel_data: str | None = None
    deflate: str | None = None


def parse_transfer_syntaxes(
    document: ParsedDocument,
    *,
    edition: str,
    transfer_syntaxes: Iterable[TransferSyntaxUID],
    rtv_document: ParsedDocument | None = None,
) -> TransferSyntaxParseResult:
    """Read each transfer syntax's encoding facts from PS3.5 Annex A.

    Pass PS3.22 as `rtv_document` so the DICOM-RTV transfer syntaxes get the
    encoding of the metadata that carries them.
    """
    reader = _AnnexReader(document, rtv_document)
    details: list[TransferSyntaxDetail] = []
    warnings: list[ParserWarning] = []
    for entry in transfer_syntaxes:
        sections = reader.defining_sections(entry.uid)
        if not sections:
            if not entry.retired:
                warnings.append(_warning(f"no Annex A section defines {entry.uid}"))
            continue
        section = sections[0]
        if len(sections) > 1:
            others = ", ".join(s.number or "" for s in sections[1:])
            warnings.append(
                _warning(
                    f"{entry.uid} is also named in Annex A {others}; "
                    f"using {section.number}"
                )
            )
        facts = reader.facts(section)
        vr, order, pixel_data = facts.vr_encoding, facts.byte_order, facts.pixel_data
        if vr is None or order is None or pixel_data is None:
            missing = [
                name
                for name, value in (
                    ("VR", vr),
                    ("byte order", order),
                    ("Pixel Data encoding", pixel_data),
                )
                if value is None
            ]
            warnings.append(
                _warning(
                    f"Section {section.number} gives no {', '.join(missing)} "
                    f"for {entry.uid}"
                )
            )
            continue
        details.append(
            TransferSyntaxDetail(
                id=f"{edition}.transfer_syntax.{entry.uid}",
                edition_id=edition,
                uid_value=entry.uid,
                vr_encoding=vr,
                byte_order=order,
                pixel_data=pixel_data,
                deflate=facts.deflate,
                section_xml_id=section.xml_id or "",
                see_also=reader.mentions(entry.uid, exclude=section.xml_id),
            )
        )
    return TransferSyntaxParseResult(details=tuple(details), warnings=tuple(warnings))


class _AnnexReader:
    def __init__(
        self, document: ParsedDocument, rtv_document: ParsedDocument | None
    ) -> None:
        self.sections = {s.xml_id: s for s in document.sections if s.xml_id}
        self.annex = [s for s in document.sections if _in_annex_a(s)]
        self.by_number = {s.number: s for s in self.annex if s.number}
        tables_by_parent: dict[str, list[str]] = {}
        for table in document.tables:
            if table.parent_xml_id:
                tables_by_parent.setdefault(table.parent_xml_id, []).append(
                    table.markdown
                )
        # Rules are read without notes: notes restate other sections' UIDs.
        self.rules = {
            s.xml_id: _without_notes(
                "\n".join([s.markdown, *tables_by_parent.get(s.xml_id or "", [])])
            )
            for s in self.annex
            if s.xml_id
        }
        self.texts: list[tuple[str, str]] = [
            (s.xml_id, s.markdown) for s in document.sections if s.xml_id
        ] + [(t.xml_id, t.markdown) for t in document.tables if t.xml_id]
        self.rtv = _rtv_metadata(rtv_document)
        self._facts: dict[str, _Facts] = {}

    def defining_sections(self, uid: str) -> list[ParsedSection]:
        return [
            section
            for section in self.annex
            if uid in _UID_RE.findall(self.rules.get(section.xml_id or "", ""))
        ]

    def mentions(self, uid: str, *, exclude: str | None) -> tuple[str, ...]:
        """Other PS3.5 sections and tables that name the UID, in document order."""
        return tuple(
            xml_id
            for xml_id, text in self.texts
            if xml_id != exclude and uid in _UID_RE.findall(text)
        )

    def facts(self, section: ParsedSection) -> _Facts:
        key = section.xml_id or ""
        if key not in self._facts:
            self._facts[key] = self._read_facts(section)
        return self._facts[key]

    def _read_facts(self, section: ParsedSection) -> _Facts:
        text = self.rules.get(section.xml_id or "", "")
        vr = _VR_RE.search(text)
        order = _BYTE_ORDER_RE.search(text)
        facts = _Facts(
            vr_encoding=f"{vr.group(1)} VR" if vr else None,
            byte_order=f"{order.group(1)} Endian" if order else None,
            pixel_data=_pixel_data(text),
            deflate=(
                DEFLATE_DATA_SET
                if _DEFLATE_DATA_SET_RE.search(text)
                else DEFLATE_FRAMES
                if _DEFLATE_FRAME_RE.search(text)
                else None
            ),
        )
        if _RTV_RE.search(text) and self.rtv is not None:
            facts = replace(
                facts,
                vr_encoding=facts.vr_encoding or self.rtv.vr_encoding,
                byte_order=facts.byte_order or self.rtv.byte_order,
            )
        base = _BASE_RE.search(text)
        if base and base.group(1) in self.by_number:
            facts = _fill(facts, self.facts(self.by_number[base.group(1)]))
        parent = self.sections.get(section.parent_xml_id or "")
        if parent is not None and _in_annex_a(parent):
            facts = _fill(facts, self.facts(parent))
        if facts.pixel_data is None and vr is not None:
            # A section that sets the Data Set's own VR rules and says nothing
            # else about Pixel Data keeps it in Native Format.
            facts = replace(facts, pixel_data=NATIVE)
        return facts


def _fill(facts: _Facts, inherited: _Facts) -> _Facts:
    """Take what this section leaves unsaid from the section it builds on."""
    return replace(
        facts,
        vr_encoding=facts.vr_encoding or inherited.vr_encoding,
        byte_order=facts.byte_order or inherited.byte_order,
        pixel_data=facts.pixel_data or inherited.pixel_data,
    )


def _pixel_data(text: str) -> str | None:
    if _REFERENCED_RE.search(text):
        return REFERENCED
    if _ENCAPSULATED_RE.search(text):
        return ENCAPSULATED
    if _RTV_RE.search(text):
        return RTV_FLOW
    return None


def _rtv_metadata(document: ParsedDocument | None) -> _Facts | None:
    if document is None:
        return None
    for section in document.sections:
        match = _RTV_METADATA_RE.search(section.plain_text)
        if match:
            return _Facts(
                vr_encoding=f"{match.group(1)} VR",
                byte_order=f"{match.group(2)} Endian",
            )
    return None


def _in_annex_a(section: ParsedSection) -> bool:
    number = section.number or ""
    return number == "A" or number.startswith("A.")


def _without_notes(markdown: str) -> str:
    return "\n".join(
        line for line in markdown.splitlines() if not line.lstrip().startswith(">")
    )


def _warning(message: str) -> ParserWarning:
    return ParserWarning(part="PS3.5", table_id=None, row_index=None, message=message)
