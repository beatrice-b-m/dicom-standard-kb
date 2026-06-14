"""Parser scaffold for PS3.8 network communication tables."""

from __future__ import annotations

from dataclasses import dataclass

from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.tables import ParsedTable
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
class Part08ParseResult:
    """Parsed PS3.8 scaffold metadata and parser gap warnings."""

    recognized_tables: tuple[Part08TableSummary, ...]
    warnings: tuple[ParserWarning, ...]


def parse_part08(document: ParsedDocument, *, edition: str) -> Part08ParseResult:
    """Classify PS3.8 tables without exposing public network facts yet."""
    recognized: list[Part08TableSummary] = []
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
        warnings=tuple(warnings),
    )


def _headers(table: ParsedTable) -> set[str]:
    for row in table.rows:
        if row.section == "thead":
            return {_key(cell.text) for cell in row.cells}
    if not table.rows:
        return set()
    return {_key(cell.text) for cell in table.rows[0].cells}


def _is_association_pdu_table(headers: set[str]) -> bool:
    return "pdu" in headers and bool(
        headers & {"direction", "description", "field", "item", "role"}
    )


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
