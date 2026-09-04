"""Parser scaffold for PS3.5 encoding tables."""

from __future__ import annotations

from dataclasses import dataclass

from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.tables import ParsedRow, ParsedTable
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.ir.models import (
    ParserWarning,
    SourceRef,
    TransferSyntaxDetail,
    UIDRegistryEntry,
    VRDefinition,
)


@dataclass(frozen=True)
class Part05TableSummary:
    """A recognized PS3.5 table with bounded parser diagnostics."""

    table_id: str | None
    title: str | None
    table_kind: str
    source_ref: SourceRef


@dataclass(frozen=True)
class Part05ParseResult:
    """Parsed PS3.5 scaffold metadata and parser gap warnings."""

    recognized_tables: tuple[Part05TableSummary, ...]
    vr_definitions: tuple[VRDefinition, ...]
    warnings: tuple[ParserWarning, ...]


def parse_part05(document: ParsedDocument, *, edition: str) -> Part05ParseResult:
    """Parse deterministic PS3.5 value representation definitions."""
    recognized: list[Part05TableSummary] = []
    vr_definitions: list[VRDefinition] = []
    warnings: list[ParserWarning] = []

    for table in document.tables:
        headers = _headers(table)
        if _is_vr_behavior_table(headers):
            recognized.append(
                Part05TableSummary(
                    table_id=table.xml_id,
                    title=table.title,
                    table_kind="vr_behavior",
                    source_ref=_source_ref(edition, table),
                )
            )
            vr_definitions.extend(
                _parse_vr_definition_table(table, headers, edition, warnings)
            )
        else:
            warnings.append(
                ParserWarning(
                    part="PS3.5",
                    table_id=table.xml_id,
                    row_index=None,
                    message="unsupported PS3.5 table shape",
                )
            )

    return Part05ParseResult(
        recognized_tables=tuple(recognized),
        vr_definitions=tuple(vr_definitions),
        warnings=tuple(warnings),
    )


def transfer_syntax_details_from_uid_registry(
    *,
    edition: str,
    uid_registry_entries: tuple[UIDRegistryEntry, ...],
) -> tuple[TransferSyntaxDetail, ...]:
    """Derive deterministic transfer syntax encoding details from UID rows."""
    records: list[TransferSyntaxDetail] = []
    for entry in uid_registry_entries:
        if _key(entry.uid_type) != "transfer syntax":
            continue
        details = _transfer_syntax_encoding(entry)
        records.append(
            TransferSyntaxDetail(
                id=f"{edition}.transfer_syntax.{entry.uid_value}",
                edition_id=edition,
                uid_registry_entry_id=entry.id,
                uid_value=entry.uid_value,
                explicit_vr=details.explicit_vr,
                endian=details.endian,
                encapsulated=details.encapsulated,
                compression_family=details.compression_family,
                encoding_notes=details.encoding_notes,
                source_ref=entry.source_ref,
            )
        )
    return tuple(records)


@dataclass(frozen=True)
class _TransferSyntaxEncoding:
    explicit_vr: bool | None = None
    endian: str | None = None
    encapsulated: bool | None = None
    compression_family: str | None = None
    encoding_notes: tuple[str, ...] = ()


def _transfer_syntax_encoding(entry: UIDRegistryEntry) -> _TransferSyntaxEncoding:
    name = _key(entry.uid_name)
    keyword = _key(entry.uid_keyword or "")
    combined = f"{name} {keyword}"

    explicit_vr = _explicit_vr(combined)
    endian = _endian(combined)
    compression_family = _compression_family(combined)
    encapsulated = _encapsulated(entry.uid_value, combined, compression_family)
    encoding_notes = _encoding_notes(compression_family, encapsulated)

    return _TransferSyntaxEncoding(
        explicit_vr=explicit_vr,
        endian=endian,
        encapsulated=encapsulated,
        compression_family=compression_family,
        encoding_notes=encoding_notes,
    )


def _explicit_vr(value: str) -> bool | None:
    if "implicit vr" in value:
        return False
    if "explicit vr" in value:
        return True
    return None


def _endian(value: str) -> str | None:
    if "big endian" in value:
        return "big"
    if "little endian" in value:
        return "little"
    return None


def _compression_family(value: str) -> str | None:
    if "deflated" in value:
        return "deflated"
    if "rle" in value or "run length" in value:
        return "rle"
    if "jpeg-ls" in value or "jpegls" in value:
        return "jpeg-ls"
    if "jpeg 2000" in value or "jpeg2000" in value or "htj2k" in value:
        return "jpeg-2000"
    if "jpip" in value:
        return "jpip"
    if "mpeg" in value:
        return "mpeg"
    if "hevc" in value or "h.265" in value or "h265" in value:
        return "hevc"
    if "avc" in value or "h.264" in value or "h264" in value:
        return "avc"
    if "jpeg xl" in value or "jpegxl" in value:
        return "jpeg-xl"
    if "jpeg" in value:
        return "jpeg"
    return None


def _encapsulated(
    uid_value: str, value: str, compression_family: str | None
) -> bool | None:
    if uid_value in {
        "1.2.840.10008.1.2",
        "1.2.840.10008.1.2.1",
        "1.2.840.10008.1.2.1.99",
        "1.2.840.10008.1.2.2",
    }:
        return False
    if compression_family is None:
        return None
    return "deflated" not in value


def _encoding_notes(
    compression_family: str | None, encapsulated: bool | None
) -> tuple[str, ...]:
    notes: list[str] = []
    if compression_family == "deflated":
        notes.append("deflated dataset encoding")
    elif compression_family is not None:
        notes.append(f"{compression_family} compressed transfer syntax")
    if encapsulated is True:
        notes.append("encapsulated pixel data")
    return tuple(notes)


def _headers(table: ParsedTable) -> dict[str, int]:
    for row in table.rows:
        if row.section == "thead":
            return {_key(cell.text): cell.column for cell in row.cells}
    if not table.rows:
        return {}
    return {_key(cell.text): cell.column for cell in table.rows[0].cells}


def _is_vr_behavior_table(headers: dict[str, int]) -> bool:
    if "vr name" in headers and {
        "definition",
        "character repertoire",
        "length of value",
    } <= set(headers):
        return True
    return "vr" in headers and bool(
        headers.keys() & {"behavior", "description", "name", "value representation"}
    )


def _parse_vr_definition_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    warnings: list[ParserWarning],
) -> list[VRDefinition]:
    records: list[VRDefinition] = []
    vr_column = _first_header(headers, "vr", "vr name")
    if vr_column is None:
        return records
    for row in _data_rows(table):
        vr_cell = _optional_cell(row, vr_column) or ""
        vr, official_name = _vr_and_name(vr_cell)
        if not _is_vr_code(vr):
            warnings.append(_warning(table, row, "skipped malformed VR row"))
            continue

        definition = _optional_cell(row, headers.get("definition"))
        character_repertoire = _optional_cell(row, headers.get("character repertoire"))
        name = (
            _optional_cell(row, _first_header(headers, "name", "value representation"))
            or official_name
            or _optional_cell(row, headers.get("description"))
            or vr
        )
        behavior_text = " ".join(
            value
            for value in (
                _optional_cell(
                    row, _first_header(headers, "binary or text", "behavior")
                ),
                definition,
                character_repertoire,
            )
            if value
        )
        records.append(
            VRDefinition(
                id=f"{edition}.PS3.5.vr.{vr}",
                edition_id=edition,
                vr=vr,
                name=name,
                value_representation_class=_optional_cell(
                    row, _first_header(headers, "value representation class", "class")
                ),
                length_notes=_optional_cells(
                    row,
                    _first_header(
                        headers,
                        "length notes",
                        "length",
                        "length of value",
                    ),
                ),
                padding_behavior=_optional_cell(
                    row, _first_header(headers, "padding behavior", "padding")
                ),
                character_repertoire_notes=(
                    (character_repertoire,)
                    if character_repertoire is not None
                    else _optional_cells(
                        row,
                        _first_header(
                            headers,
                            "character repertoire notes",
                            "character repertoire",
                        ),
                    )
                ),
                binary_or_text=_binary_or_text(behavior_text),
                source_ref=_source_ref(edition, table),
            )
        )
    warnings.extend(_duplicate_warnings(records))
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


def _optional_cells(row: ParsedRow, column: int | None) -> tuple[str, ...]:
    value = _optional_cell(row, column)
    return (value,) if value is not None else ()


def _first_header(headers: dict[str, int], *names: str) -> int | None:
    for name in names:
        column = headers.get(name)
        if column is not None:
            return column
    return None


def _vr_and_name(value: str) -> tuple[str, str | None]:
    normalized = normalize_text(value)
    if len(normalized) < 2:
        return normalized.upper(), None
    vr = normalized[:2].upper()
    name = normalize_text(normalized[2:])
    return vr, name or None


def _key(value: str) -> str:
    return normalize_text(value).lower()


def _is_vr_code(value: str) -> bool:
    return len(value) == 2 and value.isalpha() and value.isupper()


def _binary_or_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.lower()
    if "binary" in normalized:
        return "binary"
    if "text" in normalized or "character" in normalized or "string" in normalized:
        return "text"
    return None


def _source_ref(edition: str, table: ParsedTable) -> SourceRef:
    table_id = table.xml_id or "unknown"
    return SourceRef(
        id=f"{edition}.PS3.5.{table_id}",
        edition_id=edition,
        part="PS3.5",
        section=table.parent_xml_id,
        table_id=table_id,
        xml_id=table.xml_id,
        title=table.title,
    )


def _warning(table: ParsedTable, row: ParsedRow, message: str) -> ParserWarning:
    return ParserWarning(
        part="PS3.5",
        table_id=table.xml_id,
        row_index=row.row_index,
        message=message,
    )


def _duplicate_warnings(records: list[VRDefinition]) -> list[ParserWarning]:
    seen: set[str] = set()
    warnings: list[ParserWarning] = []
    for record in records:
        if record.vr in seen:
            warnings.append(
                ParserWarning(
                    part="PS3.5",
                    table_id=record.source_ref.table_id,
                    row_index=None,
                    message=f"duplicate VR definition for {record.vr}",
                )
            )
        seen.add(record.vr)
    return warnings
