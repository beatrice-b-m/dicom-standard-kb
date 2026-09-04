"""Attribute value term extraction and persistence."""

from __future__ import annotations

import re
import sqlite3
from typing import cast

from dicom_kb.db.importers._shared import (
    ImportSummary,
    _insert_source_ref,
    _unique_source_refs,
)
from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.docbook.variablelists import ParsedVariableList
from dicom_kb.ir.models import (
    AttributeValueTerm,
    SourceRef,
)


def import_attribute_value_terms(
    connection: sqlite3.Connection,
    *,
    edition: str,
    document: ParsedDocument,
) -> ImportSummary:
    """Import parsed enumerated values and defined terms from DocBook lists."""
    term_records = _attribute_value_terms_from_document(connection, edition, document)
    source_refs = _unique_source_refs(record.source_ref for record in term_records)

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for term in term_records:
                _insert_attribute_value_term(connection, term)
    except sqlite3.IntegrityError as exc:
        raise ImportError(
            f"failed to import attribute value terms for {edition} {document.part}"
        ) from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        attribute_value_terms=len(term_records),
    )


def _attribute_value_terms_from_document(
    connection: sqlite3.Connection, edition: str, document: ParsedDocument
) -> tuple[AttributeValueTerm, ...]:
    section_by_xml_id = {
        section.xml_id: section
        for section in document.sections
        if section.xml_id is not None
    }
    records: list[AttributeValueTerm] = []
    for variablelist in document.variablelists:
        term_kind = _value_term_kind(variablelist)
        if term_kind is None:
            continue
        section = (
            section_by_xml_id.get(variablelist.parent_xml_id)
            if variablelist.parent_xml_id is not None
            else None
        )
        data_element = _data_element_for_variablelist(
            connection,
            edition=edition,
            variablelist=variablelist,
            section_title=section.title if section is not None else None,
            section_text=section.plain_text if section is not None else None,
        )
        attribute_use_ids = (
            _attribute_use_ids_for_term_context(
                connection,
                edition=edition,
                data_element_id=str(data_element["id"]),
                data_element_tag=str(data_element["tag"]),
                parent_xml_id=variablelist.parent_xml_id,
            )
            if data_element is not None
            else ()
        )
        source_ref = SourceRef(
            id=_value_term_source_ref_id(edition, document.part, variablelist),
            edition_id=edition,
            part=document.part,
            section=variablelist.parent_xml_id,
            xml_id=variablelist.xml_id,
            title=variablelist.title,
        )
        for entry in variablelist.entries:
            for term_index, value in enumerate(entry.terms):
                targets = attribute_use_ids or (None,)
                for context_index, attribute_use_id in enumerate(targets):
                    records.append(
                        AttributeValueTerm(
                            id=_value_term_id(
                                edition,
                                document.part,
                                variablelist,
                                entry.entry_index,
                                term_index,
                                context_index,
                            ),
                            edition_id=edition,
                            attribute_use_id=attribute_use_id,
                            data_element_id=(
                                str(data_element["id"])
                                if data_element is not None
                                else None
                            ),
                            context_label=_value_term_context_label(
                                variablelist,
                                section_title=(
                                    section.title if section is not None else None
                                ),
                            ),
                            term_kind=term_kind,
                            value=value,
                            meaning=entry.definition or None,
                            source_ref=source_ref,
                        )
                    )
    return tuple(records)


def _insert_attribute_value_term(
    connection: sqlite3.Connection, term: AttributeValueTerm
) -> None:
    connection.execute(
        """
        INSERT INTO attribute_value_term (
          id, edition_id, attribute_use_id, data_element_id, context_label,
          term_kind, value, meaning, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            term.id,
            term.edition_id,
            term.attribute_use_id,
            term.data_element_id,
            term.context_label,
            term.term_kind,
            term.value,
            term.meaning,
            term.source_ref.id,
        ),
    )


def _attribute_use_ids_for_term_context(
    connection: sqlite3.Connection,
    *,
    edition: str,
    data_element_id: str,
    data_element_tag: str,
    parent_xml_id: str | None,
) -> tuple[str, ...]:
    if parent_xml_id is None:
        return ()
    rows = connection.execute(
        """
        SELECT au.id
        FROM attribute_use au
        JOIN source_ref sr ON sr.id = au.source_ref_id
        WHERE au.edition_id = ?
          AND au.attribute_tag = ?
          AND sr.section = ?
        ORDER BY au.id
        """,
        (edition, data_element_tag, parent_xml_id),
    ).fetchall()
    if rows:
        return tuple(str(row["id"]) for row in rows)

    global_rows = connection.execute(
        """
        SELECT au.id
        FROM attribute_use au
        JOIN data_element de
          ON de.edition_id = au.edition_id
         AND de.tag = au.attribute_tag
        WHERE au.edition_id = ?
          AND de.id = ?
        ORDER BY au.id
        """,
        (edition, data_element_id),
    ).fetchall()
    if len(global_rows) == 1:
        return (str(global_rows[0]["id"]),)
    return ()


def _data_element_for_variablelist(
    connection: sqlite3.Connection,
    *,
    edition: str,
    variablelist: ParsedVariableList,
    section_title: str | None,
    section_text: str | None,
) -> sqlite3.Row | None:
    candidates = [
        section_title,
        variablelist.parent_xml_id,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        row = connection.execute(
            """
            SELECT id, tag
            FROM data_element
            WHERE edition_id = ?
              AND (
                lower(name) = lower(?)
                OR lower(keyword) = lower(?)
                OR tag = ?
              )
            ORDER BY is_range, tag
            LIMIT 1
            """,
            (edition, candidate, candidate, candidate),
        ).fetchone()
        if row is not None:
            return cast(sqlite3.Row, row)
    return _data_element_mentioned_in_text(
        connection,
        edition=edition,
        section_text=section_text,
    )


def _value_term_context_label(
    variablelist: ParsedVariableList, *, section_title: str | None
) -> str | None:
    if section_title and variablelist.title:
        return f"{section_title} - {variablelist.title}"
    return variablelist.title or section_title or variablelist.parent_xml_id


def _value_term_id(
    edition: str,
    part: str,
    variablelist: ParsedVariableList,
    entry_index: int,
    term_index: int,
    context_index: int,
) -> str:
    return (
        f"{edition}.{part}.attribute_value_term."
        f"{variablelist.xml_id or variablelist.ordinal}."
        f"{entry_index}.{term_index}.{context_index}"
    )


def _value_term_kind(variablelist: ParsedVariableList) -> str | None:
    title = normalize_text(variablelist.title or "").lower().rstrip(":")
    if "enumerated value" in title:
        return "enumerated_value"
    if "defined term" in title:
        return "defined_term"
    return None


def _value_term_source_ref_id(
    edition: str, part: str, variablelist: ParsedVariableList
) -> str:
    return f"{edition}.{part}.value_terms.{variablelist.xml_id or variablelist.ordinal}"


def _data_element_mentioned_in_text(
    connection: sqlite3.Connection,
    *,
    edition: str,
    section_text: str | None,
) -> sqlite3.Row | None:
    if not section_text:
        return None
    compact_text = _compact_value(section_text)
    matches: list[tuple[int, sqlite3.Row]] = []
    for row in connection.execute(
        """
        SELECT id, tag, name
        FROM data_element
        WHERE edition_id = ?
        ORDER BY tag
        """,
        (edition,),
    ):
        needle = _compact_value(f"{row['name']} {row['tag']}")
        index = compact_text.find(needle)
        if index >= 0:
            matches.append((index, row))
    if not matches:
        return None
    return sorted(matches, key=lambda match: match[0])[0][1]


def _compact_value(value: str) -> str:
    return re.sub(r"\s+", "", normalize_text(value)).lower()
