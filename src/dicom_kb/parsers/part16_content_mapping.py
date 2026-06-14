"""Parser scaffold for PS3.16 content mapping tables."""

from __future__ import annotations

from dataclasses import dataclass

from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.tables import ParsedTable
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.ir.models import ParserWarning, SourceRef


@dataclass(frozen=True)
class Part16TableSummary:
    """A recognized PS3.16 table awaiting semantic import in Phase 5."""

    table_id: str | None
    title: str | None
    table_kind: str
    source_ref: SourceRef


@dataclass(frozen=True)
class Part16ParseResult:
    """Parsed PS3.16 scaffold metadata and parser gap warnings."""

    recognized_tables: tuple[Part16TableSummary, ...]
    warnings: tuple[ParserWarning, ...]


def parse_part16(document: ParsedDocument, *, edition: str) -> Part16ParseResult:
    """Classify PS3.16 tables without exposing public CMR facts yet."""
    recognized: list[Part16TableSummary] = []
    warnings: list[ParserWarning] = []

    for table in document.tables:
        headers = _headers(table)
        if _is_sr_template_table(headers):
            recognized.append(
                Part16TableSummary(
                    table_id=table.xml_id,
                    title=table.title,
                    table_kind="sr_template",
                    source_ref=_source_ref(edition, table),
                )
            )
        else:
            warnings.append(
                ParserWarning(
                    part="PS3.16",
                    table_id=table.xml_id,
                    row_index=None,
                    message="unsupported PS3.16 table shape",
                )
            )

    return Part16ParseResult(
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


def _is_sr_template_table(headers: set[str]) -> bool:
    return "tid" in headers and bool(
        headers & {"name", "template name", "template", "extensibility"}
    )


def _key(value: str) -> str:
    return normalize_text(value).lower()


def _source_ref(edition: str, table: ParsedTable) -> SourceRef:
    table_id = table.xml_id or "unknown"
    return SourceRef(
        id=f"{edition}.PS3.16.{table_id}",
        edition_id=edition,
        part="PS3.16",
        section=table.parent_xml_id,
        table_id=table_id,
        xml_id=table.xml_id,
        title=table.title,
    )
