"""Parser scaffold for PS3.10 media storage and file format tables."""

from __future__ import annotations

import re
from dataclasses import dataclass

from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.tables import ParsedRow, ParsedTable
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.ir.models import (
    DicomMediaType,
    FileMetaRequirement,
    ParserWarning,
    SourceRef,
)
from dicom_kb.ir.validators import IdentifierValidationError, normalize_tag


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
    file_meta_requirements: tuple[FileMetaRequirement, ...]
    media_types: tuple[DicomMediaType, ...]
    warnings: tuple[ParserWarning, ...]


def parse_part10(document: ParsedDocument, *, edition: str) -> Part10ParseResult:
    """Classify PS3.10 tables without exposing public media-storage facts yet."""
    recognized: list[Part10TableSummary] = []
    file_meta_requirements: list[FileMetaRequirement] = []
    media_types: list[DicomMediaType] = []
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
            file_meta_requirements.extend(
                _parse_file_meta_requirement_table(table, headers, edition, warnings)
            )
        elif _is_media_type_table(headers):
            recognized.append(
                Part10TableSummary(
                    table_id=table.xml_id,
                    title=table.title,
                    table_kind="media_type",
                    source_ref=_source_ref(edition, table),
                )
            )
            media_types.extend(
                _parse_media_type_table(table, headers, edition, warnings)
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
        file_meta_requirements=tuple(file_meta_requirements),
        media_types=tuple(media_types),
        warnings=tuple(warnings),
    )


def _headers(table: ParsedTable) -> dict[str, int]:
    for row in table.rows:
        if row.section == "thead":
            return {_key(cell.text): cell.column for cell in row.cells}
    if not table.rows:
        return {}
    return {_key(cell.text): cell.column for cell in table.rows[0].cells}


def _is_file_meta_table(headers: dict[str, int]) -> bool:
    return bool(headers.keys() & {"attribute", "attribute name"}) and bool(
        headers.keys() & {"type", "description", "tag", "file meta information"}
    )


def _is_media_type_table(headers: dict[str, int]) -> bool:
    return "media type" in headers and bool(
        headers.keys() & {"service context", "context"}
    )


def _parse_file_meta_requirement_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    warnings: list[ParserWarning],
) -> list[FileMetaRequirement]:
    records: list[FileMetaRequirement] = []
    attribute_column = _first_header(headers, "attribute", "attribute name")
    tag_column = headers.get("tag")
    type_column = headers.get("type")
    if attribute_column is None or tag_column is None or type_column is None:
        warnings.append(
            ParserWarning(
                part="PS3.10",
                table_id=table.xml_id,
                row_index=None,
                message="skipped file meta table without attribute, tag, and type",
            )
        )
        return records

    for row in _data_rows(table):
        try:
            tag = normalize_tag(_cell(row, tag_column))
        except IdentifierValidationError as exc:
            warnings.append(_warning(table, row, f"skipped malformed tag row: {exc}"))
            continue

        attribute_name = _cell(row, attribute_column)
        type_designation = _cell(row, type_column)
        if not attribute_name or not type_designation:
            warnings.append(_warning(table, row, "skipped incomplete file meta row"))
            continue

        keyword = _optional_cell(row, headers.get("keyword"))
        records.append(
            FileMetaRequirement(
                id=f"{edition}.PS3.10.file_meta.{tag}",
                edition_id=edition,
                attribute_tag=tag,
                attribute_keyword=keyword,
                type_designation=type_designation,
                rule_context="file_meta_information",
                source_ref=_source_ref(edition, table),
            )
        )
    return records


def _parse_media_type_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    warnings: list[ParserWarning],
) -> list[DicomMediaType]:
    records: list[DicomMediaType] = []
    media_type_column = headers.get("media type")
    context_column = _first_header(headers, "service context", "context")
    if media_type_column is None or context_column is None:
        warnings.append(
            ParserWarning(
                part="PS3.10",
                table_id=table.xml_id,
                row_index=None,
                message="skipped media type table without media type and context",
            )
        )
        return records

    constraints_column = _first_header(
        headers,
        "transfer syntax constraints",
        "transfer syntax constraint",
        "constraints",
    )
    directions_column = _first_header(headers, "direction", "directions")
    for row in _data_rows(table):
        media_type = _cell(row, media_type_column)
        service_context = _cell(row, context_column)
        if not media_type or not service_context:
            warnings.append(_warning(table, row, "skipped incomplete media type row"))
            continue

        constraints = _optional_tuple(row, constraints_column)
        directions = tuple(
            part.lower() for part in _optional_tuple(row, directions_column)
        )
        records.append(
            DicomMediaType(
                id=(
                    f"{edition}.PS3.10.media_type."
                    f"{_identifier_fragment(service_context)}."
                    f"{_identifier_fragment(media_type)}"
                ),
                edition_id=edition,
                media_type=media_type,
                service_context=service_context,
                transfer_syntax_constraints=constraints,
                directions=directions,
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


def _optional_tuple(row: ParsedRow, column: int | None) -> tuple[str, ...]:
    value = _optional_cell(row, column)
    if value is None:
        return ()
    return tuple(part.strip() for part in value.split(";") if part.strip())


def _first_header(headers: dict[str, int], *names: str) -> int | None:
    for name in names:
        if name in headers:
            return headers[name]
    return None


def _key(value: str) -> str:
    return normalize_text(value).lower()


def _identifier_fragment(value: str) -> str:
    normalized = normalize_text(value).lower().replace("+", "_plus_")
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")


def _warning(table: ParsedTable, row: ParsedRow, message: str) -> ParserWarning:
    return ParserWarning(
        part="PS3.10",
        table_id=table.xml_id,
        row_index=row.row_index,
        message=message,
    )


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
