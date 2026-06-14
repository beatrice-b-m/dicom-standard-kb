"""Parser scaffold for PS3.8 network communication tables."""

from __future__ import annotations

from dataclasses import dataclass

from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.tables import ParsedRow, ParsedTable
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.ir.models import ParserWarning, SourceRef


@dataclass(frozen=True)
class Part08TableSummary:
    """A recognized PS3.8 table awaiting semantic import in Phase 7."""

    table_id: str | None
    title: str | None
    table_kind: str
    source_ref: SourceRef


@dataclass(frozen=True)
class NetworkPduBehavior:
    """Selected PS3.8 association PDU behavior parsed from a PDU table."""

    pdu: str
    direction: str | None
    behavior: str
    source_ref: SourceRef


@dataclass(frozen=True)
class Part08ParseResult:
    """Parsed PS3.8 scaffold metadata and parser gap warnings."""

    recognized_tables: tuple[Part08TableSummary, ...]
    pdu_behaviors: tuple[NetworkPduBehavior, ...]
    warnings: tuple[ParserWarning, ...]


def parse_part08(document: ParsedDocument, *, edition: str) -> Part08ParseResult:
    """Classify PS3.8 tables without exposing public network facts yet."""
    recognized: list[Part08TableSummary] = []
    pdu_behaviors: list[NetworkPduBehavior] = []
    warnings: list[ParserWarning] = []

    for table in document.tables:
        headers = _headers(table)
        if _is_association_pdu_table(headers):
            recognized.append(
                Part08TableSummary(
                    table_id=table.xml_id,
                    title=table.title,
                    table_kind="association_pdu",
                    source_ref=_source_ref(edition, table),
                )
            )
            pdu_behaviors.extend(
                _parse_pdu_behavior_table(table, headers, edition, warnings)
            )
        else:
            warnings.append(
                ParserWarning(
                    part="PS3.8",
                    table_id=table.xml_id,
                    row_index=None,
                    message="unsupported PS3.8 table shape",
                )
            )

    return Part08ParseResult(
        recognized_tables=tuple(recognized),
        pdu_behaviors=tuple(pdu_behaviors),
        warnings=tuple(warnings),
    )


def _headers(table: ParsedTable) -> dict[str, int]:
    for row in table.rows:
        if row.section == "thead":
            return {_key(cell.text): cell.column for cell in row.cells}
    if not table.rows:
        return {}
    return {_key(cell.text): cell.column for cell in table.rows[0].cells}


def _is_association_pdu_table(headers: dict[str, int]) -> bool:
    return "pdu" in headers and bool(
        headers.keys() & {"direction", "description", "field", "item", "role"}
    )


def _parse_pdu_behavior_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    warnings: list[ParserWarning],
) -> list[NetworkPduBehavior]:
    pdu_column = headers.get("pdu")
    behavior_column = headers.get("behavior")
    if pdu_column is None or behavior_column is None:
        warnings.append(
            ParserWarning(
                part="PS3.8",
                table_id=table.xml_id,
                row_index=None,
                message="skipped association PDU table without pdu and behavior",
            )
        )
        return []

    records: list[NetworkPduBehavior] = []
    direction_column = headers.get("direction")
    for row in _data_rows(table):
        pdu = _cell(row, pdu_column)
        behavior = _cell(row, behavior_column)
        if not pdu or not behavior:
            warnings.append(
                ParserWarning(
                    part="PS3.8",
                    table_id=table.xml_id,
                    row_index=row.row_index,
                    message="skipped incomplete association PDU behavior row",
                )
            )
            continue
        records.append(
            NetworkPduBehavior(
                pdu=pdu,
                direction=_optional_cell(row, direction_column),
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
        id=f"{edition}.PS3.8.{table_id}",
        edition_id=edition,
        part="PS3.8",
        section=table.parent_xml_id,
        table_id=table_id,
        xml_id=table.xml_id,
        title=table.title,
    )
