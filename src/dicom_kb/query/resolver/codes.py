"""Coded terminology: context groups, templates and single codes (PS3.16)."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from dicom_kb.query.answer_contracts import StandardRef, ToolResponse
from dicom_kb.query.resolver.objects import _close_matches, _not_found, _paged, _pipe
from dicom_kb.query.resolver.standard import read_standard

_CID_RE = re.compile(r"^[BDE]?CID\s*[-_ ]?\s*(\d+)$", re.I)
_TID_RE = re.compile(r"^[BDE]?TID\s*[-_ ]?\s*(\d+)$", re.I)
# (121071, DCM, "Finding"), with or without the brackets and meaning.
_TRIPLE_RE = re.compile(
    r'^\(?\s*([^,()\s]+)\s*,\s*([^,()\s]+)\s*(?:,\s*"?([^"]*)"?\s*)?\)?$'
)
# More groups than this are counted rather than named.
_MAX_GROUPS_NAMED = 40


@dataclass(frozen=True)
class _Group:
    id: str
    cid: str
    name: str
    extensibility: str | None
    version: str | None


def code_lookup(
    connection: sqlite3.Connection,
    *,
    query: str,
    edition: str,
    scheme: str | None = None,
    page: int = 1,
) -> ToolResponse:
    """Answer for a CID, a TID, or a code value (with its scheme)."""
    text = re.sub(r"\s+", " ", query).strip()
    scheme = scheme.strip() if scheme and scheme.strip() else None
    if scheme is None:
        if match := _CID_RE.match(text):
            return _group_answer(connection, match.group(1), edition=edition, page=page)
        if match := _TID_RE.match(text):
            return _template_answer(
                connection, f"TID {match.group(1)}", edition=edition, page=page
            )
        if match := _TRIPLE_RE.match(text):
            text, scheme = match.group(1), match.group(2)
        else:
            parts = text.split(" ")
            schemes = _schemes(connection, edition)
            if len(parts) == 2 and parts[0].upper() in schemes:
                scheme, text = parts[0], parts[1]
            elif len(parts) == 2 and parts[1].upper() in schemes:
                text, scheme = parts[0], parts[1]
    if " " not in text or scheme is not None:
        answer = _code_answer(connection, text, scheme=scheme, edition=edition)
        if answer is not None:
            return answer
        if scheme is None and text.isdigit():
            return _group_answer(connection, text, edition=edition, page=page)
        if scheme is not None:
            return _not_found(
                f"No code {text} in scheme {scheme} is listed in PS3.16.", []
            )
    return _named(connection, text, edition=edition, page=page)


# Context groups ---------------------------------------------------------------


def _group_answer(
    connection: sqlite3.Connection, number: str, *, edition: str, page: int
) -> ToolResponse:
    group = _group(connection, f"CID {number}", edition=edition)
    if group is None:
        # A CID without a code table (one defined by reference) still reads.
        return read_standard(
            connection, reference=f"CID {number}", edition=edition, page=page
        )
    lines = [_group_heading(group), ""]
    lines += _group_rows(connection, group, edition=edition, listed={group.cid})
    return _paged(
        "\n".join(lines),
        page=page,
        next_call=f'dicom_code("{group.cid}", page={{page}})',
        refs=[_ref(edition, group.cid)],
    )


def _group_rows(
    connection: sqlite3.Connection,
    group: _Group,
    *,
    edition: str,
    listed: set[str],
) -> list[str]:
    """Render a group's codes, then each group it includes, each once."""
    codes = ["| Scheme | Code | Meaning |", "|---|---|---|"]
    includes: list[str] = []
    for row in connection.execute(
        """
        SELECT coding_scheme_designator, coding_scheme_version, code_value,
               code_meaning, include_cid
        FROM context_group_row
        WHERE edition_id = ? AND context_group_id = ?
        ORDER BY row_order
        """,
        (edition, group.id),
    ):
        if row["include_cid"]:
            includes.append(str(row["include_cid"]))
            continue
        scheme = row["coding_scheme_designator"] or ""
        if row["coding_scheme_version"]:
            scheme += f" [{row['coding_scheme_version']}]"
        codes.append(_pipe(scheme, row["code_value"] or "", row["code_meaning"] or ""))
    lines = codes if len(codes) > 2 else []
    if includes:
        if lines:
            lines.append("")
        lines.append(
            "Includes "
            + ", ".join(
                f"{cid} {included.name}"
                if (included := _group(connection, cid, edition=edition))
                else cid
                for cid in includes
            )
            + "."
        )
    for cid in includes:
        if cid in listed:
            continue
        listed.add(cid)
        included = _group(connection, cid, edition=edition)
        if included is None:
            continue
        lines += ["", f"**From {included.cid} {included.name}**", ""]
        lines += _group_rows(connection, included, edition=edition, listed=listed)
    return lines


def _group_heading(group: _Group) -> str:
    heading = f"**{group.cid} {group.name}**"
    if group.extensibility:
        heading += f" · {group.extensibility}"
    if group.version:
        heading += f" · Version {group.version}"
    return heading


def _group(connection: sqlite3.Connection, cid: str, *, edition: str) -> _Group | None:
    row = connection.execute(
        """
        SELECT id, cid, name, extensibility, version FROM context_group
        WHERE edition_id = ? AND cid = ?
        """,
        (edition, cid),
    ).fetchone()
    if row is None:
        return None
    return _Group(
        id=row["id"],
        cid=row["cid"],
        name=row["name"],
        extensibility=row["extensibility"],
        version=row["version"],
    )


# Templates ---------------------------------------------------------------------


def _template_answer(
    connection: sqlite3.Connection, tid: str, *, edition: str, page: int
) -> ToolResponse:
    """Read a template's section, else render the rows recorded for it."""
    answer = read_standard(connection, reference=tid, edition=edition, page=page)
    if answer.status == "ok":
        return answer
    template = connection.execute(
        """
        SELECT id, tid, name, extensibility FROM sr_template
        WHERE edition_id = ? AND tid = ?
        """,
        (edition, tid),
    ).fetchone()
    if template is None:
        return answer
    heading = f"**{template['tid']} {template['name']}**"
    if template["extensibility"]:
        heading += f" · {template['extensibility']}"
    lines = [
        heading,
        "",
        "| Rel | VT | Concept Name | VM | Condition | Includes |",
        "|---|---|---|---|---|---|",
    ]
    for row in connection.execute(
        """
        SELECT relationship_type, value_type, concept_name, cardinality,
               condition_text, include_tid
        FROM sr_template_row WHERE edition_id = ? AND sr_template_id = ?
        ORDER BY row_order
        """,
        (edition, template["id"]),
    ):
        lines.append(_pipe(*(str(cell or "") for cell in tuple(row))))
    return _paged(
        "\n".join(lines),
        page=page,
        next_call=f'dicom_code("{tid}", page={{page}})',
        refs=[_ref(edition, tid)],
    )


# Single codes -------------------------------------------------------------------


def _code_answer(
    connection: sqlite3.Connection,
    value: str,
    *,
    scheme: str | None,
    edition: str,
) -> ToolResponse | None:
    concepts = connection.execute(
        """
        SELECT code_value, coding_scheme_designator, coding_scheme_version,
               code_meaning, definition, notes
        FROM coded_concept
        WHERE edition_id = ? AND code_value = ?
          AND (? IS NULL OR lower(coding_scheme_designator) = lower(?))
        ORDER BY coding_scheme_designator, coding_scheme_version
        """,
        (edition, value, scheme, scheme),
    ).fetchall()
    if not concepts:
        return None
    return _concepts_answer(connection, concepts, edition=edition)


def _concepts_answer(
    connection: sqlite3.Connection, concepts: list[sqlite3.Row], *, edition: str
) -> ToolResponse:
    lines: list[str] = []
    refs: list[StandardRef] = []
    for concept in concepts:
        if lines:
            lines.append("")
        lines += _concept_lines(connection, concept, edition=edition)
        if concept["definition"] is not None:
            refs.append(_ref(edition, "Table D-1"))
        groups = _groups_with_code(
            connection,
            concept["code_value"],
            scheme=concept["coding_scheme_designator"],
            edition=edition,
        )
        refs += [_ref(edition, cid) for cid in groups[:3]]
    return _paged(
        "\n".join(lines),
        page=1,
        next_call="",
        refs=list(dict.fromkeys(refs)) or [_ref(edition, "")],
    )


def _concept_lines(
    connection: sqlite3.Connection, concept: sqlite3.Row, *, edition: str
) -> list[str]:
    scheme = concept["coding_scheme_designator"]
    if concept["coding_scheme_version"]:
        scheme += f" [{concept['coding_scheme_version']}]"
    lines = [f'**({concept["code_value"]}, {scheme}, "{concept["code_meaning"]}")**']
    if concept["definition"]:
        lines.append(f"Definition: {concept['definition']}")
    if concept["notes"]:
        lines.append(f"Notes: {concept['notes']}")
    direct = _groups_with_code(
        connection,
        concept["code_value"],
        scheme=concept["coding_scheme_designator"],
        edition=edition,
    )
    if not direct:
        lines.append("No context group lists it.")
        return lines
    lines.append("In " + _group_names(connection, direct, edition=edition) + ".")
    through = _including_groups(connection, direct, edition=edition)
    if through:
        lines.append(
            "Also through includes in "
            + _group_names(connection, through, edition=edition)
            + "."
        )
    return lines


def _groups_with_code(
    connection: sqlite3.Connection, value: str, *, scheme: str | None, edition: str
) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            """
            SELECT DISTINCT g.cid FROM context_group_row r
            JOIN context_group g ON g.id = r.context_group_id
            WHERE r.edition_id = ? AND r.code_value = ?
              AND (? IS NULL OR lower(r.coding_scheme_designator) = lower(?))
            ORDER BY CAST(substr(g.cid, 5) AS INTEGER)
            """,
            (edition, value, scheme, scheme),
        )
    ]


def _including_groups(
    connection: sqlite3.Connection, cids: list[str], *, edition: str
) -> list[str]:
    """Return the groups that include any of these, at any depth."""
    includers: dict[str, set[str]] = {}
    for row in connection.execute(
        """
        SELECT g.cid, r.include_cid FROM context_group_row r
        JOIN context_group g ON g.id = r.context_group_id
        WHERE r.edition_id = ? AND r.include_cid IS NOT NULL
        """,
        (edition,),
    ):
        includers.setdefault(str(row["include_cid"]), set()).add(str(row["cid"]))
    reached: set[str] = set()
    pending = list(cids)
    while pending:
        for includer in includers.get(pending.pop(), ()):
            if includer not in reached and includer not in cids:
                reached.add(includer)
                pending.append(includer)
    return sorted(reached, key=lambda cid: int(cid.split()[-1]))


def _group_names(
    connection: sqlite3.Connection, cids: list[str], *, edition: str
) -> str:
    names = dict(
        connection.execute(
            "SELECT cid, name FROM context_group WHERE edition_id = ?", (edition,)
        ).fetchall()
    )
    shown = [f"{cid} {names.get(cid, '')}".strip() for cid in cids[:_MAX_GROUPS_NAMED]]
    text = "; ".join(shown)
    if len(cids) > _MAX_GROUPS_NAMED:
        text += f"; and {len(cids) - _MAX_GROUPS_NAMED} more"
    return text


# Names --------------------------------------------------------------------------


def _named(
    connection: sqlite3.Connection, name: str, *, edition: str, page: int
) -> ToolResponse:
    """Find a group or template by name, or codes by their meaning."""
    lowered = name.lower()
    row = connection.execute(
        "SELECT cid FROM context_group WHERE edition_id = ? AND lower(name) = ?",
        (edition, lowered),
    ).fetchone()
    if row is not None:
        return _group_answer(
            connection, str(row["cid"]).split()[-1], edition=edition, page=page
        )
    row = connection.execute(
        "SELECT tid FROM sr_template WHERE edition_id = ? AND lower(name) = ?",
        (edition, lowered),
    ).fetchone()
    if row is not None:
        return _template_answer(connection, str(row["tid"]), edition=edition, page=page)
    concepts = connection.execute(
        """
        SELECT code_value, coding_scheme_designator, coding_scheme_version,
               code_meaning, definition, notes
        FROM coded_concept WHERE edition_id = ? AND lower(code_meaning) = ?
        ORDER BY coding_scheme_designator, code_value
        """,
        (edition, lowered),
    ).fetchall()
    if concepts:
        return _concepts_answer(connection, concepts, edition=edition)
    names = [
        f"{row[0]} {row[1]}"
        for row in connection.execute(
            "SELECT cid, name FROM context_group WHERE edition_id = ? "
            "UNION ALL SELECT tid, name FROM sr_template WHERE edition_id = ?",
            (edition, edition),
        )
    ]
    by_name = {entry.split(" ", 2)[-1]: entry for entry in names}
    close = _close_matches(name, by_name)
    return _not_found(
        f"No context group, template or code is named {name!r}.",
        [by_name[match] for match in close],
    )


def _schemes(connection: sqlite3.Connection, edition: str) -> set[str]:
    return {
        str(row[0]).upper()
        for row in connection.execute(
            "SELECT DISTINCT coding_scheme_designator FROM coded_concept "
            "WHERE edition_id = ?",
            (edition,),
        )
    }


def _ref(edition: str, label: str) -> StandardRef:
    anchor = None
    if label.startswith(("CID ", "TID ")):
        anchor = "sect_" + label.replace(" ", "_")
    elif label.startswith("Table "):
        anchor = "table_" + label.removeprefix("Table ")
    return StandardRef(
        part="PS3.16",
        anchor=anchor,
        edition=edition,
        label=f"PS3.16 {label}".strip(),
    )
