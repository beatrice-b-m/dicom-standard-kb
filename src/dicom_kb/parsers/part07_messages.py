"""Parser scaffold for PS3.7 message exchange tables."""

from __future__ import annotations

from dataclasses import dataclass

from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.tables import ParsedRow, ParsedTable
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.ir.models import ParserWarning, SourceRef


@dataclass(frozen=True)
class Part07TableSummary:
    """A recognized PS3.7 table awaiting semantic import in Phase 7."""

    table_id: str | None
    title: str | None
    table_kind: str
    source_ref: SourceRef


@dataclass(frozen=True)
class MessageServiceBehavior:
    """Selected PS3.7 DIMSE service behavior parsed from a service table."""

    service: str
    role: str | None
    behavior: str
    source_ref: SourceRef


@dataclass(frozen=True)
class Part07ParseResult:
    """Parsed PS3.7 scaffold metadata and parser gap warnings."""

    recognized_tables: tuple[Part07TableSummary, ...]
    service_behaviors: tuple[MessageServiceBehavior, ...]
    warnings: tuple[ParserWarning, ...]


def parse_part07(document: ParsedDocument, *, edition: str) -> Part07ParseResult:
    """Classify PS3.7 tables without exposing public message facts yet."""
    recognized: list[Part07TableSummary] = []
    service_behaviors: list[MessageServiceBehavior] = []
    warnings: list[ParserWarning] = []

    for table in document.tables:
        headers = _headers(table)
        if _is_dimse_service_table(headers):
            recognized.append(
                Part07TableSummary(
                    table_id=table.xml_id,
                    title=table.title,
                    table_kind="dimse_service",
                    source_ref=_source_ref(edition, table),
                )
            )
            service_behaviors.extend(
                _parse_service_behavior_table(table, headers, edition, warnings)
            )
        else:
            warnings.append(
                ParserWarning(
                    part="PS3.7",
                    table_id=table.xml_id,
                    row_index=None,
                    message="unsupported PS3.7 table shape",
                )
            )

    return Part07ParseResult(
        recognized_tables=tuple(recognized),
        service_behaviors=tuple(service_behaviors),
        warnings=tuple(warnings),
    )


def _headers(table: ParsedTable) -> dict[str, int]:
    for row in table.rows:
        if row.section == "thead":
            return {_key(cell.text): cell.column for cell in row.cells}
    if not table.rows:
        return {}
    return {_key(cell.text): cell.column for cell in table.rows[0].cells}


def _is_dimse_service_table(headers: dict[str, int]) -> bool:
    return "service" in headers and bool(
        headers.keys() & {"role", "message", "command", "dimse service"}
    )


def _parse_service_behavior_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    warnings: list[ParserWarning],
) -> list[MessageServiceBehavior]:
    service_column = headers.get("service")
    behavior_column = headers.get("behavior")
    if service_column is None or behavior_column is None:
        warnings.append(
            ParserWarning(
                part="PS3.7",
                table_id=table.xml_id,
                row_index=None,
                message="skipped DIMSE service table without service and behavior",
            )
        )
        return []

    records: list[MessageServiceBehavior] = []
    role_column = headers.get("role")
    for row in _data_rows(table):
        service = _cell(row, service_column)
        behavior = _cell(row, behavior_column)
        if not service or not behavior:
            warnings.append(
                ParserWarning(
                    part="PS3.7",
                    table_id=table.xml_id,
                    row_index=row.row_index,
                    message="skipped incomplete DIMSE service behavior row",
                )
            )
            continue
        records.append(
            MessageServiceBehavior(
                service=service,
                role=_optional_cell(row, role_column),
                behavior=behavior,
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
            return normalize_text(cell.text)
    return ""


def _optional_cell(row: ParsedRow, column: int | None) -> str | None:
    if column is None:
        return None
    value = _cell(row, column)
    return value or None


def _key(value: str) -> str:
    return normalize_text(value).lower()


def _source_ref(edition: str, table: ParsedTable) -> SourceRef:
    table_id = table.xml_id or "unknown"
    return SourceRef(
        id=f"{edition}.PS3.7.{table_id}",
        edition_id=edition,
        part="PS3.7",
        section=table.parent_xml_id,
        table_id=table_id,
        xml_id=table.xml_id,
        title=table.title,
    )
