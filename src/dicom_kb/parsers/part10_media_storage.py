"""Parser scaffold for PS3.10 media storage and file format tables."""

from __future__ import annotations

from dataclasses import dataclass

from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.tables import ParsedTable
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.ir.models import ParserWarning, SourceRef


@dataclass(frozen=True)
class Part10TableSummary:
    """A recognized PS3.10 table awaiting semantic import in Phase 3."""

    table_id: str | None
    title: str | None
    table_kind: str
    source_ref: SourceRef


@dataclass(frozen=True)
class Part10ParseResult:
    """Parsed PS3.10 scaffold metadata and parser gap warnings."""

    recognized_tables: tuple[Part10TableSummary, ...]
    warnings: tuple[ParserWarning, ...]


def parse_part10(document: ParsedDocument, *, edition: str) -> Part10ParseResult:
    """Classify PS3.10 tables without exposing public media-storage facts yet."""
    recognized: list[Part10TableSummary] = []
    warnings: list[ParserWarning] = []

    for table in document.tables:
        headers = _headers(table)
        if _is_file_meta_table(headers):
            recognized.append(
                Part10TableSummary(
                    table_id=table.xml_id,
                    title=table.title,
                    table_kind="file_meta_information",
                    source_ref=_source_ref(edition, table),
                )
            )
        else:
            warnings.append(
                ParserWarning(
                    part="PS3.10",
                    table_id=table.xml_id,
                    row_index=None,
                    message="unsupported PS3.10 table shape",
                )
            )

    return Part10ParseResult(
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


def _is_file_meta_table(headers: set[str]) -> bool:
    return "attribute" in headers and bool(
        headers & {"type", "description", "tag", "file meta information"}
    )


def _key(value: str) -> str:
    return normalize_text(value).lower()


def _source_ref(edition: str, table: ParsedTable) -> SourceRef:
    table_id = table.xml_id or "unknown"
    return SourceRef(
        id=f"{edition}.PS3.10.{table_id}",
        edition_id=edition,
        part="PS3.10",
        section=table.parent_xml_id,
        table_id=table_id,
        xml_id=table.xml_id,
        title=table.title,
    )
