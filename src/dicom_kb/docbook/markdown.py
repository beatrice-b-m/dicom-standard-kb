"""Render DocBook content as compact markdown with every reference resolved.

DocBook writes most references as empty `<xref>`/`<olink>` elements whose
visible text is generated from the target. Plain `itertext()` drops them, so
"See for Defined Terms." loses the one thing a reader needs. This renderer
turns each reference into the label the standard prints (`Section C.7.3.1.1.1`,
`Table C.7-5a`, `CID 7010`), adding the part for references into other parts.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from lxml import etree

from dicom_kb.docbook.namespaces import DOCBOOK_NS, xml_id_name
from dicom_kb.docbook.targets import Target, TargetIndex, target_for_element
from dicom_kb.docbook.text_chunks import normalize_text, strip_zero_width

MATHML_NS = "http://www.w3.org/1998/Math/MathML"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
# Placeholder a section body keeps where one of its tables sits; readers
# expand it so a table is stored once but read in place.
TABLE_PLACEHOLDER = "[[table:{xml_id}]]"
TABLE_PLACEHOLDER_RE = re.compile(r"^\[\[table:(?P<xml_id>[^\]]+)\]\]$", re.M)

_REFERENCE_TAGS = frozenset({"xref", "olink", "link"})
_SKIPPED = frozenset(
    {
        "title",
        "caption",
        "titleabbrev",
        "subtitle",
        "info",
        "label",
        "indexterm",
        "remark",
        "colspec",
        "col",
        "colgroup",
    }
)
_LIST_TAGS = frozenset({"itemizedlist", "orderedlist", "simplelist"})
_CODE_TAGS = frozenset({"programlisting", "screen", "literallayout", "synopsis"})
_BLOCK_TAGS = frozenset(
    {
        "para",
        "simpara",
        "formalpara",
        "note",
        "warning",
        "caution",
        "important",
        "tip",
        "variablelist",
        "table",
        "informaltable",
        "figure",
        "informalfigure",
        "mediaobject",
        "equation",
        "informalequation",
        "example",
        "informalexample",
        "glossary",
        "glossdiv",
        "glosslist",
        "glossentry",
        "bibliography",
        "bibliodiv",
        "bibliolist",
        "biblioentry",
        "blockquote",
        "sidebar",
        "section",
        "chapter",
        "legalnotice",
        *_LIST_TAGS,
        *_CODE_TAGS,
    }
)
_SPACE_RE = re.compile(r"[ \t\r\n\f\v]+")


@dataclass
class ReferenceLog:
    """References that could not be resolved, for the build's gap log."""

    unresolved: list[str] = field(default_factory=list)


@dataclass
class MarkdownRenderer:
    """Render one part's DocBook elements as markdown."""

    part: str
    targets: TargetIndex
    log: ReferenceLog = field(default_factory=ReferenceLog)
    _local: dict[str, etree._Element] = field(default_factory=dict)

    @classmethod
    def for_document(
        cls, root: etree._Element, *, part: str, targets: TargetIndex | None = None
    ) -> MarkdownRenderer:
        """Build a renderer that can also resolve ids local to this part."""
        if targets is None:
            targets = TargetIndex()
        if not targets.has_part(part):
            targets.add_document(root, part=part)
        local = {
            str(element.get(xml_id_name())): element
            for element in root.iter()
            if isinstance(element.tag, str) and element.get(xml_id_name())
        }
        return cls(part=part, targets=targets, _local=local)

    # Public entry points -------------------------------------------------

    def section_body(self, section: etree._Element) -> str:
        """Render a section's own content, leaving subsections out.

        Tables that carry an id become placeholders, because each is stored
        and searched as its own node.
        """
        return _join_blocks(self._blocks(section, top=True))

    def table(self, table: etree._Element) -> str:
        """Render a table as a caption line and a pipe table."""
        return "\n".join(self._table_lines(table))

    def title(self, element: etree._Element) -> str | None:
        """Render an element's title or caption, references included."""
        for child in element:
            if _local_name(child) in {"title", "caption"}:
                text = _clean_inline(self._inline_children(child))
                if text:
                    return text
        return None

    def inline_text(self, element: etree._Element) -> str:
        """Render an element as one line: what a table cell or title reads."""
        return _join_cell(self._blocks(element, cell=True))

    # Blocks --------------------------------------------------------------

    def _blocks(
        self, element: etree._Element, *, top: bool = False, cell: bool = False
    ) -> list[str]:
        """Render an element's children as markdown blocks."""
        blocks: list[str] = []
        inline: list[str] = []

        def flush() -> None:
            text = _clean_inline("".join(inline))
            inline.clear()
            if text:
                blocks.append(text)

        if element.text:
            inline.append(element.text)
        for child in element:
            name = _local_name(child)
            if (
                name is None
                or name in _SKIPPED
                or (name in {"section", "chapter"} and top)
            ):
                pass
            elif name in _BLOCK_TAGS:
                flush()
                blocks.extend(self._block(child, top=top, cell=cell))
            else:
                inline.append(self._inline(child))
            if child.tail:
                inline.append(child.tail)
        flush()
        return blocks

    def _block(self, element: etree._Element, *, top: bool, cell: bool) -> list[str]:
        name = _local_name(element) or ""
        if name in {"para", "simpara", "formalpara", "blockquote", "sidebar"}:
            return self._blocks(element, cell=cell)
        if name in {"note", "warning", "caution", "important", "tip"}:
            return self._note(element, cell=cell)
        if name in _LIST_TAGS:
            return [self._list(element, cell=cell)]
        if name == "variablelist":
            return self._variablelist(element, cell=cell)
        if name in _CODE_TAGS:
            return [self._code(element, cell=cell)]
        if name in {"table", "informaltable"}:
            xml_id = element.get(xml_id_name())
            if top and xml_id and not cell:
                return [TABLE_PLACEHOLDER.format(xml_id=xml_id)]
            if cell:
                return [_join_cell(self._blocks(element, cell=True))]
            return ["\n".join(self._table_lines(element))]
        if name in {"figure", "informalfigure", "mediaobject"}:
            return self._figure(element)
        if name in {"equation", "informalequation"}:
            return self._equation(element)
        if name in {"example", "informalexample"}:
            return self._titled(element, cell=cell)
        if name in {"glossary", "glossdiv", "glosslist", "bibliography", "bibliodiv"}:
            return self._titled(element, cell=cell)
        if name == "glossentry":
            return self._glossentry(element, cell=cell)
        if name == "biblioentry":
            return [self._biblioentry(element)]
        if name in {"section", "chapter"}:
            # A section nested where it is not a stored node (inside a cell).
            return self._titled(element, cell=cell)
        return self._blocks(element, cell=cell)

    def _note(self, element: etree._Element, *, cell: bool) -> list[str]:
        title = self.title(element) or "Note"
        body = self._blocks(element, cell=cell)
        if cell:
            return [f"{title}: {_join_cell(body)}"]
        if not body:
            return []
        first, *rest = body
        if first.startswith(("- ", "1. ")):
            quoted = [f"{title}:", first, *rest]
        else:
            quoted = [f"{title}: {first}", *rest]
        return ["\n".join(f"> {line}" if line else ">" for line in _lines(quoted))]

    def _list(self, element: etree._Element, *, cell: bool) -> str:
        name = _local_name(element)
        items = [
            child for child in element if _local_name(child) in {"listitem", "member"}
        ]
        start = _int_or(element.get("startingnumber"), 1)
        rendered: list[str] = []
        for index, item in enumerate(items):
            marker = f"{start + index}." if name == "orderedlist" else "-"
            body = self._blocks(item, cell=cell)
            if cell:
                rendered.append(f"{marker} {_join_cell(body)}".rstrip())
            else:
                rendered.append(_list_item(marker, body))
        if cell:
            return "<br>".join(rendered)
        return "\n".join(rendered)

    def _variablelist(self, element: etree._Element, *, cell: bool) -> list[str]:
        blocks: list[str] = []
        title = self.title(element)
        if title:
            blocks.append(title)
        entries: list[str] = []
        for entry in element:
            if _local_name(entry) != "varlistentry":
                continue
            terms = [
                self.inline_text(term) for term in entry if _local_name(term) == "term"
            ]
            term_text = ", ".join(term.rstrip(":").rstrip() for term in terms if term)
            body: list[str] = []
            for item in entry:
                if _local_name(item) == "listitem":
                    body.extend(self._blocks(item, cell=cell))
            if cell:
                definition = _join_cell(body)
                entries.append(
                    f"{term_text}: {definition}" if definition else term_text
                )
            elif body:
                entries.append(_list_item(f"- {term_text}:", body))
            else:
                entries.append(f"- {term_text}")
        if cell:
            blocks.extend(entries)
            return ["<br>".join(blocks)] if blocks else []
        if entries:
            blocks.append("\n".join(entries))
        return blocks

    def _code(self, element: etree._Element, *, cell: bool) -> str:
        text = strip_zero_width("".join(self._literal(element))).strip("\n")
        if cell:
            return f"`{normalize_text(text)}`"
        return f"```\n{text}\n```"

    def _literal(self, element: etree._Element) -> Iterator[str]:
        if element.text:
            yield element.text
        for child in element:
            if _local_name(child) in _REFERENCE_TAGS:
                yield self._reference(child)
            elif isinstance(child.tag, str):
                yield from self._literal(child)
            if child.tail:
                yield child.tail

    def _figure(self, element: etree._Element) -> list[str]:
        target = target_for_element(element, part=self.part)
        caption = self.title(element)
        alt = normalize_text(
            " ".join(
                "".join(node.itertext())
                for node in element.iter(
                    f"{{{DOCBOOK_NS}}}alt", f"{{{DOCBOOK_NS}}}phrase"
                )
            )
        )
        name = target.name if target and target.kind == "figure" else "Figure"
        parts = [name]
        if caption:
            parts.append(f"“{caption}”")
        description = f" ({alt})" if alt else ""
        return [f"[{' '.join(parts)}{description}: image]"]

    def _equation(self, element: etree._Element) -> list[str]:
        caption = self.title(element)
        target = target_for_element(element, part=self.part)
        name = target.name if target and target.kind == "equation" else None
        formula = _clean_inline(self._math_text(element))
        prefix = " ".join(item for item in (name, caption) if item)
        return [f"{prefix}: {formula}" if prefix else formula]

    def _math_text(self, element: etree._Element) -> str:
        pieces: list[str] = []
        for child in element:
            name = _local_name(child)
            if name in {"title", "caption"}:
                continue
            pieces.append(self._inline(child))
        if not pieces:
            return self._inline(element)
        return " ".join(pieces)

    def _titled(self, element: etree._Element, *, cell: bool) -> list[str]:
        title = self.title(element)
        target = target_for_element(element, part=self.part)
        heading = title
        if target and target.xml_id == element.get(xml_id_name()) and target.label:
            heading = f"{target.name} {title}" if title else target.name
        body = self._blocks(element, cell=cell)
        if cell:
            return [_join_cell([heading or "", *body])]
        return [f"**{heading}**", *body] if heading else body

    def _glossentry(self, element: etree._Element, *, cell: bool) -> list[str]:
        term = ""
        body: list[str] = []
        for child in element:
            name = _local_name(child)
            if name == "glossterm":
                term = self.inline_text(child)
            elif name == "glossdef":
                body.extend(self._blocks(child, cell=cell))
            elif name == "glosssee":
                body.append(f"See {self.inline_text(child)}")
        if cell:
            return [f"{term}: {_join_cell(body)}"]
        return [_list_item(f"- {term}:", body)]

    def _biblioentry(self, element: etree._Element) -> str:
        abbrev = ""
        rest: list[str] = []
        for child in element:
            name = _local_name(child)
            if name == "abbrev":
                abbrev = normalize_text("".join(child.itertext()))
            elif name is not None:
                text = self.inline_text(child)
                if text:
                    rest.append(text)
        body = ". ".join(rest)
        return f"- [{abbrev}] {body}".rstrip() if abbrev else f"- {body}"

    # Tables --------------------------------------------------------------

    def _table_lines(self, table: etree._Element) -> list[str]:
        grid = self._table_grid(table)
        target = target_for_element(table, part=self.part)
        caption = self.title(table)
        heading_parts: list[str] = []
        if target and target.xml_id == table.get(xml_id_name()) and target.label:
            heading_parts.append(target.name)
        if caption:
            heading_parts.append(caption)
        lines = [f"**{': '.join(heading_parts)}**"] if heading_parts else []
        if not grid.rows:
            return lines
        width = max(len(row) for row in grid.rows)
        rows = [row + [""] * (width - len(row)) for row in grid.rows]
        header_count = max(grid.header_rows, 1)
        header = rows[0]
        if grid.header_rows == 0:
            # A pipe table needs a header; an empty one keeps every row as data.
            header = [""] * width
            header_count = 0
        lines.append(_pipe_row(header))
        lines.append("|" + "---|" * width)
        for row in rows[header_count:] if grid.header_rows else rows:
            lines.append(_pipe_row(row))
        for note in grid.footnotes:
            lines.append(note)
        return lines

    def _table_grid(self, table: etree._Element) -> _Grid:
        grid = _Grid()
        occupied: dict[tuple[int, int], str] = {}
        row_index = 0
        for section in ("thead", "tbody", "tfoot"):
            for row in _rows(table, section):
                cells: list[str] = []
                column = 0
                for entry in row:
                    if _local_name(entry) not in {"entry", "td", "th"}:
                        continue
                    while (row_index, column) in occupied:
                        cells.append(occupied.pop((row_index, column)))
                        column += 1
                    text = _escape_cell(self.inline_text(entry))
                    colspan = _span(entry, "colspan") or _name_span(entry)
                    rowspan = _span(entry, "rowspan") or (
                        _int_or(entry.get("morerows"), 0) + 1
                    )
                    for offset in range(colspan):
                        value = text if offset == 0 else ""
                        cells.append(value)
                        for extra in range(1, rowspan):
                            occupied[(row_index + extra, column + offset)] = value
                    column += colspan
                while (row_index, column) in occupied:
                    cells.append(occupied.pop((row_index, column)))
                    column += 1
                grid.rows.append(cells)
                if section == "thead":
                    grid.header_rows += 1
                row_index += 1
        if not grid.rows:
            for row in _rows(table, None):
                grid.rows.append(
                    [
                        _escape_cell(self.inline_text(entry))
                        for entry in row
                        if _local_name(entry) in {"entry", "td", "th"}
                    ]
                )
        for child in table:
            if _local_name(child) in {"para", "note", "itemizedlist", "orderedlist"}:
                grid.footnotes.extend(self._block(child, top=False, cell=False))
        return grid

    # Inline --------------------------------------------------------------

    def _inline(self, element: etree._Element) -> str:
        name = _local_name(element)
        if name is None:
            return ""
        if name in _REFERENCE_TAGS:
            return self._reference(element)
        if name in _SKIPPED:
            return ""
        if name == "subscript":
            return f"_{self._inline_children(element)}"
        if name == "superscript":
            return f"^{self._inline_children(element)}"
        if name in {"quote"}:
            return f"“{self._inline_children(element)}”"
        if name in {"computeroutput", "literal", "code", "filename", "userinput"}:
            text = self._inline_children(element).strip()
            return f"`{text}`" if text else ""
        if name in {"inlinemediaobject", "imageobject", "imagedata"}:
            return ""
        if name in _BLOCK_TAGS:
            # Block content met inside inline content (for example a list in
            # an emphasis): keep its text on one line rather than losing it.
            return " " + _join_cell(self._block(element, top=False, cell=True)) + " "
        if etree.QName(element).namespace == MATHML_NS:
            return self._math(element)
        return self._inline_children(element)

    def _inline_children(self, element: etree._Element) -> str:
        pieces = [element.text or ""]
        for child in element:
            pieces.append(self._inline(child))
            pieces.append(child.tail or "")
        return "".join(pieces)

    def _math(self, element: etree._Element) -> str:
        name = etree.QName(element).localname
        children = [child for child in element if isinstance(child.tag, str)]
        parts = [self._math(child) for child in children]
        if name in {"mi", "mn", "mo", "mtext", "ms"}:
            return normalize_text("".join(element.itertext()))
        if name == "msub" and len(parts) == 2:
            return f"{parts[0]}_{_group(parts[1])}"
        if name == "msup" and len(parts) == 2:
            return f"{parts[0]}^{_group(parts[1])}"
        if name == "msubsup" and len(parts) == 3:
            return f"{parts[0]}_{_group(parts[1])}^{_group(parts[2])}"
        if name == "mfrac" and len(parts) == 2:
            return f"{_group(parts[0])}/{_group(parts[1])}"
        if name == "msqrt":
            return f"sqrt({' '.join(parts)})"
        if name == "mfenced":
            opening = element.get("open", "(")
            closing = element.get("close", ")")
            separator = element.get("separators", ",")[:1] or ","
            return f"{opening}{(separator + ' ').join(parts)}{closing}"
        if name in {"munderover", "munder", "mover"} and parts:
            return " ".join(parts)
        if name == "mtr":
            return " & ".join(parts)
        if name == "mtable":
            return "; ".join(parts)
        return " ".join(part for part in parts if part)

    # References ----------------------------------------------------------

    def _reference(self, element: etree._Element) -> str:
        name = _local_name(element)
        text = normalize_text(self._inline_children(element))
        style = element.get("xrefstyle")
        if text:
            # Authored link text already says what it points to.
            return text
        href = element.get(XLINK_HREF)
        if name == "link" and href and not element.get("linkend"):
            return str(href)
        if name == "olink":
            part = _part_label(element.get("targetdoc"))
            xml_id = element.get("targetptr") or element.get("targetdoc") or ""
        else:
            part = self.part
            xml_id = element.get("linkend") or ""
        target = self._resolve(part, xml_id)
        if target is None:
            self.log.unresolved.append(f"{part} {xml_id}")
            fallback = _fallback_name(xml_id)
            return fallback if part == self.part else f"{part} {fallback}"
        return _format_reference(target, style, current_part=self.part)

    def _resolve(self, part: str, xml_id: str) -> Target | None:
        target = self.targets.get(part, xml_id)
        if target is not None:
            return target
        if part == self.part and xml_id in self._local:
            return target_for_element(self._local[xml_id], part=part)
        if part and xml_id == part:
            return Target(part=part, xml_id=xml_id, kind="book", label=None, title=part)
        return None


@dataclass
class _Grid:
    rows: list[list[str]] = field(default_factory=list)
    header_rows: int = 0
    footnotes: list[str] = field(default_factory=list)


def _format_reference(target: Target, style: str | None, *, current_part: str) -> str:
    """Write a reference the way the standard prints it, with its target."""
    cross_part = target.part != current_part
    label = target.label or ""
    title = target.title or ""
    words: set[str] = set()
    if style and style.strip().startswith("template:"):
        template = style.strip().removeprefix("template:").strip()
        text = (
            template.replace("%n", label or target.name)
            .replace("%t", title)
            .replace("%o", target.part)
            .replace("%p", "")
        )
        text = normalize_text(text)
        if "%n" not in template and target.name not in text:
            text = f"{text} ({_qualified(target, cross_part)})"
        elif cross_part and target.part not in text and not target.globally_unique:
            text = f"{text} in {target.part}"
        return text
    if style:
        words = set(style.replace("select:", " ").replace(",", " ").split())
    wants_label = bool(words & {"label", "labelnumber", "labelnum", "labelname"})
    wants_title = bool(words & {"title", "quotedtitle"})
    wants_docname = "docname" in words
    if not wants_label and not wants_title:
        wants_label = True
    pieces: list[str] = []
    if wants_label or not title:
        pieces.append(_qualified(target, cross_part or wants_docname))
    if wants_title and title and target.kind != "book":
        pieces.append(f"“{title}”" if "quotedtitle" in words or wants_label else title)
    text = " ".join(pieces)
    if wants_title and not wants_label and title and target.kind != "book":
        # A bare title loses its target; keep the label for a follow-up read.
        text = f"{title} ({_qualified(target, cross_part)})"
    return text


def _qualified(target: Target, cross_part: bool) -> str:
    if target.kind == "book":
        return target.part
    if cross_part and not target.globally_unique:
        return f"{target.part} {target.name}"
    return target.name


def _fallback_name(xml_id: str) -> str:
    """Derive a readable name from an id the source does not define."""
    for prefix, word in (
        ("sect_", "Section"),
        ("table_", "Table"),
        ("figure_", "Figure"),
        ("chapter_", "Annex"),
    ):
        if xml_id.startswith(prefix):
            label = xml_id.removeprefix(prefix)
            if label.startswith(("CID_", "TID_")):
                return label.replace("_", " ", 1)
            if prefix == "chapter_" and label.isdigit():
                return f"Section {label}"
            return f"{word} {label}"
    return xml_id


def _part_label(value: str | None) -> str:
    if not value:
        return ""
    match = re.match(r"(?i)^PS\s?3\.?(\d+)", value.strip())
    return f"PS3.{int(match.group(1))}" if match else value.strip()


def _rows(table: etree._Element, section: str | None) -> list[etree._Element]:
    found: list[etree._Element] = []
    for group in table.iter():
        name = _local_name(group)
        if section is None and name in {"row", "tr"}:
            found.append(group)
        elif name == section:
            found.extend(
                child for child in group if _local_name(child) in {"row", "tr"}
            )
    return found


def _span(entry: etree._Element, attribute: str) -> int:
    value = _int_or(entry.get(attribute), 0)
    return value if value > 0 else 0


def _name_span(entry: etree._Element) -> int:
    start = entry.get("namest")
    end = entry.get("nameend")
    if start and end:
        start_match = re.search(r"(\d+)$", start)
        end_match = re.search(r"(\d+)$", end)
        if start_match and end_match:
            return max(int(end_match.group(1)) - int(start_match.group(1)) + 1, 1)
    return 1


def _int_or(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _local_name(element: object) -> str | None:
    if not isinstance(element, etree._Element) or not isinstance(element.tag, str):
        return None
    return str(etree.QName(element).localname)


def _clean_inline(text: str) -> str:
    return _SPACE_RE.sub(" ", strip_zero_width(text)).strip()


def _join_blocks(blocks: list[str]) -> str:
    return "\n\n".join(block for block in blocks if block)


def _join_cell(blocks: list[str]) -> str:
    return "<br>".join(block.replace("\n", "<br>") for block in blocks if block)


def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|")


def _pipe_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _lines(blocks: list[str]) -> list[str]:
    lines: list[str] = []
    for index, block in enumerate(blocks):
        if index:
            lines.append("")
        lines.extend(block.split("\n"))
    return lines


def _list_item(marker: str, body: list[str]) -> str:
    if not body:
        return marker
    indent = " " * (len(marker.split(" ")[0]) + 1)
    first, *rest = body
    lines = [f"{marker} {first.split(chr(10))[0]}"]
    lines.extend(f"{indent}{line}" if line else "" for line in first.split("\n")[1:])
    for block in rest:
        lines.extend(f"{indent}{line}" if line else "" for line in block.split("\n"))
    return "\n".join(lines)


def _group(text: str) -> str:
    return text if re.fullmatch(r"[\w.]+", text) else f"({text})"


_LINE_MARKER_RE = re.compile(r"^(?:[-*]|\d+\.)\s+", re.M)
_TABLE_RULE_RE = re.compile(r"^\|(?:---\|)+$", re.M)
_PIPE_EDGE_RE = re.compile(r"^\|\s?|\s?\|$", re.M)


def plain_text(markdown: str) -> str:
    """Flatten rendered markdown to one line of words, for parsers and search."""
    text = TABLE_PLACEHOLDER_RE.sub(" ", markdown)
    text = _TABLE_RULE_RE.sub(" ", text)
    text = _PIPE_EDGE_RE.sub(" ", text)
    text = _LINE_MARKER_RE.sub("", text)
    text = text.replace("<br>", " ").replace("**", "").replace(" | ", " ")
    return normalize_text(text.replace("```", " "))
