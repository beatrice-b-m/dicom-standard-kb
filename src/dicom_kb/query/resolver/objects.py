"""What an object needs: IODs, their modules, and the attributes in them."""

from __future__ import annotations

import difflib
import re
import sqlite3
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field

from dicom_kb.db.repositories import DataElementRepository
from dicom_kb.ir.models import DataElement
from dicom_kb.query.answer_contracts import StandardRef, ToolResponse, tool_response
from dicom_kb.query.resolver.standard import paginate

# More IODs than this are counted rather than named.
_MAX_IODS_NAMED = 25
_TABLE_RE = re.compile(r"^(?:PS3\.3\s+)?(?:Table\s+)?([A-Z]?\d[\w.]*-\w+)$", re.I)
_UID_RE = re.compile(r"^\d+(?:\.\d+)+$")
# Types a `type="required"` filter keeps.
_REQUIRED_TYPES = ("1", "1C", "2", "2C")
_TYPES = ("1", "1C", "2", "2C", "3")
_USAGES = ("M", "C", "U")
# Optional sequences named before the rest are counted.
_MAX_SEQUENCES_NAMED = 5
_SENTENCE_RE = re.compile(r"(?<=[.:])\s+(?=[A-Z])")
# Sentences of a conditional attribute that state when it is present.
_CONDITION_RE = re.compile(
    r"^(?:Required|Shall|May (?:only )?be present|Should be present|"
    r"Not required|Only (?:required|present)|Otherwise|If required|Either|"
    r"Mutually exclusive|It shall not)",
    re.I,
)


@dataclass(frozen=True)
class _Row:
    """One row of a module or macro table, joined to its PS3.6 entry."""

    kind: str  # attribute, include or text
    depth: int
    name: str
    tag: str | None
    keyword: str | None
    vr: str | None
    vm: str | None
    type: str | None
    description: str | None
    macro_id: str | None
    include_text: str | None


@dataclass(frozen=True)
class _Line:
    """A row placed in an expanded table: its nesting and how it got there."""

    row: _Row
    depth: int
    # The macros it came through, outermost first.
    via: tuple[str, ...] = ()
    # An include whose macro is already listed earlier in this answer.
    repeated: bool = False
    # An include shown as one line, its macro not expanded.
    collapsed: bool = False


@dataclass(frozen=True)
class _Owner:
    """A module or macro: what holds attribute rows."""

    id: str
    name: str
    kind: str  # module or macro
    section: str | None
    table: str | None

    @property
    def label(self) -> str:
        """`General Series Module`, or `Code Sequence Macro`."""
        return self.name if self.kind == "macro" else f"{self.name} Module"

    @property
    def locator(self) -> str:
        """`C.7.3.1, Table C.7-5a`, or just the table for a macro."""
        parts = []
        if self.kind == "module" and self.section:
            parts.append(_xml_id_label(self.section))
        if self.table:
            parts.append(_xml_id_label(self.table))
        return ", ".join(part for part in parts if part)


@dataclass(frozen=True)
class _IOD:
    id: str
    name: str
    table: str | None
    section: str | None


class _Tables:
    """Reads module and macro tables once per answer."""

    def __init__(self, connection: sqlite3.Connection, edition: str) -> None:
        self.connection = connection
        self.edition = edition
        self._rows: dict[str, list[_Row]] = {}
        self._owners: dict[str, _Owner] | None = None

    def rows(self, owner_id: str) -> list[_Row]:
        if owner_id not in self._rows:
            self._rows[owner_id] = [
                _Row(
                    kind=str(row["row_kind"]),
                    depth=int(row["sequence_depth"]),
                    name=str(row["attribute_name"] or ""),
                    tag=row["attribute_tag"],
                    keyword=row["keyword"],
                    vr=row["vr"],
                    vm=row["vm"],
                    type=row["type_designation"],
                    description=row["description_text"],
                    macro_id=row["included_macro_id"],
                    include_text=row["include_target_text"],
                )
                for row in self.connection.execute(
                    """
                    SELECT a.row_kind, a.sequence_depth, a.attribute_name,
                           a.attribute_tag, a.type_designation, a.description_text,
                           a.included_macro_id, a.include_target_text,
                           d.keyword, d.vr, d.vm
                    FROM attribute_use a
                    LEFT JOIN data_element d
                      ON d.edition_id = a.edition_id AND d.tag = a.attribute_tag
                    WHERE a.edition_id = ? AND a.owner_id = ?
                    ORDER BY a.row_order
                    """,
                    (self.edition, owner_id),
                )
            ]
        return self._rows[owner_id]

    def owners(self) -> dict[str, _Owner]:
        if self._owners is None:
            owners: dict[str, _Owner] = {}
            with_rows = {
                str(row[0])
                for row in self.connection.execute(
                    "SELECT DISTINCT owner_id FROM attribute_use WHERE edition_id = ?",
                    (self.edition,),
                )
            }
            for row in self.connection.execute(
                """
                SELECT m.id, m.name, m.section, sr.table_id
                FROM module m JOIN source_ref sr ON sr.id = m.source_ref_id
                WHERE m.edition_id = ?
                """,
                (self.edition,),
            ):
                owners[row["id"]] = _Owner(
                    id=row["id"],
                    name=row["name"],
                    kind="module",
                    section=row["section"],
                    # A module only an IOD names has no table of its own.
                    table=row["table_id"] if row["id"] in with_rows else None,
                )
            for row in self.connection.execute(
                "SELECT id, name, table_id FROM macro WHERE edition_id = ?",
                (self.edition,),
            ):
                owners[row["id"]] = _Owner(
                    id=row["id"],
                    name=row["name"],
                    kind="macro",
                    section=None,
                    table=row["table_id"],
                )
            self._owners = owners
        return self._owners

    def owner(self, owner_id: str) -> _Owner | None:
        return self.owners().get(owner_id)

    def attribute_count(self, owner_id: str) -> int:
        """Attributes an owner holds, its macros expanded once."""
        return sum(
            1
            for line in self.expand(owner_id, listed={owner_id})
            if line.row.kind == "attribute"
        )

    def expand(
        self,
        owner_id: str,
        *,
        listed: set[str] | None = None,
        depth: int = 0,
        via: tuple[str, ...] = (),
        skip: Callable[[], bool] | None = None,
    ) -> Iterator[_Line]:
        """Yield an owner's rows with every included macro's rows in place.

        With `listed`, each macro is expanded only the first time it appears
        and later includes of it are marked repeated. Without it every include
        is expanded, so each row carries its full nesting. `skip` is asked
        after an include is yielded, so the caller has seen it; when it
        answers true, that include is neither expanded nor counted as listed.
        """
        for row in self.rows(owner_id):
            line_depth = row.depth + depth
            macro_id = row.macro_id
            if row.kind != "include" or macro_id is None:
                yield _Line(row=row, depth=line_depth, via=via)
                continue
            # A macro that includes itself, directly or not, stops here.
            repeated = (listed is not None and macro_id in listed) or macro_id in {
                *via,
                owner_id,
            }
            yield _Line(row=row, depth=line_depth, via=via, repeated=repeated)
            if repeated or (skip is not None and skip()):
                continue
            if listed is not None:
                listed.add(macro_id)
            yield from self.expand(
                macro_id,
                listed=listed,
                depth=line_depth,
                via=(*via, macro_id),
                skip=skip,
            )


# dicom_module ---------------------------------------------------------------


def module_attributes(
    connection: sqlite3.Connection,
    *,
    name: str,
    edition: str,
    detail: str = "outline",
    types: str | None = None,
    page: int = 1,
) -> ToolResponse:
    """Return a module's or macro's attributes.

    The outline lists the module's own rows, each macro as one line, and
    descriptions cut to their first sentence and condition. `detail="full"`
    expands every macro in place with full descriptions. `types` keeps the
    attributes of those Types whose enclosing sequences are of those Types
    too, with macros expanded.
    """
    if detail not in {"outline", "full"}:
        return _invalid("detail is 'outline' or 'full'.")
    kept_types = _parse_types(types)
    if isinstance(kept_types, ToolResponse):
        return kept_types
    tables = _Tables(connection, edition)
    owner = _find_owner(tables, name)
    if owner is None:
        return _not_found(
            f"No module or macro is named {name!r}.",
            _close_matches(name, (owner.label for owner in tables.owners().values())),
        )
    descriptions = "all" if detail == "full" else "summary"
    notes: list[str] = []
    if kept_types is not None:
        lines, omitted = _keep_types(
            tables, owner.id, kept_types, listed={owner.id}, shown=set()
        )
        notes.append(omitted.note(kept_types))
    elif detail == "full":
        lines = list(tables.expand(owner.id, listed={owner.id}))
    else:
        lines = [
            _Line(row=row, depth=row.depth, collapsed=row.kind == "include")
            for row in tables.rows(owner.id)
        ]
        macros = sum(1 for line in lines if line.row.kind == "include")
        if macros:
            notes.append(
                f"{macros} macro include{'s' if macros != 1 else ''} not expanded; "
                'open one with dicom_module("<macro>").'
            )
    if descriptions == "summary":
        notes.append(
            "Descriptions cut to their first sentence and condition. Everything: "
            + _call("dicom_module", name, detail="full", type=types)
            + "."
        )
    body = "\n".join(
        [
            f"**{owner.label}** ({owner.locator})",
            "",
            *(
                _attribute_table(tables, lines, descriptions=descriptions)
                or ["No attributes."]
            ),
            *(["", " ".join(note for note in notes if note)] if notes else []),
        ]
    )
    return _paged(
        body,
        page=page,
        next_call=_call(
            "dicom_module",
            name,
            detail=None if detail == "outline" else detail,
            type=types,
            page="{page}",
        ),
        refs=[_ref(edition, owner.table or owner.section)],
    )


# dicom_iod ------------------------------------------------------------------


def iod_modules(
    connection: sqlite3.Connection,
    *,
    name: str,
    edition: str,
    expand: bool = False,
    types: str | None = None,
    usage: str | None = None,
    module: str | None = None,
    page: int = 1,
) -> ToolResponse:
    """Return an IOD's modules, or with `expand` the attributes it needs.

    The checklist covers M and C modules unless `usage` says otherwise, or
    only the modules `module` names. `types` keeps the attributes of those
    Types whose enclosing sequences are of those Types too. Passing any of
    these filters implies `expand`.
    """
    kept_types = _parse_types(types)
    if isinstance(kept_types, ToolResponse):
        return kept_types
    usages = _parse_usage(usage)
    if isinstance(usages, ToolResponse):
        return usages
    found = _find_iod(connection, name, edition=edition)
    if found is None:
        return _not_found(
            f"No IOD or SOP Class is named {name!r}.",
            _close_matches(name, _iod_and_sop_class_names(connection, edition)),
        )
    iod = found
    tables = _Tables(connection, edition)
    module_uses = _module_uses(connection, iod.id, edition=edition)
    group_uses = _functional_group_uses(connection, iod.id, edition=edition)

    heading = f"**{iod.name} IOD**"
    sop_classes = _sop_classes_for_iod(connection, iod.id, edition=edition)
    lines = [heading]
    if sop_classes:
        lines.append(
            "SOP Class: "
            + "; ".join(f"{sop_name} `{uid}`" for sop_name, uid in sop_classes)
        )

    if not (expand or types or usage or module):
        lines += ["", "| IE | Module | Reference | Usage |", "|---|---|---|---|"]
        last_ie = None
        for use in module_uses:
            owner = tables.owner(use.module_id)
            ie = use.information_entity or ""
            if use.information_entity == last_ie:
                ie = ""
            last_ie = use.information_entity
            lines.append(
                _pipe(
                    ie,
                    owner.name if owner else use.module_id,
                    owner.locator if owner else "",
                    use.usage_text,
                )
            )
        if group_uses:
            lines += [
                "",
                "Functional group macros (each sits in the Shared or Per-Frame "
                "Functional Groups Sequence):",
                "",
                "| Macro | Reference | Usage |",
                "|---|---|---|",
                *(
                    _pipe(owner.name, owner.locator, use.usage_text)
                    for use in group_uses
                    if (owner := tables.owner(use.module_id)) is not None
                ),
            ]
        every = _call("dicom_iod", iod.name, expand=True)
        required = _call("dicom_iod", iod.name, type="required")
        lines += [
            "",
            f"Attributes of the M and C modules: {every}; only the required "
            f'ones: {required}. One module: dicom_module("<module>").',
        ]
        return tool_response(
            status="ok",
            result={"markdown": "\n".join(lines)},
            refs=[_ref(edition, iod.table)],
        )

    if module is not None:
        wanted = _named_uses(tables, [*module_uses, *group_uses], module)
        if isinstance(wanted, ToolResponse):
            return wanted
        selected = wanted
    else:
        selected = {
            use.module_id for use in [*module_uses, *group_uses] if use.usage in usages
        }

    lines += [
        "",
        "Macros expanded in place, each listed once. Conditional attributes "
        "show their condition; dicom_module has the full descriptions.",
    ]
    listed: set[str] = set()
    shown: set[str] = set()
    omitted = _Omitted()
    for title, uses in (("", module_uses), ("## Functional group macros", group_uses)):
        uses = [use for use in uses if use.module_id in selected]
        if title and uses:
            lines += [
                "",
                title,
                "",
                "Each one sits in the Shared or Per-Frame Functional Groups Sequence.",
            ]
        for use in uses:
            owner = tables.owner(use.module_id)
            if owner is None:
                continue
            lines += ["", f"### {owner.label}: {use.usage_text} ({owner.locator})", ""]
            # Under a Type filter a macro listed earlier may have shown no rows.
            if owner.id in listed and (kept_types is None or owner.id in shown):
                lines.append("Listed above.")
                continue
            listed.add(owner.id)
            if kept_types is not None:
                rows, module_omitted = _keep_types(
                    tables, owner.id, kept_types, listed=listed, shown=shown
                )
                omitted.add(module_omitted)
            else:
                rows = list(tables.expand(owner.id, listed=listed))
            lines += _attribute_table(tables, rows, descriptions="condition") or [
                "No attributes." if kept_types is None else "None of those Types."
            ]

    notes = []
    if kept_types is not None:
        notes.append(omitted.note(kept_types))
    if module is None:
        left_out = [
            (owner.name, use.usage)
            for use in [*module_uses, *group_uses]
            if use.module_id not in selected
            and (owner := tables.owner(use.module_id)) is not None
        ]
        if left_out:
            names = ", ".join(f"{label} ({use})" for label, use in left_out)
            notes.append(
                f"Modules not shown: {names}. Add them with "
                f'usage="{",".join([*usages, *sorted({u for _, u in left_out})])}"'
                ', or name one with module="<module>".'
            )
    if notes:
        lines += ["", " ".join(notes)]
    return _paged(
        "\n".join(lines),
        page=page,
        next_call=_call(
            "dicom_iod",
            iod.name,
            expand=True,
            type=types,
            usage=usage,
            module=module,
            page="{page}",
        ),
        refs=[_ref(edition, iod.table)],
    )


# Filters ---------------------------------------------------------------------


@dataclass
class _Omitted:
    """What a Type filter left out, for the line that says so."""

    other_types: int = 0
    # Attributes of the kept Types inside a sequence that is not, by the
    # outermost such sequence.
    nested: dict[str, int] = field(default_factory=dict)

    def add(self, other: _Omitted) -> None:
        self.other_types += other.other_types
        for sequence, count in other.nested.items():
            self.nested[sequence] = self.nested.get(sequence, 0) + count

    def note(self, types: tuple[str, ...]) -> str:
        kept = "/".join(types)
        parts = [f"Kept Type {kept}, in sequences of those Types."]
        if self.other_types:
            parts.append(f"Not shown: {self.other_types} attributes of other Types.")
        if self.nested:
            ranked = sorted(self.nested.items(), key=lambda item: -item[1])
            named = ", ".join(
                f"{sequence} ({count})"
                for sequence, count in ranked[:_MAX_SEQUENCES_NAMED]
            )
            more = len(ranked) - _MAX_SEQUENCES_NAMED
            if more > 0:
                named += f" and {more} more"
            parts.append(
                f"{sum(self.nested.values())} Type {kept} attributes sit inside "
                f"sequences of other Types: {named}."
            )
        return " ".join(parts)


def _keep_types(
    tables: _Tables,
    owner_id: str,
    types: tuple[str, ...],
    *,
    listed: set[str],
    shown: set[str],
) -> tuple[list[_Line], _Omitted]:
    """Expand an owner, keeping attributes of `types` in sequences of `types`.

    A macro inside a sequence that is left out is not expanded, so it stays
    unlisted for a later include. `shown` collects the macros that kept a
    row; a later include of one stays as "listed above", other includes stay
    when something they brought in stays.
    """
    omitted = _Omitted()
    lines: list[_Line] = []
    keep: list[bool] = []
    # (depth, name, kept) for each attribute enclosing the current line.
    stack: list[tuple[int, str, bool]] = []
    blocker: str | None = None

    def blocked() -> bool:
        return blocker is not None

    for line in tables.expand(owner_id, listed=listed, skip=blocked):
        while stack and stack[-1][0] >= line.depth:
            stack.pop()
        blocker = next((name for _, name, kept in stack if not kept), None)
        row = line.row
        lines.append(line)
        keep.append(False)
        if row.kind == "include":
            if blocker is not None and row.macro_id is not None:
                count = sum(
                    1
                    for inner in tables.expand(row.macro_id, listed={row.macro_id})
                    if inner.row.kind == "attribute" and (inner.row.type or "") in types
                )
                if count:
                    omitted.nested[blocker] = omitted.nested.get(blocker, 0) + count
            continue
        if row.kind != "attribute":
            continue
        matches = (row.type or "") in types
        if blocker is None and matches:
            keep[-1] = True
            shown.update(line.via)
        elif blocker is None:
            omitted.other_types += 1
        elif matches:
            omitted.nested[blocker] = omitted.nested.get(blocker, 0) + 1
        stack.append((line.depth, row.keyword or row.name, blocker is None and matches))
    for index, line in enumerate(lines):
        macro_id = line.row.macro_id
        if line.row.kind != "include" or macro_id is None:
            continue
        if line.repeated:
            keep[index] = macro_id in shown and _encloser_kept(lines, keep, index)
            continue
        # Its own rows follow it, carrying it at the end of their path.
        inside = (*line.via, macro_id)
        later = index + 1
        while later < len(lines) and lines[later].via[: len(inside)] == inside:
            if keep[later]:
                keep[index] = True
                break
            later += 1
    return [line for index, line in enumerate(lines) if keep[index]], omitted


def _encloser_kept(lines: list[_Line], keep: list[bool], index: int) -> bool:
    """Whether the attribute enclosing an include row is kept (or none is)."""
    depth = lines[index].depth
    for earlier in range(index - 1, -1, -1):
        line = lines[earlier]
        if line.row.kind == "attribute" and line.depth < depth:
            return keep[earlier]
    return True


def _parse_types(value: str | None) -> tuple[str, ...] | ToolResponse | None:
    if value is None or not value.strip():
        return None
    if value.strip().lower() == "required":
        return _REQUIRED_TYPES
    wanted = {part.upper() for part in re.split(r"[\s,/]+", value.strip()) if part}
    unknown = sorted(wanted - set(_TYPES))
    if unknown:
        return _invalid(
            f"Unknown Type {', '.join(unknown)}. Use 1, 1C, 2, 2C, 3 or 'required'."
        )
    return tuple(type_ for type_ in _TYPES if type_ in wanted)


def _parse_usage(value: str | None) -> tuple[str, ...] | ToolResponse:
    if value is None or not value.strip():
        return ("M", "C")
    wanted = {part.upper() for part in re.split(r"[\s,/]+", value.strip()) if part}
    unknown = sorted(wanted - set(_USAGES))
    if unknown:
        return _invalid(f"Unknown usage {', '.join(unknown)}. Use M, C or U.")
    return tuple(usage for usage in _USAGES if usage in wanted)


def _named_uses(
    tables: _Tables, uses: list[_Use], names: str
) -> set[str] | ToolResponse:
    """Module ids of the IOD's uses that `names` (comma-separated) picks."""
    by_id = {
        use.module_id: owner
        for use in uses
        if (owner := tables.owner(use.module_id)) is not None
    }
    selected: set[str] = set()
    for name in (part.strip() for part in names.split(",")):
        if not name:
            continue
        owner = _find_owner(tables, name)
        if owner is None or owner.id not in by_id:
            return _not_found(
                f"The IOD has no module or functional group macro named {name!r}.",
                _close_matches(name, (owner.label for owner in by_id.values())),
            )
        selected.add(owner.id)
    return selected


# dicom_element --------------------------------------------------------------


def element_usage(
    connection: sqlite3.Connection,
    *,
    name: str,
    edition: str,
    iod: str | None = None,
) -> ToolResponse:
    """Return a data element's dictionary entry and where PS3.3 uses it."""
    element, _ = DataElementRepository(connection).find_by_tag_or_keyword(
        name.strip(), edition=edition
    )
    if element is None:
        return _not_found(
            f"No data element is named {name!r}.",
            _close_matches(name, _element_names(connection, edition)),
        )
    lines = [_element_heading(element)]
    tables = _Tables(connection, edition)
    if iod is not None:
        found = _find_iod(connection, iod, edition=edition)
        if found is None:
            return _not_found(
                f"No IOD or SOP Class is named {iod!r}.",
                _close_matches(iod, _iod_and_sop_class_names(connection, edition)),
            )
        iod_record = found
        lines += ["", *_uses_in_iod(connection, tables, element, iod_record)]
        refs = [
            _ref(edition, element.source_ref.table_id, part="PS3.6"),
            _ref(edition, iod_record.table),
        ]
    else:
        lines += _uses_everywhere(connection, tables, element, edition=edition)
        refs = [_ref(edition, element.source_ref.table_id, part="PS3.6")]
    return tool_response(status="ok", result={"markdown": "\n".join(lines)}, refs=refs)


def _element_heading(element: DataElement) -> str:
    retired = " (retired)" if element.retired else ""
    keyword = f" `{element.keyword}`" if element.keyword else ""
    return (
        f"**{element.tag} {element.name}**{keyword} · VR {element.vr or '-'}"
        f" · VM {element.vm or '-'}{retired}"
    )


def _uses_everywhere(
    connection: sqlite3.Connection,
    tables: _Tables,
    element: DataElement,
    *,
    edition: str,
) -> list[str]:
    uses = list(
        connection.execute(
            """
            SELECT owner_id, type_designation, parent_attribute_use_id
            FROM attribute_use
            WHERE edition_id = ? AND row_kind = 'attribute' AND attribute_tag = ?
            ORDER BY owner_type DESC, owner_id, row_order
            """,
            (edition, element.tag),
        )
    )
    if not uses:
        return ["", "No PS3.3 module or macro lists it."]
    rows = []
    owner_ids: list[str] = []
    for use in uses:
        owner = tables.owner(use["owner_id"])
        if owner is None:
            continue
        owner_ids.append(owner.id)
        rows.append(
            _pipe(
                owner.label,
                owner.locator,
                use["type_designation"] or "",
                " > ".join(_parent_path(connection, use["parent_attribute_use_id"])),
            )
        )
    lines = [
        "",
        "| Used in | Reference | Type | Within |",
        "|---|---|---|---|",
        *rows,
    ]
    iods = _iods_using(connection, owner_ids, edition=edition)
    if iods:
        lines.append("")
        if len(iods) > _MAX_IODS_NAMED:
            lines.append(
                f"In {len(iods)} IODs. For its Type and conditions in one: "
                f'dicom_element("{element.keyword or element.tag}", iod="<IOD>").'
            )
        else:
            lines.append(f"In IODs: {', '.join(iods)}.")
    return lines


def _uses_in_iod(
    connection: sqlite3.Connection,
    tables: _Tables,
    element: DataElement,
    iod: _IOD,
) -> list[str]:
    rows: list[str] = []
    contexts = [
        (use, f"{owner.label}", "module")
        for use in _module_uses(connection, iod.id, edition=tables.edition)
        if (owner := tables.owner(use.module_id)) is not None
    ] + [
        (use, f"{owner.label} (functional group)", "group")
        for use in _functional_group_uses(connection, iod.id, edition=tables.edition)
        if (owner := tables.owner(use.module_id)) is not None
    ]
    for use, label, _ in contexts:
        path: dict[int, str] = {}
        for line in tables.expand(use.module_id):
            row = line.row
            if row.kind != "attribute":
                continue
            path[line.depth] = row.keyword or row.name
            for deeper in [depth for depth in path if depth > line.depth]:
                del path[deeper]
            if row.tag != element.tag:
                continue
            within = " > ".join(path[depth] for depth in sorted(path)[:-1])
            via = " > ".join(
                owner.name for macro in line.via if (owner := tables.owner(macro))
            )
            rows.append(
                _pipe(
                    label,
                    use.usage_text,
                    row.type or "",
                    within,
                    via,
                    row.description or "",
                )
            )
    if not rows:
        return [f"The {iod.name} IOD does not use it."]
    return [
        f"In the {iod.name} IOD:",
        "",
        "| Module | Module usage | Type | Within | Via macro | Description |",
        "|---|---|---|---|---|---|",
        *rows,
    ]


def _parent_path(connection: sqlite3.Connection, parent_id: str | None) -> list[str]:
    path: list[str] = []
    while parent_id is not None:
        row = connection.execute(
            """
            SELECT a.attribute_name, a.parent_attribute_use_id, d.keyword
            FROM attribute_use a
            LEFT JOIN data_element d
              ON d.edition_id = a.edition_id AND d.tag = a.attribute_tag
            WHERE a.id = ?
            """,
            (parent_id,),
        ).fetchone()
        if row is None:
            break
        path.insert(0, row["keyword"] or row["attribute_name"])
        parent_id = row["parent_attribute_use_id"]
    return path


def _iods_using(
    connection: sqlite3.Connection, owner_ids: Iterable[str], *, edition: str
) -> list[str]:
    """Name every IOD whose modules or functional groups reach these owners."""
    includers: dict[str, set[str]] = {}
    for row in connection.execute(
        """
        SELECT owner_id, included_macro_id FROM attribute_use
        WHERE edition_id = ? AND row_kind = 'include'
          AND included_macro_id IS NOT NULL
        """,
        (edition,),
    ):
        includers.setdefault(row["included_macro_id"], set()).add(row["owner_id"])
    reached = set(owner_ids)
    pending = list(reached)
    while pending:
        for includer in includers.get(pending.pop(), ()):
            if includer not in reached:
                reached.add(includer)
                pending.append(includer)
    marks = ",".join("?" for _ in reached)
    rows = connection.execute(
        f"""
        SELECT DISTINCT i.name FROM iod i
        WHERE i.edition_id = ? AND i.id IN (
          SELECT iod_id FROM iod_module_use WHERE module_id IN ({marks})
          UNION
          SELECT iod_id FROM iod_functional_group_use WHERE macro_id IN ({marks})
        )
        ORDER BY i.name
        """,
        (edition, *reached, *reached),
    )
    return [str(row["name"]) for row in rows]


# Shared rendering -------------------------------------------------------------


def _attribute_table(
    tables: _Tables, lines: list[_Line], *, descriptions: str
) -> list[str]:
    """Render rows as `| Attribute | Tag | VR | VM | Type | Description |`.

    `descriptions` is `all`, `summary` (first sentence, plus the condition of
    a conditional attribute) or `condition` (a conditional attribute's
    condition only).
    """
    if not lines:
        return []
    out = [
        "| Attribute | Tag | VR | VM | Type | Description |",
        "|---|---|---|---|---|---|",
    ]
    for line in lines:
        row = line.row
        nesting = ">" * line.depth
        if row.kind == "include":
            text = _include_text(tables, row)
            if line.repeated:
                text += " (listed above)"
            elif line.collapsed and row.macro_id is not None:
                count = tables.attribute_count(row.macro_id)
                text += f" ({count} attribute{'s' if count != 1 else ''})"
            # Trailing empty cells may be left out of a pipe-table row.
            out.append(_pipe(f"{nesting}{text}"))
        elif row.kind == "text" and row.description:
            out.append(_pipe(f"{nesting}*{row.name}*", "", "", "", "", row.description))
        elif row.kind == "text":
            out.append(_pipe(f"{nesting}*{row.name}*"))
        else:
            out.append(
                _pipe(
                    f"{nesting}{row.keyword or row.name}",
                    row.tag or "",
                    row.vr or "",
                    row.vm or "",
                    row.type or "",
                    _description(row, descriptions),
                )
            )
    return out


def _description(row: _Row, mode: str) -> str:
    text = row.description or ""
    if mode == "all" or not text:
        return text
    conditional = row.type is not None and row.type.endswith("C")
    sentences = [
        sentence.strip()
        for paragraph in re.split(r"<br>|\n", text)
        for sentence in _SENTENCE_RE.split(paragraph)
        if sentence.strip()
    ]
    condition = [s for s in sentences if _CONDITION_RE.match(s)] if conditional else []
    # A condition worded some other way keeps the whole description.
    if conditional and not condition:
        return text
    if mode == "condition":
        return " ".join(condition)
    first = sentences[0] if sentences else ""
    return " ".join([first, *(s for s in condition if s != first)])


def _include_text(tables: _Tables, row: _Row) -> str:
    text = (row.include_text or row.name or "Include").lstrip(">").strip()
    owner = tables.owner(row.macro_id) if row.macro_id else None
    # Some includes name only the table; say which macro it is.
    if owner is not None and owner.name.lower() not in text.lower():
        text += f" ({owner.name})"
    return text


def _pipe(*cells: str) -> str:
    return (
        "| "
        + " | ".join(cell.replace("|", "\\|").replace("\n", "<br>") for cell in cells)
        + " |"
    )


def _paged(
    body: str, *, page: int, next_call: str, refs: list[StandardRef]
) -> ToolResponse:
    if page < 1:
        return tool_response(
            status="validation_error", result={"message": "page starts at 1."}
        )
    pages = paginate(body)
    if page > len(pages):
        return tool_response(
            status="validation_error",
            result={
                "message": f"There {'is' if len(pages) == 1 else 'are'} "
                f"{len(pages)} page{'s' if len(pages) != 1 else ''}."
            },
        )
    text = pages[page - 1]
    if len(pages) > 1:
        text += f"\n\nPage {page} of {len(pages)}."
        if page < len(pages):
            text += " Next: " + next_call.format(page=page + 1) + "."
    return tool_response(status="ok", result={"markdown": text}, refs=refs)


def _not_found(message: str, candidates: list[str]) -> ToolResponse:
    if candidates:
        message += " Closest: " + "; ".join(candidates) + "."
    return tool_response(status="not_found", result={"message": message})


def _invalid(message: str) -> ToolResponse:
    return tool_response(status="validation_error", result={"message": message})


def _call(tool: str, name: str, **arguments: object) -> str:
    """`dicom_iod("CT Image", type="required")`, leaving out unset arguments."""
    parts = [f'"{name}"']
    for key, value in arguments.items():
        if value is None or value is False:
            continue
        if value is True:
            parts.append(f"{key}=true")
        elif value == "{page}":
            parts.append(f"{key}={{page}}")
        else:
            parts.append(f'{key}="{value}"')
    return f"{tool}({', '.join(parts)})"


def _close_matches(query: str, names: Iterable[str]) -> list[str]:
    choices = {name.lower(): name for name in names if name}
    needle = query.strip().lower()
    contained = [name for key, name in choices.items() if needle and needle in key]
    if 0 < len(contained) <= 8:
        return sorted(contained, key=len)
    close = difflib.get_close_matches(needle, list(choices), n=5, cutoff=0.6)
    return [choices[key] for key in close] or sorted(contained, key=len)[:8]


def _ref(edition: str, xml_id: str | None, *, part: str = "PS3.3") -> StandardRef:
    label = _xml_id_label(xml_id)
    return StandardRef(
        part=part,
        anchor=xml_id,
        edition=edition,
        label=f"{part} {label}" if label else part,
    )


def _xml_id_label(xml_id: str | None) -> str:
    if not xml_id:
        return ""
    if xml_id.startswith("table_"):
        return "Table " + xml_id.removeprefix("table_")
    if xml_id.startswith("sect_"):
        return xml_id.removeprefix("sect_")
    return xml_id


# Lookups --------------------------------------------------------------------


@dataclass(frozen=True)
class _Use:
    module_id: str
    information_entity: str | None
    usage: str
    condition: str | None

    @property
    def usage_text(self) -> str:
        return f"{self.usage}: {self.condition}" if self.condition else self.usage


def _module_uses(
    connection: sqlite3.Connection, iod_id: str, *, edition: str
) -> list[_Use]:
    return [
        _Use(
            module_id=row["module_id"],
            information_entity=row["information_entity"],
            usage=row["usage"],
            condition=row["usage_condition_text"],
        )
        for row in connection.execute(
            """
            SELECT module_id, information_entity, usage, usage_condition_text
            FROM iod_module_use WHERE edition_id = ? AND iod_id = ?
            ORDER BY rowid
            """,
            (edition, iod_id),
        )
    ]


def _functional_group_uses(
    connection: sqlite3.Connection, iod_id: str, *, edition: str
) -> list[_Use]:
    return [
        _Use(
            module_id=row["macro_id"],
            information_entity=None,
            usage=row["usage"],
            condition=row["usage_condition_text"],
        )
        for row in connection.execute(
            """
            SELECT macro_id, usage, usage_condition_text
            FROM iod_functional_group_use WHERE edition_id = ? AND iod_id = ?
            ORDER BY rowid
            """,
            (edition, iod_id),
        )
    ]


def _find_owner(tables: _Tables, name: str) -> _Owner | None:
    query = re.sub(r"\s+", " ", name).strip()
    table = _TABLE_RE.match(query)
    owners = tables.owners().values()
    if table:
        table_id = f"table_{table.group(1)}".lower()
        for owner in owners:
            if owner.table and owner.table.lower() == table_id:
                return owner
    lowered = query.lower()
    for suffix in (" module attributes", " macro attributes", " attributes", " module"):
        lowered = lowered.removesuffix(suffix)
    for owner in owners:
        if owner.name.lower() in {lowered, f"{lowered} macro"}:
            return owner
    if lowered.startswith("sect_") or re.match(r"^[a-z]\.\d", lowered):
        section = lowered if lowered.startswith("sect_") else f"sect_{lowered}"
        for owner in owners:
            if owner.section and owner.section.lower() == section:
                return owner
    return None


def _find_iod(
    connection: sqlite3.Connection, name: str, *, edition: str
) -> _IOD | None:
    """Find an IOD by its name, or by a SOP Class name, UID or keyword."""
    query = re.sub(r"\s+", " ", name).strip()
    iod_name = re.sub(r"\s+IOD$", "", query, flags=re.I)
    row = connection.execute(
        """
        SELECT i.id, i.name, i.section, sr.section AS parent
        FROM iod i JOIN source_ref sr ON sr.id = i.source_ref_id
        WHERE i.edition_id = ? AND (lower(i.name) = lower(?) OR i.keyword = lower(?))
        """,
        (edition, iod_name, iod_name),
    ).fetchone()
    if row is not None:
        return _iod(row)
    uid = query
    if not _UID_RE.match(query):
        keyword_row = connection.execute(
            """
            SELECT uid_value FROM uid_registry_entry
            WHERE edition_id = ? AND lower(uid_keyword) = lower(?)
            """,
            (edition, query),
        ).fetchone()
        uid = keyword_row["uid_value"] if keyword_row else ""
    row = connection.execute(
        """
        SELECT i.id, i.name, i.section, sr.section AS parent, s.name AS sop_name
        FROM sop_class s
        JOIN sop_class_iod e ON e.sop_class_id = s.id
        JOIN iod i ON i.id = e.iod_id
        JOIN source_ref sr ON sr.id = i.source_ref_id
        WHERE s.edition_id = ? AND (s.uid_value = ? OR lower(s.name) = lower(?))
        """,
        (edition, uid, query),
    ).fetchone()
    return _iod(row) if row is not None else None


def _iod(row: sqlite3.Row) -> _IOD:
    return _IOD(
        id=row["id"], name=row["name"], table=row["section"], section=row["parent"]
    )


def _sop_classes_for_iod(
    connection: sqlite3.Connection, iod_id: str, *, edition: str
) -> list[tuple[str, str]]:
    return [
        (str(row["name"]), str(row["uid_value"]))
        for row in connection.execute(
            """
            SELECT DISTINCT s.name, s.uid_value FROM sop_class s
            JOIN sop_class_iod e ON e.sop_class_id = s.id
            WHERE s.edition_id = ? AND e.iod_id = ?
            ORDER BY s.name
            """,
            (edition, iod_id),
        )
    ]


def _iod_and_sop_class_names(connection: sqlite3.Connection, edition: str) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM iod WHERE edition_id = ? "
            "UNION SELECT name FROM sop_class WHERE edition_id = ?",
            (edition, edition),
        )
    ]


def _element_names(connection: sqlite3.Connection, edition: str) -> list[str]:
    names: list[str] = []
    for row in connection.execute(
        "SELECT name, keyword FROM data_element WHERE edition_id = ?", (edition,)
    ):
        names.append(str(row["name"]))
        if row["keyword"]:
            names.append(str(row["keyword"]))
    return names
