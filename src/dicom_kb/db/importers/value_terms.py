"""Enumerated value and defined term extraction and persistence."""

from __future__ import annotations

import re
import sqlite3

from dicom_kb.db.importers._shared import ImportConflictError, ImportSummary
from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.docbook.variablelists import ParsedVariableList
from dicom_kb.ir.models import AttributeValueTerm
from dicom_kb.ir.validators import IdentifierValidationError, normalize_tag

_TAG_IN_TEXT_RE = re.compile(r"\([0-9A-Fa-fxX]{4},[0-9A-Fa-fxX]{4}\)")
# "Enumerated Values for X (gggg,eeee) when Y (gggg,eeee) is ..." is about X.
_QUALIFIER_RE = re.compile(r"\s(?:when|if|where|for Value)\s", re.IGNORECASE)
_NAME_SPLIT_RE = re.compile(r",\s*(?:and\s+)?|\s+and\s+")


def import_attribute_value_terms(
    connection: sqlite3.Connection,
    *,
    edition: str,
    document: ParsedDocument,
) -> ImportSummary:
    """Import the enumerated values and defined terms of a part's lists.

    A list in a table cell belongs to the attribute of its row. A list in a
    section belongs to the attribute the list title names, else the one the
    section title names.
    """
    terms = _value_terms(connection, edition, document)
    try:
        with connection:
            connection.executemany(
                """
                INSERT INTO attribute_value_term (
                  id, edition_id, attribute_tag, attribute_use_id, table_id,
                  section_id, list_index, list_title, term_kind, term_order,
                  value, meaning
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        term.id,
                        term.edition_id,
                        term.attribute_tag,
                        term.attribute_use_id,
                        term.table_id,
                        term.section_id,
                        term.list_index,
                        term.list_title,
                        term.term_kind,
                        term.term_order,
                        term.value,
                        term.meaning,
                    )
                    for term in terms
                ],
            )
    except sqlite3.IntegrityError as exc:
        raise ImportConflictError(
            f"failed to import attribute value terms for {edition} {document.part}"
        ) from exc
    return ImportSummary(
        edition=edition, source_refs=0, attribute_value_terms=len(terms)
    )


def value_term_kind(title: str | None) -> str | None:
    """Return `enumerated_value` or `defined_term` for a list title."""
    lowered = normalize_text(title or "").lower()
    if "enumerated value" in lowered:
        return "enumerated_value"
    if "defined term" in lowered:
        return "defined_term"
    return None


def _value_terms(
    connection: sqlite3.Connection, edition: str, document: ParsedDocument
) -> list[AttributeValueTerm]:
    names = _element_names(connection, edition)
    rows = _attribute_rows(connection, edition)
    terms: list[AttributeValueTerm] = []
    for variablelist in document.variablelists:
        kind = value_term_kind(variablelist.title)
        if kind is None or not variablelist.entries:
            continue
        for tag in _list_tags(variablelist, names):
            attribute_use_id = None
            if variablelist.row_tag is not None and variablelist.table_xml_id:
                matches = rows.get((variablelist.table_xml_id, tag), [])
                if matches:
                    attribute_use_id = matches[
                        min(variablelist.row_tag_index, len(matches) - 1)
                    ]
            order = 0
            for entry in variablelist.entries:
                for value in entry.terms:
                    terms.append(
                        AttributeValueTerm(
                            id=f"{edition}.{document.part}.value_term."
                            f"{variablelist.ordinal}.{tag}.{order}",
                            edition_id=edition,
                            attribute_tag=tag,
                            attribute_use_id=attribute_use_id,
                            table_id=variablelist.table_xml_id,
                            section_id=variablelist.parent_xml_id,
                            list_index=variablelist.ordinal,
                            list_title=_list_title(variablelist),
                            term_kind=kind,
                            term_order=order,
                            value=value,
                            meaning=entry.definition or None,
                        )
                    )
                    order += 1
    return terms


def _list_title(variablelist: ParsedVariableList) -> str:
    title = normalize_text(variablelist.title or "")
    if variablelist.lead:
        return f"{normalize_text(variablelist.lead).rstrip('.:')}. {title}"
    return title


def _list_tags(variablelist: ParsedVariableList, names: dict[str, str]) -> list[str]:
    """Return the tags of the attributes a list gives values for."""
    if variablelist.row_tag is not None:
        tag = _tag(variablelist.row_tag)
        if tag is not None:
            return [tag]
    subject = _QUALIFIER_RE.split(variablelist.title or "", maxsplit=1)[0]
    tags = [
        tag
        for found in _TAG_IN_TEXT_RE.findall(subject)
        if (tag := _tag(found)) is not None
    ]
    if tags:
        return list(dict.fromkeys(tags))
    title = _name_key(variablelist.section_title or "")
    if title in names:
        return [names[title]]
    return list(
        dict.fromkeys(
            names[key]
            for part in _NAME_SPLIT_RE.split(title)
            if (key := part.strip()) in names
        )
    )


def _element_names(connection: sqlite3.Connection, edition: str) -> dict[str, str]:
    names: dict[str, str] = {}
    for row in connection.execute(
        """
        SELECT name, tag FROM data_element WHERE edition_id = ?
        ORDER BY retired, is_range, tag
        """,
        (edition,),
    ):
        names.setdefault(_name_key(str(row["name"])), str(row["tag"]))
    return names


def _attribute_rows(
    connection: sqlite3.Connection, edition: str
) -> dict[tuple[str, str], list[str]]:
    rows: dict[tuple[str, str], list[str]] = {}
    for row in connection.execute(
        """
        SELECT sr.table_id, a.attribute_tag, a.id
        FROM attribute_use a JOIN source_ref sr ON sr.id = a.source_ref_id
        WHERE a.edition_id = ? AND a.row_kind = 'attribute'
        ORDER BY a.owner_id, a.row_order
        """,
        (edition,),
    ):
        rows.setdefault((str(row["table_id"]), str(row["attribute_tag"])), []).append(
            str(row["id"])
        )
    return rows


def _tag(text: str) -> str | None:
    try:
        return normalize_tag(text)
    except IdentifierValidationError:
        return None


def _name_key(name: str) -> str:
    return normalize_text(name).replace("’", "'").lower()
