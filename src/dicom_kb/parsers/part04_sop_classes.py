"""Parser for PS3.4 Service Class and SOP Class tables."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.tables import ParsedRow, ParsedTable
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.ir.models import (
    ParserWarning,
    ServiceClass,
    SOPClass,
    SOPClassIOD,
    SourceRef,
)
from dicom_kb.ir.validators import IdentifierValidationError, normalize_uid

SERVICE_CLASS_TITLE_RE = re.compile(
    r"^(?P<name>.+?\bService\s+Class)\b.*(?:SOP\s+Classes|IODs)", re.I
)


@dataclass(frozen=True)
class Part04ParseResult:
    """Parsed PS3.4 service class and SOP Class facts."""

    service_classes: tuple[ServiceClass, ...]
    sop_classes: tuple[SOPClass, ...]
    sop_class_iods: tuple[SOPClassIOD, ...]
    warnings: tuple[ParserWarning, ...]


def parse_part04(
    document: ParsedDocument,
    *,
    edition: str,
    iod_id_by_ref: Mapping[str, str] | None = None,
) -> Part04ParseResult:
    """Parse PS3.4 SOP Class records from DocBook table IR."""
    service_classes: dict[str, ServiceClass] = {}
    sop_classes: dict[str, SOPClass] = {}
    sop_class_iods: dict[str, SOPClassIOD] = {}
    warnings: list[ParserWarning] = []

    for table in document.tables:
        headers = _headers(table)
        if not _is_sop_class_iod_table(headers):
            continue
        service_class = _service_class_from_table(table, edition)
        service_classes[service_class.id] = service_class
        rows = _parse_sop_class_table(
            table,
            headers,
            edition,
            service_class=service_class,
            iod_id_by_ref=iod_id_by_ref or {},
            warnings=warnings,
        )
        for sop_class, edge in rows:
            sop_classes.setdefault(sop_class.id, sop_class)
            sop_class_iods.setdefault(edge.id, edge)

    return Part04ParseResult(
        service_classes=tuple(service_classes.values()),
        sop_classes=tuple(sop_classes.values()),
        sop_class_iods=tuple(sop_class_iods.values()),
        warnings=tuple(warnings),
    )


def _headers(table: ParsedTable) -> dict[str, int]:
    for row in table.rows:
        if row.section == "thead":
            return {_key(cell.text): cell.column for cell in row.cells}
    if not table.rows:
        return {}
    return {_key(cell.text): cell.column for cell in table.rows[0].cells}


def _is_sop_class_iod_table(headers: dict[str, int]) -> bool:
    return (
        _iod_column(headers) is not None
        and _sop_name_column(headers) is not None
        and _sop_uid_column(headers) is not None
    )


def _parse_sop_class_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    *,
    service_class: ServiceClass,
    iod_id_by_ref: Mapping[str, str],
    warnings: list[ParserWarning],
) -> list[tuple[SOPClass, SOPClassIOD]]:
    iod_column = _iod_column(headers)
    sop_name_column = _sop_name_column(headers)
    sop_uid_column = _sop_uid_column(headers)
    if iod_column is None or sop_name_column is None or sop_uid_column is None:
        return []

    rows: list[tuple[SOPClass, SOPClassIOD]] = []
    source_ref = _source_ref(edition, table)
    for order, row in enumerate(_data_rows(table)):
        sop_name = _cell(row, sop_name_column)
        iod_id = _iod_id_from_ref(row, iod_column, iod_id_by_ref)
        iod_name = _iod_name(_cell(row, iod_column))
        if iod_id is None:
            iod_name = iod_name or _iod_name_from_sop_name(sop_name)
            iod_id = _id(edition, "iod", iod_name) if iod_name else None
        if iod_id is None or not sop_name:
            warnings.append(_warning(table, row, "skipped SOP Class row missing name"))
            continue
        try:
            uid_value = normalize_uid(_cell(row, sop_uid_column))
        except IdentifierValidationError as exc:
            warnings.append(
                _warning(table, row, f"skipped malformed SOP Class UID: {exc}")
            )
            continue

        sop_class = SOPClass(
            id=f"{edition}.sop_class.{uid_value}",
            edition_id=edition,
            name=sop_name,
            uid_value=uid_value,
            service_class_id=service_class.id,
            source_ref=source_ref,
        )
        edge = SOPClassIOD(
            id=f"{sop_class.id}.iod.{order}",
            edition_id=edition,
            sop_class_id=sop_class.id,
            iod_id=iod_id,
            resolution="parsed",
            source_ref=source_ref,
        )
        rows.append((sop_class, edge))
    return rows


def _service_class_from_table(table: ParsedTable, edition: str) -> ServiceClass:
    title = table.title or table.xml_id or "Unknown Service Class"
    match = SERVICE_CLASS_TITLE_RE.match(title)
    name = match.group("name") if match else title
    return ServiceClass(
        id=_id(edition, "service_class", name),
        edition_id=edition,
        name=name,
        section=table.xml_id,
        source_ref=_source_ref(edition, table),
    )


def _iod_column(headers: dict[str, int]) -> int | None:
    exact = _first_header(headers, "iod", "information object definition")
    if exact is not None:
        return exact
    for name, column in headers.items():
        if name.startswith("iod specification"):
            return column
    return None


def _sop_name_column(headers: dict[str, int]) -> int | None:
    return _first_header(headers, "sop class name", "sop class")


def _sop_uid_column(headers: dict[str, int]) -> int | None:
    return _first_header(headers, "sop class uid", "uid")


def _first_header(headers: dict[str, int], *names: str) -> int | None:
    for name in names:
        if name in headers:
            return headers[name]
    return None


def _data_rows(table: ParsedTable) -> list[ParsedRow]:
    return [
        row for row in table.rows if row.section != "thead" and row.row_kind == "data"
    ]


def _cell(row: ParsedRow, column: int) -> str:
    for cell in row.cells:
        if cell.column == column:
            return cell.text
    return ""


def _iod_id_from_ref(
    row: ParsedRow, column: int, iod_id_by_ref: Mapping[str, str]
) -> str | None:
    for cell in row.cells:
        if cell.column != column:
            continue
        for target in cell.xrefs:
            iod_id = iod_id_by_ref.get(target)
            if iod_id is not None:
                return iod_id
    return None


def _iod_name(value: str) -> str:
    normalized = normalize_text(value)
    return re.sub(r"\s+IOD$", "", normalized, flags=re.I)


def _iod_name_from_sop_name(value: str) -> str:
    normalized = normalize_text(value)
    return re.sub(r"\s+Storage$", "", normalized, flags=re.I)


def _key(value: str) -> str:
    return normalize_text(value).lower()


def _source_ref(edition: str, table: ParsedTable) -> SourceRef:
    table_id = table.xml_id or "unknown"
    return SourceRef(
        id=f"{edition}.PS3.4.{table_id}",
        edition_id=edition,
        part="PS3.4",
        section=table.xml_id,
        table_id=table_id,
        xml_id=table.xml_id,
        title=table.title,
    )


def _warning(table: ParsedTable, row: ParsedRow, message: str) -> ParserWarning:
    return ParserWarning(
        part="PS3.4",
        table_id=table.xml_id,
        row_index=row.row_index,
        message=message,
    )


def _id(edition: str, kind: str, value: str) -> str:
    return f"{edition}.{kind}.{_slug(value)}"


def _slug(value: str) -> str:
    normalized = normalize_text(value).lower()
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
