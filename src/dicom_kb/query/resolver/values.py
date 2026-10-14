"""What an attribute may hold: enumerated values, defined terms and CIDs."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field

from dicom_kb.db.repositories import DataElementRepository
from dicom_kb.ir.models import DataElement
from dicom_kb.query.answer_contracts import ToolResponse
from dicom_kb.query.resolver.objects import (
    _close_matches,
    _element_heading,
    _element_names,
    _find_iod,
    _find_owner,
    _functional_group_uses,
    _iod_and_sop_class_names,
    _module_uses,
    _not_found,
    _paged,
    _pipe,
    _ref,
    _Tables,
    _xml_id_label,
)

# Places named in one cell before the rest are counted.
_MAX_PLACES_NAMED = 12
# A meaning longer than this is cut at a sentence; dicom_read has all of it.
_MAX_MEANING_CHARS = 300
_CODE_VALUE_TAG = "(0008,0100)"
_CID_RE = re.compile(r"\b[BDE]?CIDs?\b")
_VALUES_RE = re.compile(r"Enumerated Value|Defined Term|\b[BDE]?CIDs?\b", re.I)
_INCLUDE_PREFIX_RE = re.compile(
    r"^>*\s*Include\s+(?:PS3\.\d+\s+)?(?:Table|Section)\s+\S+\s*"
    r"(?:“[^”]*”|\"[^\"]*\")?\s*\.?\s*",
    re.I,
)
_PLAIN_TITLES = {
    "enumerated values",
    "enumerated value",
    "defined terms",
    "defined term",
}
_KIND_LABEL = {"enumerated_value": "Enumerated Values", "defined_term": "Defined Terms"}


@dataclass(frozen=True)
class _Use:
    """A module or macro row that lists the attribute."""

    id: str
    owner_id: str
    row_order: int
    depth: int
    description: str


@dataclass
class _List:
    """One list of values, and the modules and macros it applies in."""

    kind: str
    title: str
    section_id: str | None
    terms: list[tuple[str, str | None]] = field(default_factory=list)
    owners: list[str] = field(default_factory=list)
    from_row: bool = False


def attribute_values(
    connection: sqlite3.Connection,
    *,
    name: str,
    edition: str,
    within: str | None = None,
    page: int = 1,
) -> ToolResponse:
    """Return an attribute's enumerated values, defined terms and CIDs.

    With `within` (an IOD, module or macro) only what applies there is kept.
    """
    element, _ = DataElementRepository(connection).find_by_tag_or_keyword(
        name.strip(), edition=edition
    )
    if element is None:
        return _not_found(
            f"No data element is named {name!r}.",
            _close_matches(name, _element_names(connection, edition)),
        )
    tables = _Tables(connection, edition)
    scope: set[str] | None = None
    scope_label = ""
    if within is not None:
        found = _scope(connection, tables, within, edition=edition)
        if found is None:
            names = [owner.label for owner in tables.owners().values()]
            return _not_found(
                f"No IOD, module or macro is named {within!r}.",
                _close_matches(
                    within, [*names, *_iod_and_sop_class_names(connection, edition)]
                ),
            )
        scope, scope_label = found

    uses = _uses(connection, element.tag, edition=edition)
    in_scope = [use for use in uses if scope is None or use.owner_id in scope]
    lists = _lists(
        connection, element.tag, in_scope, edition=edition, scoped=bool(scope)
    )
    codes = _codes(connection, tables, element, uses, scope, edition=edition)

    lines = [_element_heading(element)]
    if scope_label:
        lines.append(f"In {scope_label}.")
    explained = {owner for value_list in lists for owner in value_list.owners}
    explained |= {owner for _, owners in codes for owner in owners}
    for value_list in lists:
        lines += ["", *_render_list(tables, value_list)]
    if codes:
        lines += [
            "",
            "**Context groups** for its Code Sequence items:",
            "",
            "| Where | Codes |",
            "|---|---|",
            *(_pipe(_places(tables, owners), text) for text, owners in codes),
        ]
    pointers = _pointers(tables, in_scope, explained)
    if pointers:
        lines += [
            "",
            "Other descriptions that name values:",
            "",
            "| Where | Description |",
            "|---|---|",
            *pointers,
        ]
    if not lists and not codes and not pointers:
        lines += [
            "",
            "No enumerated values, defined terms or context groups are given "
            "for it" + (f" in {scope_label}." if scope_label else "."),
        ]
    if codes:
        lines += ["", 'A group\'s codes: dicom_code("CID <n>").']
    refs = sorted(
        {value_list.section_id for value_list in lists if value_list.section_id}
    )
    call = f'dicom_values("{name}"'
    if within is not None:
        call += f', within="{within}"'
    return _paged(
        "\n".join(lines),
        page=page,
        next_call=call + ", page={page})",
        refs=[_ref(edition, element.source_ref.table_id, part="PS3.6")]
        + [_ref(edition, section) for section in refs],
    )


def _scope(
    connection: sqlite3.Connection, tables: _Tables, name: str, *, edition: str
) -> tuple[set[str], str] | None:
    """Return the modules and macros an IOD, module or macro reaches.

    An IOD wins over a module of the same name: "CT Image" is the IOD, which
    holds the CT Image Module and every other module that applies.
    """
    iod = None
    if not re.search(r"\b(?:module|macro)(?: attributes)?$", name.strip(), re.I):
        iod = _find_iod(connection, name, edition=edition)
    if iod is not None:
        roots = [
            use.module_id
            for use in [
                *_module_uses(connection, iod.id, edition=edition),
                *_functional_group_uses(connection, iod.id, edition=edition),
            ]
        ]
        label = f"the {iod.name} IOD"
    else:
        owner = _find_owner(tables, name)
        if owner is None:
            return None
        roots = [owner.id]
        label = f"the {owner.label}"
    reached: set[str] = set()
    for root in roots:
        reached.add(root)
        for line in tables.expand(root):
            if line.row.macro_id is not None:
                reached.add(line.row.macro_id)
    return reached, label


def _uses(connection: sqlite3.Connection, tag: str, *, edition: str) -> list[_Use]:
    return [
        _Use(
            id=row["id"],
            owner_id=row["owner_id"],
            row_order=int(row["row_order"]),
            depth=int(row["sequence_depth"]),
            description=row["description_text"] or "",
        )
        for row in connection.execute(
            """
            SELECT id, owner_id, row_order, sequence_depth, description_text
            FROM attribute_use
            WHERE edition_id = ? AND row_kind = 'attribute' AND attribute_tag = ?
            ORDER BY owner_type DESC, owner_id, row_order
            """,
            (edition, tag),
        )
    ]


def _lists(
    connection: sqlite3.Connection,
    tag: str,
    uses: list[_Use],
    *,
    edition: str,
    scoped: bool,
) -> list[_List]:
    """Collect the attribute's lists, merging ones that say the same thing."""
    owner_of = {use.id: use.owner_id for use in uses}
    by_index: dict[int, _List] = {}
    for row in connection.execute(
        """
        SELECT list_index, list_title, term_kind, value, meaning,
               attribute_use_id, table_id, section_id
        FROM attribute_value_term
        WHERE edition_id = ? AND attribute_tag = ?
        ORDER BY list_index, term_order
        """,
        (edition, tag),
    ):
        value_list = by_index.get(row["list_index"])
        if value_list is None:
            use_id = row["attribute_use_id"]
            if use_id is not None:
                if use_id not in owner_of:
                    continue  # out of scope
                owners = [owner_of[use_id]]
            elif row["table_id"] is not None:
                if scoped:
                    continue
                owners = []
            else:
                owners = _owners_pointing_at(uses, row["section_id"])
                if scoped and not owners:
                    continue
            value_list = by_index[row["list_index"]] = _List(
                kind=row["term_kind"],
                title=row["list_title"],
                section_id=row["section_id"] if use_id is None else None,
                owners=owners,
                from_row=use_id is not None,
            )
        value_list.terms.append((row["value"], row["meaning"]))

    merged: dict[tuple[object, ...], _List] = {}
    for value_list in by_index.values():
        key = (
            value_list.kind,
            _qualifier(value_list.title),
            value_list.section_id,
            tuple(value_list.terms),
        )
        if key in merged:
            merged[key].owners += [
                owner for owner in value_list.owners if owner not in merged[key].owners
            ]
        else:
            merged[key] = value_list
    # Definitions in sections first, then the lists most modules share.
    return sorted(merged.values(), key=lambda item: (item.from_row, -len(item.owners)))


def _owners_pointing_at(uses: Iterable[_Use], section_id: str | None) -> list[str]:
    if not section_id:
        return []
    label = re.escape(_xml_id_label(section_id))
    pattern = re.compile(rf"\bSection {label}(?![.\-]?\w)")
    return list(
        dict.fromkeys(use.owner_id for use in uses if pattern.search(use.description))
    )


def _render_list(tables: _Tables, value_list: _List) -> list[str]:
    title = value_list.title.rstrip(":").strip()
    if title.lower() in _PLAIN_TITLES:
        title = _KIND_LABEL[value_list.kind]
    heading = f"**{title}**"
    if value_list.section_id:
        heading += f" (Section {_xml_id_label(value_list.section_id)})"
    if value_list.owners:
        heading += (", referenced by " if value_list.section_id else " in ") + _places(
            tables, value_list.owners
        )
    if not any(meaning for _, meaning in value_list.terms):
        return [heading + ": " + ", ".join(value for value, _ in value_list.terms)]
    lines = [heading, "", "| Value | Meaning |", "|---|---|"]
    cut = False
    for value, meaning in value_list.terms:
        text = _shorten(meaning or "")
        cut = cut or text != (meaning or "")
        lines.append(_pipe(value, text))
    if cut and value_list.section_id:
        lines += [
            "",
            "Meanings are cut short; "
            f'dicom_read("PS3.3 {_xml_id_label(value_list.section_id)}") '
            "has them in full.",
        ]
    return lines


def _places(tables: _Tables, owner_ids: list[str]) -> str:
    labels = [
        owner.label if (owner := tables.owner(owner_id)) else owner_id
        for owner_id in owner_ids
    ]
    if len(labels) > _MAX_PLACES_NAMED:
        shown = ", ".join(labels[:_MAX_PLACES_NAMED])
        return f"{shown} and {len(labels) - _MAX_PLACES_NAMED} more"
    return ", ".join(labels)


def _shorten(text: str) -> str:
    if len(text) <= _MAX_MEANING_CHARS:
        return text
    head = text[:_MAX_MEANING_CHARS]
    stop = max(head.rfind(". "), head.rfind("<br>"))
    if stop > 80:
        head = head[: stop + 1] if head[stop] == "." else head[:stop]
    return head.rstrip() + " …"


def _qualifier(title: str) -> str:
    text = title.rstrip(":").strip().lower()
    return "" if text in _PLAIN_TITLES else text


# Context groups -------------------------------------------------------------


def _codes(
    connection: sqlite3.Connection,
    tables: _Tables,
    element: DataElement,
    uses: list[_Use],
    scope: set[str] | None,
    *,
    edition: str,
) -> list[tuple[str, list[str]]]:
    """Return each CID statement for the attribute and where it is made.

    A Code Sequence Macro included under the attribute names its group. So
    does a module that includes a macro holding the attribute, when its
    include text names the attribute, or names none of the macro's
    attributes and the attribute comes first in the macro.
    """
    code_macros = _code_macros(connection, edition=edition)
    found: dict[str, list[str]] = {}

    def add(text: str, owner_id: str) -> None:
        owners = found.setdefault(text, [])
        if owner_id not in owners:
            owners.append(owner_id)

    for use in uses:
        if scope is not None and use.owner_id not in scope:
            continue
        rows = connection.execute(
            """
            SELECT row_kind, sequence_depth, included_macro_id, include_target_text
            FROM attribute_use
            WHERE edition_id = ? AND owner_id = ? AND row_order > ?
            ORDER BY row_order
            """,
            (edition, use.owner_id, use.row_order),
        )
        for row in rows:
            depth = int(row["sequence_depth"])
            if depth <= use.depth:
                break
            text = _include_note(row["include_target_text"])
            if (
                row["row_kind"] == "include"
                and depth == use.depth + 1
                and row["included_macro_id"] in code_macros
                and _CID_RE.search(text)
            ):
                add(text, use.owner_id)

    holders = {
        use.owner_id
        for use in uses
        if use.owner_id not in code_macros
        and (owner := tables.owner(use.owner_id)) is not None
        and owner.kind == "macro"
    }
    first_in = {
        holder
        for holder in holders
        if _first_attribute_tag(tables, holder) == element.tag
    }
    names = [element.name.lower(), element.tag.lower()]
    if element.keyword:
        names.append(element.keyword.lower())
    pending = list(holders)
    reached = set(holders)
    while pending:
        macro_id = pending.pop()
        for row in connection.execute(
            """
            SELECT owner_id, include_target_text FROM attribute_use
            WHERE edition_id = ? AND row_kind = 'include' AND included_macro_id = ?
            """,
            (edition, macro_id),
        ):
            includer = str(row["owner_id"])
            owner = tables.owner(includer)
            if owner is not None and owner.kind == "macro" and includer not in reached:
                reached.add(includer)
                pending.append(includer)
            text = _include_note(row["include_target_text"])
            if not _CID_RE.search(text):
                continue
            if scope is not None and includer not in scope:
                continue
            lowered = text.lower()
            if any(name in lowered for name in names) or (
                macro_id in first_in
                and not _names_any_attribute(tables, macro_id, lowered)
            ):
                macro = tables.owner(macro_id)
                add(f"{text} (via {macro.name})" if macro else text, includer)
    return list(found.items())


def _code_macros(connection: sqlite3.Connection, *, edition: str) -> set[str]:
    """Macros whose top level holds Code Value, directly or by an include."""
    found = {
        str(row[0])
        for row in connection.execute(
            """
            SELECT DISTINCT owner_id FROM attribute_use
            WHERE edition_id = ? AND owner_type = 'macro' AND attribute_tag = ?
              AND sequence_depth = 0
            """,
            (edition, _CODE_VALUE_TAG),
        )
    }
    includes = connection.execute(
        """
        SELECT owner_id, included_macro_id FROM attribute_use
        WHERE edition_id = ? AND owner_type = 'macro' AND row_kind = 'include'
          AND sequence_depth = 0 AND included_macro_id IS NOT NULL
        """,
        (edition,),
    ).fetchall()
    grew = True
    while grew:
        grew = False
        for owner_id, macro_id in includes:
            if macro_id in found and owner_id not in found:
                found.add(owner_id)
                grew = True
    return found


def _include_note(text: str | None) -> str:
    return _INCLUDE_PREFIX_RE.sub("", text or "", count=1).strip()


def _first_attribute_tag(tables: _Tables, owner_id: str) -> str | None:
    for row in tables.rows(owner_id):
        if row.kind == "attribute":
            return row.tag
    return None


def _names_any_attribute(tables: _Tables, owner_id: str, lowered_text: str) -> bool:
    return any(
        row.kind == "attribute"
        and (
            (row.name and row.name.lower() in lowered_text)
            or (row.tag and row.tag.lower() in lowered_text)
        )
        for row in tables.rows(owner_id)
    )


# Descriptions that point elsewhere -------------------------------------------


def _pointers(tables: _Tables, uses: list[_Use], explained: set[str]) -> list[str]:
    """Rows whose description names values this answer could not list."""
    rows: dict[str, list[str]] = {}
    for use in uses:
        if use.owner_id in explained or not _VALUES_RE.search(use.description):
            continue
        owners = rows.setdefault(_shorten(use.description), [])
        if use.owner_id not in owners:
            owners.append(use.owner_id)
    return [_pipe(_places(tables, owners), text) for text, owners in rows.items()]
