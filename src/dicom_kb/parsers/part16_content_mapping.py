"""Parser scaffold for PS3.16 content mapping tables."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.tables import ParsedRow, ParsedTable
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.ir.models import (
    CodedConcept,
    ContextGroup,
    ContextGroupRow,
    ParserWarning,
    SourceRef,
    SRTemplate,
    SRTemplateRow,
)


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
    sr_templates: tuple[SRTemplate, ...]
    sr_template_rows: tuple[SRTemplateRow, ...]
    context_groups: tuple[ContextGroup, ...]
    context_group_rows: tuple[ContextGroupRow, ...]
    coded_concepts: tuple[CodedConcept, ...]
    warnings: tuple[ParserWarning, ...]


def parse_part16(document: ParsedDocument, *, edition: str) -> Part16ParseResult:
    """Parse supported PS3.16 content mapping tables and report parser gaps."""
    recognized: list[Part16TableSummary] = []
    templates: dict[str, SRTemplate] = {}
    template_rows: list[SRTemplateRow] = []
    context_groups: dict[str, ContextGroup] = {}
    context_group_rows: list[ContextGroupRow] = []
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
            parsed_templates, parsed_template_rows = _parse_sr_template_table(
                table, headers, edition, warnings
            )
            for template in parsed_templates:
                templates[template.id] = template
            template_rows.extend(parsed_template_rows)
        elif _is_context_group_table(headers):
            recognized.append(
                Part16TableSummary(
                    table_id=table.xml_id,
                    title=table.title,
                    table_kind="context_group",
                    source_ref=_source_ref(edition, table),
                )
            )
            parsed_groups, parsed_group_rows = _parse_context_group_table(
                table, headers, edition, warnings
            )
            for group in parsed_groups:
                context_groups[group.id] = group
            context_group_rows.extend(parsed_group_rows)
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
        sr_templates=tuple(templates.values()),
        sr_template_rows=tuple(template_rows),
        context_groups=tuple(context_groups.values()),
        context_group_rows=tuple(context_group_rows),
        coded_concepts=coded_concepts_from_context_group_rows(context_group_rows),
        warnings=tuple(warnings),
    )


def coded_concepts_from_context_group_rows(
    rows: Iterable[ContextGroupRow],
) -> tuple[CodedConcept, ...]:
    """Derive unique coded concepts from complete PS3.16 context group rows."""
    concepts: dict[tuple[str, str, str, str], CodedConcept] = {}
    for row in rows:
        if (
            row.code_value is None
            or row.coding_scheme_designator is None
            or row.code_meaning is None
        ):
            continue
        scheme_version = row.coding_scheme_version or ""
        key = (
            row.edition_id,
            row.code_value,
            row.coding_scheme_designator,
            scheme_version,
        )
        concepts.setdefault(
            key,
            CodedConcept(
                id=_coded_concept_id(
                    edition=row.edition_id,
                    code_value=row.code_value,
                    coding_scheme_designator=row.coding_scheme_designator,
                    coding_scheme_version=scheme_version,
                ),
                edition_id=row.edition_id,
                code_value=row.code_value,
                coding_scheme_designator=row.coding_scheme_designator,
                coding_scheme_version=scheme_version,
                code_meaning=row.code_meaning,
                source_ref=row.source_ref,
            ),
        )
    return tuple(concepts.values())


def _headers(table: ParsedTable) -> dict[str, int]:
    for row in table.rows:
        if row.section == "thead":
            return {_key(cell.text): cell.column for cell in row.cells}
    if not table.rows:
        return {}
    return {_key(cell.text): cell.column for cell in table.rows[0].cells}


def _is_sr_template_table(headers: dict[str, int]) -> bool:
    return "tid" in headers and bool(
        headers.keys() & {"name", "template name", "template", "extensibility"}
    )


def _is_context_group_table(headers: dict[str, int]) -> bool:
    return "cid" in headers and bool(
        headers.keys()
        & {
            "name",
            "context group name",
            "context group",
            "code value",
            "code meaning",
        }
    )


def _parse_sr_template_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    warnings: list[ParserWarning],
) -> tuple[list[SRTemplate], list[SRTemplateRow]]:
    templates: dict[str, SRTemplate] = {}
    template_rows: list[SRTemplateRow] = []
    tid_column = headers.get("tid")
    name_column = _first_header(headers, "name", "template name", "template")
    if tid_column is None or name_column is None:
        warnings.append(
            ParserWarning(
                part="PS3.16",
                table_id=table.xml_id,
                row_index=None,
                message="skipped SR template table without TID and name",
            )
        )
        return [], []

    row_column = _first_header(headers, "row", "row order", "nl")
    extensibility_column = _first_header(headers, "extensibility")
    relationship_column = _first_header(
        headers,
        "relationship type",
        "relationship",
        "rel with parent",
        "rel",
    )
    value_type_column = _first_header(headers, "value type", "vt")
    concept_name_column = _first_header(headers, "concept name")
    cardinality_column = _first_header(headers, "cardinality", "vm")
    condition_column = _first_header(headers, "condition", "condition text")
    include_column = _first_header(headers, "include tid", "included tid", "include")

    row_count_by_template: dict[str, int] = {}
    for row in _data_rows(table):
        tid = _normalize_tid(_cell(row, tid_column))
        name = _cell(row, name_column)
        if tid is None or not name:
            warnings.append(_warning(table, row, "skipped incomplete SR template row"))
            continue

        template_id = f"{edition}.PS3.16.sr_template.{_identifier_fragment(tid)}"
        templates.setdefault(
            template_id,
            SRTemplate(
                id=template_id,
                edition_id=edition,
                tid=tid,
                name=name,
                extensibility=_optional_cell(row, extensibility_column),
                source_ref=_source_ref(edition, table),
            ),
        )

        row_count_by_template[template_id] = row_count_by_template.get(
            template_id, 0
        ) + 1
        row_order = _row_order(row, row_column) or row_count_by_template[template_id]
        template_rows.append(
            SRTemplateRow(
                id=f"{template_id}.row.{row_order}",
                edition_id=edition,
                sr_template_id=template_id,
                row_order=row_order,
                relationship_type=_optional_cell(row, relationship_column),
                value_type=_optional_cell(row, value_type_column),
                concept_name=_optional_cell(row, concept_name_column),
                cardinality=_optional_cell(row, cardinality_column),
                condition_text=_optional_cell(row, condition_column),
                include_tid=_normalize_tid(_optional_cell(row, include_column)),
                source_ref=_source_ref(edition, table),
            )
        )

    return list(templates.values()), template_rows


def _parse_context_group_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    warnings: list[ParserWarning],
) -> tuple[list[ContextGroup], list[ContextGroupRow]]:
    groups: dict[str, ContextGroup] = {}
    group_rows: list[ContextGroupRow] = []
    cid_column = headers.get("cid")
    name_column = _first_header(headers, "name", "context group name", "context group")
    if cid_column is None or name_column is None:
        warnings.append(
            ParserWarning(
                part="PS3.16",
                table_id=table.xml_id,
                row_index=None,
                message="skipped context group table without CID and name",
            )
        )
        return [], []

    row_column = _first_header(headers, "row", "row order")
    extensibility_column = _first_header(headers, "extensibility")
    version_column = _first_header(headers, "version")
    scheme_column = _first_header(
        headers,
        "coding scheme designator",
        "scheme",
        "coding scheme",
    )
    scheme_version_column = _first_header(
        headers,
        "coding scheme version",
        "scheme version",
    )
    code_value_column = _first_header(headers, "code value", "code")
    code_meaning_column = _first_header(headers, "code meaning", "meaning")
    include_column = _first_header(headers, "include cid", "included cid", "include")

    row_count_by_group: dict[str, int] = {}
    for row in _data_rows(table):
        cid = _normalize_cid(_cell(row, cid_column))
        name = _cell(row, name_column)
        if cid is None or not name:
            warnings.append(
                _warning(table, row, "skipped incomplete context group row")
            )
            continue

        group_id = f"{edition}.PS3.16.context_group.{_identifier_fragment(cid)}"
        groups.setdefault(
            group_id,
            ContextGroup(
                id=group_id,
                edition_id=edition,
                cid=cid,
                name=name,
                extensibility=_optional_cell(row, extensibility_column),
                version=_optional_cell(row, version_column),
                source_ref=_source_ref(edition, table),
            ),
        )

        row_count_by_group[group_id] = row_count_by_group.get(group_id, 0) + 1
        row_order = _row_order(row, row_column) or row_count_by_group[group_id]
        group_rows.append(
            ContextGroupRow(
                id=f"{group_id}.row.{row_order}",
                edition_id=edition,
                context_group_id=group_id,
                row_order=row_order,
                coding_scheme_designator=_optional_cell(row, scheme_column),
                coding_scheme_version=_optional_cell(row, scheme_version_column),
                code_value=_optional_cell(row, code_value_column),
                code_meaning=_optional_cell(row, code_meaning_column),
                include_cid=_normalize_cid(_optional_cell(row, include_column)),
                source_ref=_source_ref(edition, table),
            )
        )

    return list(groups.values()), group_rows


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


def _row_order(row: ParsedRow, column: int | None) -> int | None:
    value = _optional_cell(row, column)
    if value is None:
        return None
    match = re.search(r"\d+", value)
    if match is None:
        return None
    return int(match.group(0))


def _normalize_tid(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_text(value)
    if not normalized:
        return None
    if normalized.upper().startswith("TID "):
        return f"TID {normalized[4:].strip()}"
    if normalized.isdigit():
        return f"TID {normalized}"
    return normalized


def _normalize_cid(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_text(value)
    if not normalized:
        return None
    if normalized.upper().startswith("CID "):
        return f"CID {normalized[4:].strip()}"
    if normalized.isdigit():
        return f"CID {normalized}"
    return normalized


def _first_header(headers: dict[str, int], *names: str) -> int | None:
    for name in names:
        if name in headers:
            return headers[name]
    return None


def _key(value: str) -> str:
    return normalize_text(value).lower()


def _identifier_fragment(value: str) -> str:
    normalized = normalize_text(value).lower()
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")


def _coded_concept_id(
    *,
    edition: str,
    code_value: str,
    coding_scheme_designator: str,
    coding_scheme_version: str,
) -> str:
    parts = [
        edition,
        "PS3.16",
        "coded_concept",
        _identifier_fragment(coding_scheme_designator),
        _identifier_fragment(code_value),
    ]
    if coding_scheme_version:
        parts.append(_identifier_fragment(coding_scheme_version))
    return ".".join(parts)


def _warning(table: ParsedTable, row: ParsedRow, message: str) -> ParserWarning:
    return ParserWarning(
        part="PS3.16",
        table_id=table.xml_id,
        row_index=row.row_index,
        message=message,
    )


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
