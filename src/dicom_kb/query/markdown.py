"""Render resolver answers as compact markdown for agents."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from dicom_kb.query.answer_contracts import StandardRef, ToolResponse

Renderer = Callable[[dict[str, Any]], list[str]]

# Internal keys that identify rows in the database but tell an agent nothing.
_HIDDEN_KEYS = frozenset(
    {
        "id",
        "attribute_use_id",
        "condition_id",
        "included_macro_id",
        "expanded_from_include_id",
        "parent_attribute_use_id",
        "module_id",
        "iod_id",
        "owner_type",
        "row_order",
        "order",
        "row_kind",
        "sequence_depth",
        "resolution",
    }
)
_MAX_SOURCES = 5


def render_markdown(response: ToolResponse) -> str:
    """Return the answer as markdown with one closing source line."""
    result = response.result or {}
    if response.status != "ok":
        lines = [str(result.get("message", "No match."))]
        candidates = result.get("candidates")
        if isinstance(candidates, list) and candidates:
            lines += ["", "Candidates:", *_table(candidates)]
    else:
        lines = _renderer_for(result)(result)
    if response.warnings:
        lines += ["", *(f"Warning: {warning}" for warning in response.warnings)]
    source = source_line(response.refs)
    if source:
        lines += ["", source]
    return "\n".join(lines).strip() + "\n"


def source_line(refs: Iterable[StandardRef]) -> str:
    """Name where the answer comes from, e.g. `Source: PS3.6 Table 6-1 (2026d)`."""
    labels: list[str] = []
    edition = None
    for ref in refs:
        edition = edition or ref.edition
        label = ref_label(ref)
        if label not in labels:
            labels.append(label)
    if not labels:
        return ""
    shown = labels[:_MAX_SOURCES]
    more = len(labels) - len(shown)
    tail = f" and {more} more" if more else ""
    return f"Source: {'; '.join(shown)}{tail} ({edition})"


def ref_label(ref: StandardRef) -> str:
    """Return a readable locator such as `PS3.3 Table C.7-9` or `PS3.16 CID 29`."""
    if ref.label:
        return ref.label
    for candidate in (ref.anchor, ref.section):
        if candidate:
            label = _locator(candidate)
            if label:
                return f"{ref.part} {label}"
    return ref.part


def _locator(xml_id: str) -> str | None:
    match = re.fullmatch(r"(?:table|sect)_(CID|TID)_(\w+)", xml_id)
    if match:
        return f"{match.group(1)} {match.group(2)}"
    if xml_id.startswith("table_"):
        return f"Table {xml_id.removeprefix('table_')}"
    if xml_id.startswith("sect_"):
        return xml_id.removeprefix("sect_")
    if xml_id.startswith(("chapter_", "PS3.")):
        return xml_id.removeprefix("chapter_")
    return None


def _renderer_for(result: dict[str, Any]) -> Renderer:
    keys = set(result)
    for required, renderer in _RENDERERS:
        if required <= keys:
            return renderer
    return _render_generic


def _render_value_terms(result: dict[str, Any]) -> list[str]:
    attribute = result.get("attribute")
    heading = (
        f"**{attribute['tag']} {attribute['name']}**" if attribute else "**Values**"
    )
    terms = result.get("terms", [])
    contexts = {term.get("context_label") for term in terms}
    rows = [
        {
            "Value": term.get("value"),
            "Meaning": term.get("meaning"),
            "Kind": _kind(term.get("term_kind")),
            # A context shared by every row is noise; keep it only to tell
            # apart value lists from different modules.
            "Context": term.get("context_label") if len(contexts) > 1 else None,
        }
        for term in terms
    ]
    return [heading, "", *_table(rows)]


def _render_context_group(result: dict[str, Any]) -> list[str]:
    heading = f"**{_prefixed('CID', result['cid'])} {result['name']}**"
    facts = [
        f"{label} {result[key]}"
        for label, key in (("Extensibility", "extensibility"), ("Version", "version"))
        if result.get(key)
    ]
    rows = [
        {
            "Scheme": row.get("coding_scheme_designator"),
            "Code": row.get("code_value"),
            "Meaning": row.get("code_meaning")
            or (
                f"Include {_prefixed('CID', row['include_cid'])}"
                if row.get("include_cid")
                else None
            ),
        }
        for row in result.get("rows", [])
    ]
    return [heading, *([" · ".join(facts)] if facts else []), "", *_table(rows)]


def _render_sr_template(result: dict[str, Any]) -> list[str]:
    heading = f"**{_prefixed('TID', result['tid'])} {result['name']}**"
    facts = (
        [f"Extensibility {result['extensibility']}"]
        if result.get("extensibility")
        else []
    )
    rows = [
        {
            "Rel": row.get("relationship_type"),
            "VT": row.get("value_type"),
            "Concept Name": row.get("concept_name")
            or (
                f"Include {_prefixed('TID', row['include_tid'])}"
                if row.get("include_tid")
                else None
            ),
            "VM": row.get("cardinality"),
            "Condition": row.get("condition"),
        }
        for row in result.get("rows", [])
    ]
    return [heading, *facts, "", *_table(rows)]


def _render_generic(result: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, value in result.items():
        if key in _HIDDEN_KEYS or _empty(value):
            continue
        label = key.replace("_", " ").capitalize()
        if isinstance(value, list) and all(isinstance(item, Mapping) for item in value):
            lines += ["", f"**{label}**", *_table(value)]
        elif isinstance(value, list):
            lines += ["", f"**{label}**", *(f"- {_text(item)}" for item in value)]
        elif isinstance(value, Mapping):
            lines += ["", f"**{label}**", *_render_generic(dict(value))]
        else:
            lines.append(f"**{label}:** {_text(value)}")
    return lines


def _render_standard_markdown(result: dict[str, Any]) -> list[str]:
    return [str(result["markdown"])]


def _render_hits(result: dict[str, Any]) -> list[str]:
    note = [str(result["note"]), ""] if result.get("note") else []
    return [*note, *_table(result["hits"])]


_RENDERERS: tuple[tuple[frozenset[str], Renderer], ...] = (
    (frozenset({"markdown"}), _render_standard_markdown),
    (frozenset({"hits"}), _render_hits),
    (frozenset({"attribute", "terms"}), _render_value_terms),
    (frozenset({"cid", "rows"}), _render_context_group),
    (frozenset({"tid", "rows"}), _render_sr_template),
)


def _table(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Render rows as a pipe table, keeping only columns that carry a value."""
    columns: list[str] = []
    for row in rows:
        for key, value in row.items():
            if key not in _HIDDEN_KEYS and key not in columns and not _empty(value):
                columns.append(key)
    if not columns:
        return []
    header = [
        key if key[:1].isupper() else key.replace("_", " ").capitalize()
        for key in columns
    ]
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in rows:
        cells = [_cell(row.get(key)) for key in columns]
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def _cell(value: Any) -> str:
    if _empty(value):
        return ""
    if isinstance(value, Mapping):
        value = value.get("source_text") or value.get("name") or ""
    elif isinstance(value, list):
        value = ", ".join(_text(item) for item in value)
    return _text(value).replace("|", "\\|").replace("\n", " ")


def _text(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return re.sub(r"\s+", " ", str(value)).strip()


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _code(value: Any) -> str:
    return f"`{value}`" if value else "-"


def _kind(term_kind: Any) -> str:
    return {"enumerated_value": "Enumerated", "defined_term": "Defined"}.get(
        str(term_kind), str(term_kind or "")
    )


def _section(value: Any) -> str:
    text = str(value or "")
    return _locator(text) or text


def _prefixed(prefix: str, value: Any) -> str:
    text = str(value)
    return text if text.upper().startswith(prefix) else f"{prefix} {text}"
