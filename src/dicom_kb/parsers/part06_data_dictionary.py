"""Parser for PS3.6 data element and UID registry tables."""

from __future__ import annotations

from dataclasses import dataclass

from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.tables import ParsedRow, ParsedTable
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.ir.models import DataElement, ParserWarning, SourceRef, UIDRegistryEntry
from dicom_kb.ir.validators import (
    IdentifierValidationError,
    normalize_tag,
    normalize_uid,
    split_tag,
)


@dataclass(frozen=True)
class Part06ParseResult:
    """Parsed PS3.6 registry facts."""

    data_elements: tuple[DataElement, ...]
    uid_registry_entries: tuple[UIDRegistryEntry, ...]
    warnings: tuple[ParserWarning, ...]


def parse_part06(document: ParsedDocument, *, edition: str) -> Part06ParseResult:
    """Parse PS3.6 tables from raw DocBook table IR."""
    data_elements: list[DataElement] = []
    uids: list[UIDRegistryEntry] = []
    warnings: list[ParserWarning] = []

    for table in document.tables:
        headers = _headers(table)
        if _is_data_element_table(headers):
            data_elements.extend(
                _parse_data_element_table(table, headers, edition, warnings)
            )
        elif _is_uid_table(headers):
            uids.extend(_parse_uid_table(table, headers, edition, warnings))

    # A repeated tag or UID would abort the whole PS3.6 import on its unique
    # key, and every data element and UID with it. Keep the first and log it.
    return Part06ParseResult(
        data_elements=_first_of_each(
            data_elements, "tag", "data element tag", warnings
        ),
        uid_registry_entries=_first_of_each(uids, "uid_value", "UID value", warnings),
        warnings=tuple(warnings),
    )


def _headers(table: ParsedTable) -> dict[str, int]:
    for row in table.rows:
        if row.section == "thead":
            return {_key(cell.text): cell.column for cell in row.cells}
    if not table.rows:
        return {}
    return {_key(cell.text): cell.column for cell in table.rows[0].cells}


def _is_data_element_table(headers: dict[str, int]) -> bool:
    return "tag" in headers and "name" in headers and "keyword" in headers


def _is_uid_table(headers: dict[str, int]) -> bool:
    return "uid value" in headers and "uid name" in headers and "uid type" in headers


def _parse_data_element_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    warnings: list[ParserWarning],
) -> list[DataElement]:
    records: list[DataElement] = []
    for row in _data_rows(table):
        try:
            raw_tag = _cell(row, headers["tag"])
            tag = normalize_tag(raw_tag)
            group, element, is_range = split_tag(tag)
        except (KeyError, IdentifierValidationError) as exc:
            warnings.append(_warning(table, row, f"skipped malformed tag row: {exc}"))
            continue

        name = _cell(row, headers["name"])
        keyword = _optional_cell(row, headers.get("keyword"))
        retired_text = _optional_cell(row, _retired_column(headers))
        retired = _is_retired(name, keyword, retired_text)
        records.append(
            DataElement(
                id=f"{edition}.data_element.{tag}",
                edition_id=edition,
                tag=tag,
                group_pattern=group,
                element_pattern=element,
                is_range=is_range,
                name=_strip_retired_marker(name) or name,
                keyword=_strip_retired_marker(keyword) if keyword else None,
                vr=_optional_cell(row, headers.get("vr")),
                vm=_optional_cell(row, headers.get("vm")),
                retired=retired,
                retired_in_or_last_seen=retired_text if retired else None,
                source_ref=_source_ref(edition, table),
            )
        )
    return records


def _parse_uid_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    warnings: list[ParserWarning],
) -> list[UIDRegistryEntry]:
    records: list[UIDRegistryEntry] = []
    for row in _data_rows(table):
        try:
            uid_value = normalize_uid(_cell(row, headers["uid value"]))
        except (KeyError, IdentifierValidationError) as exc:
            warnings.append(_warning(table, row, f"skipped malformed UID row: {exc}"))
            continue

        uid_name = _cell(row, headers["uid name"])
        keyword = _optional_cell(row, headers.get("uid keyword"))
        retired_text = _optional_cell(row, _retired_column(headers))
        retired = _is_retired(uid_name, keyword, retired_text)
        records.append(
            UIDRegistryEntry(
                id=f"{edition}.uid.{uid_value}",
                edition_id=edition,
                uid_value=uid_value,
                uid_name=_strip_retired_marker(uid_name) or uid_name,
                uid_keyword=_strip_retired_marker(keyword) if keyword else None,
                uid_type=_cell(row, headers["uid type"]),
                part=_optional_cell(row, headers.get("part")),
                retired=retired,
                retired_in_or_last_seen=retired_text if retired else None,
                source_ref=_source_ref(edition, table),
            )
        )
    return records


def _data_rows(table: ParsedTable) -> list[ParsedRow]:
    return [
        row for row in table.rows if row.section != "thead" and row.row_kind == "data"
    ]


def _cell(row: ParsedRow, column: int) -> str:
    for cell in row.cells:
        if cell.column == column:
            return cell.text
    return ""


def _optional_cell(row: ParsedRow, column: int | None) -> str | None:
    if column is None:
        return None
    value = normalize_text(_cell(row, column))
    return value or None


_KNOWN_COLUMNS = frozenset(
    {"tag", "name", "keyword", "vr", "vm"}
    | {"uid value", "uid name", "uid keyword", "uid type", "part"}
    | {"normative reference"}
)


def _retired_column(headers: dict[str, int]) -> int | None:
    """Return the column that marks retired rows ("RET"), if the table has one.

    NEMA leaves its header blank today; any column that isn't one of the
    known ones counts, so naming it later doesn't silently un-retire rows.
    """
    for key, column in headers.items():
        if key not in _KNOWN_COLUMNS:
            return column
    return None


def _key(value: str) -> str:
    return normalize_text(value).lower()


def _is_retired(*values: str | None) -> bool:
    return any(_has_retired_marker(value) for value in values)


def _has_retired_marker(value: str | None) -> bool:
    if value is None:
        return False
    normalized = normalize_text(value)
    if "retired" in normalized.lower():
        return True
    return any(token == "RET" for token in normalized.replace("-", " ").split())


def _strip_retired_marker(value: str | None) -> str | None:
    if value is None:
        return None
    without_note = value.replace("(Retired)", "")
    return normalize_text(" ".join(t for t in without_note.split() if t != "RET"))


def _source_ref(edition: str, table: ParsedTable) -> SourceRef:
    table_id = table.xml_id or "unknown"
    return SourceRef(
        id=f"{edition}.PS3.6.{table_id}",
        edition_id=edition,
        part="PS3.6",
        table_id=table_id,
        xml_id=table.xml_id,
        title=table.title,
    )


def _warning(table: ParsedTable, row: ParsedRow, message: str) -> ParserWarning:
    return ParserWarning(
        part="PS3.6",
        table_id=table.xml_id,
        row_index=row.row_index,
        message=message,
    )


def _first_of_each[R: (DataElement, UIDRegistryEntry)](
    records: list[R], field: str, label: str, warnings: list[ParserWarning]
) -> tuple[R, ...]:
    kept: dict[str, R] = {}
    for record in records:
        value = getattr(record, field)
        if value in kept:
            warnings.append(
                ParserWarning(
                    part="PS3.6",
                    table_id=record.source_ref.table_id,
                    row_index=None,
                    message=f"duplicate {label} {value}; kept the first",
                )
            )
        else:
            kept[value] = record
    return tuple(kept.values())
