"""Parse PS3.16 templates (TID), context groups (CID) and DCM definitions."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from dicom_kb.docbook.parser import ParsedDocument, ParsedSection
from dicom_kb.docbook.tables import ParsedCell, ParsedRow, ParsedTable
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

# PS3.16 Annex D lists the DCM codes, each with its definition. It is the only
# table with these columns and no coding scheme column; finding it by shape
# survives a renumbering of the annex.
_DCM_DEFINITION_HEADERS = {"code value", "code meaning", "definition"}


@dataclass(frozen=True)
class Part16ParseResult:
    """Parsed PS3.16 templates, context groups, codes and parser warnings."""

    sr_templates: tuple[SRTemplate, ...]
    sr_template_rows: tuple[SRTemplateRow, ...]
    context_groups: tuple[ContextGroup, ...]
    context_group_rows: tuple[ContextGroupRow, ...]
    coded_concepts: tuple[CodedConcept, ...]
    warnings: tuple[ParserWarning, ...]


@dataclass(frozen=True)
class _TableMetadata:
    identifier: str | None
    name: str | None
    extensibility: str | None = None
    version: str | None = None


def parse_part16(document: ParsedDocument, *, edition: str) -> Part16ParseResult:
    """Parse supported PS3.16 content mapping tables and report parser gaps."""
    templates: dict[str, SRTemplate] = {}
    template_rows: list[SRTemplateRow] = []
    context_groups: dict[str, ContextGroup] = {}
    context_group_rows: list[ContextGroupRow] = []
    row_counts: dict[str, int] = {}
    sections_by_id = {
        section.xml_id: section
        for section in document.sections
        if section.xml_id is not None
    }

    dcm_definitions: list[CodedConcept] = []
    for table in document.tables:
        headers = _headers(table)
        if _is_dcm_definitions_table(headers):
            dcm_definitions = _parse_dcm_definitions(table, headers, edition)
        elif _is_sr_template_table(table, headers, sections_by_id):
            template, rows = _parse_sr_template_table(
                table, headers, edition, sections_by_id, row_counts
            )
            templates.setdefault(template.id, template)
            template_rows.extend(rows)
        elif _is_context_group_table(table, headers, sections_by_id):
            group, group_rows = _parse_context_group_table(
                table, headers, edition, sections_by_id, row_counts
            )
            context_groups.setdefault(group.id, group)
            context_group_rows.extend(group_rows)
        # Every other table (TID parameters, annex examples, ...) is read as
        # text through doc_node, so it is not a gap.

    return Part16ParseResult(
        sr_templates=tuple(templates.values()),
        sr_template_rows=tuple(template_rows),
        context_groups=tuple(context_groups.values()),
        context_group_rows=tuple(context_group_rows),
        coded_concepts=_with_definitions(
            coded_concepts_from_context_group_rows(context_group_rows),
            dcm_definitions,
        ),
        warnings=(),
    )


def _parse_dcm_definitions(
    table: ParsedTable, headers: dict[str, int], edition: str
) -> list[CodedConcept]:
    """Read the DCM codes and their definitions from Annex D."""
    value_column = headers["code value"]
    meaning_column = headers["code meaning"]
    concepts = []
    for row in _data_rows(table):
        value = normalize_text(_cell(row, value_column))
        meaning = normalize_text(_cell(row, meaning_column))
        if not value or not meaning:
            continue
        concepts.append(
            CodedConcept(
                id=_coded_concept_id(
                    edition=edition,
                    code_value=value,
                    coding_scheme_designator="DCM",
                    coding_scheme_version="",
                ),
                edition_id=edition,
                code_value=value,
                coding_scheme_designator="DCM",
                code_meaning=meaning,
                definition=_optional_cell(row, headers.get("definition")),
                notes=_optional_cell(row, headers.get("notes")),
                source_ref=_source_ref(edition, table),
            )
        )
    return concepts


def _with_definitions(
    concepts: tuple[CodedConcept, ...], definitions: list[CodedConcept]
) -> tuple[CodedConcept, ...]:
    """Add Table D-1 definitions to DCM concepts, and the codes no CID lists."""
    by_key = {
        (concept.code_value, concept.coding_scheme_designator): index
        for index, concept in enumerate(concepts)
        if not concept.coding_scheme_version
    }
    merged = list(concepts)
    for definition in definitions:
        index = by_key.get((definition.code_value, "DCM"))
        if index is None:
            by_key[(definition.code_value, "DCM")] = len(merged)
            merged.append(definition)
        else:
            merged[index] = merged[index].model_copy(
                update={"definition": definition.definition, "notes": definition.notes}
            )
    return tuple(merged)


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


def _is_dcm_definitions_table(headers: dict[str, int]) -> bool:
    return set(headers) >= _DCM_DEFINITION_HEADERS and (
        "coding scheme designator" not in headers
    )


def _is_sr_template_table(
    table: ParsedTable,
    headers: dict[str, int],
    sections_by_id: dict[str, ParsedSection],
) -> bool:
    return {"nl", "vt", "concept name"} <= set(headers) and _metadata_from_context(
        table, sections_by_id, prefix="TID", normalizer=_normalize_tid
    ).identifier is not None


def _is_context_group_table(
    table: ParsedTable,
    headers: dict[str, int],
    sections_by_id: dict[str, ParsedSection],
) -> bool:
    return {"coding scheme designator", "code value", "code meaning"} <= set(
        headers
    ) and _metadata_from_context(
        table, sections_by_id, prefix="CID", normalizer=_normalize_cid
    ).identifier is not None


def _parse_sr_template_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    sections_by_id: dict[str, ParsedSection],
    row_counts: dict[str, int],
) -> tuple[SRTemplate, list[SRTemplateRow]]:
    metadata = _metadata_from_context(
        table, sections_by_id, prefix="TID", normalizer=_normalize_tid
    )
    assert metadata.identifier is not None
    tid = metadata.identifier
    template_id = f"{edition}.PS3.16.sr_template.{_identifier_fragment(tid)}"
    template = SRTemplate(
        id=template_id,
        edition_id=edition,
        tid=tid,
        name=metadata.name or tid,
        extensibility=metadata.extensibility,
        source_ref=_source_ref(edition, table),
    )
    relationship_column = _first_header(headers, "rel with parent", "rel")
    value_type_column = headers["vt"]
    concept_name_column = headers["concept name"]
    cardinality_column = _first_header(headers, "vm")
    condition_column = _first_header(headers, "condition")

    template_rows: list[SRTemplateRow] = []
    for row in _data_rows(table):
        # Count across tables: a template split over two tables keeps going.
        row_order = row_counts[template_id] = row_counts.get(template_id, 0) + 1
        value_type = _optional_cell(row, value_type_column)
        include_tid = None
        if value_type is not None and value_type.upper() == "INCLUDE":
            include_tid = _sr_template_include_target(row)
        template_rows.append(
            SRTemplateRow(
                id=f"{template_id}.row.{row_order}",
                edition_id=edition,
                sr_template_id=template_id,
                row_order=row_order,
                relationship_type=_optional_cell(row, relationship_column),
                value_type=value_type,
                concept_name=_sr_template_concept_name(
                    row, concept_name_column, sections_by_id
                ),
                cardinality=_optional_cell(row, cardinality_column),
                condition_text=_optional_cell(row, condition_column),
                include_tid=include_tid,
                source_ref=_source_ref(edition, table),
            )
        )
    return template, template_rows


def _parse_context_group_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    sections_by_id: dict[str, ParsedSection],
    row_counts: dict[str, int],
) -> tuple[ContextGroup, list[ContextGroupRow]]:
    metadata = _metadata_from_context(
        table, sections_by_id, prefix="CID", normalizer=_normalize_cid
    )
    assert metadata.identifier is not None
    cid = metadata.identifier
    group_id = f"{edition}.PS3.16.context_group.{_identifier_fragment(cid)}"
    group = ContextGroup(
        id=group_id,
        edition_id=edition,
        cid=cid,
        name=metadata.name or cid,
        extensibility=metadata.extensibility,
        version=metadata.version,
        source_ref=_source_ref(edition, table),
    )
    scheme_column = headers["coding scheme designator"]
    scheme_version_column = _first_header(headers, "coding scheme version")
    code_value_column = headers["code value"]
    code_meaning_column = headers["code meaning"]

    group_rows: list[ContextGroupRow] = []
    for row in _body_rows(table):
        row_order = row_counts[group_id] = row_counts.get(group_id, 0) + 1
        include_cid = _context_group_include_target(row)
        # An include row carries no code of its own.
        scheme, scheme_version, code_value, code_meaning = (
            (None, None, None, None)
            if include_cid
            else (
                _optional_cell(row, scheme_column),
                _optional_cell(row, scheme_version_column),
                _optional_cell(row, code_value_column),
                _optional_cell(row, code_meaning_column),
            )
        )
        group_rows.append(
            ContextGroupRow(
                id=f"{group_id}.row.{row_order}",
                edition_id=edition,
                context_group_id=group_id,
                row_order=row_order,
                coding_scheme_designator=scheme,
                coding_scheme_version=scheme_version,
                code_value=code_value,
                code_meaning=code_meaning,
                include_cid=include_cid,
                source_ref=_source_ref(edition, table),
            )
        )
    return group, group_rows


def _data_rows(table: ParsedTable) -> list[ParsedRow]:
    return [
        row for row in table.rows if row.section != "thead" and row.row_kind == "data"
    ]


def _body_rows(table: ParsedTable) -> list[ParsedRow]:
    return [row for row in table.rows if row.section != "thead"]


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


def _cell_at(row: ParsedRow, column: int | None) -> ParsedCell | None:
    if column is None:
        return None
    for cell in row.cells:
        if cell.column == column:
            return cell
    return None


def _sr_template_concept_name(
    row: ParsedRow,
    column: int | None,
    sections_by_id: dict[str, ParsedSection],
) -> str | None:
    cell = _cell_at(row, column)
    if cell is None:
        return None
    value = normalize_text(cell.text)
    if not _is_compact_concept_marker(value):
        return value or None
    for target in cell.xrefs:
        label = _xref_label(target, sections_by_id)
        if label is not None:
            return label
    return value or None


def _is_compact_concept_marker(value: str) -> bool:
    normalized = normalize_text(value).lower()
    return normalized in {"", "d", "b", "null"}


def _xref_label(
    target: str,
    sections_by_id: dict[str, ParsedSection],
) -> str | None:
    section = sections_by_id.get(target)
    if section is None:
        return None
    title = normalize_text(section.title or "")
    return title or None


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


def _metadata_from_context(
    table: ParsedTable,
    sections_by_id: dict[str, ParsedSection],
    *,
    prefix: str,
    normalizer: Callable[[str | None], str | None],
) -> _TableMetadata:
    title = table.title or ""
    section = sections_by_id.get(table.parent_xml_id or "")
    section_title = str(getattr(section, "title", "") or "")
    plain_text = str(getattr(section, "plain_text", "") or "")
    identifier, name = _identifier_and_name_from_title(
        title, prefix=prefix, normalizer=normalizer
    )
    if identifier is None:
        identifier, name = _identifier_and_name_from_title(
            section_title, prefix=prefix, normalizer=normalizer
        )
    if identifier is None:
        identifier = _identifier_from_id(
            table.xml_id, prefix=prefix, normalizer=normalizer
        )
        name = name or table.title or section_title or None
    if identifier is None:
        identifier = _identifier_from_id(
            table.parent_xml_id, prefix=prefix, normalizer=normalizer
        )
        name = name or table.title or section_title or None
    return _TableMetadata(
        identifier=identifier,
        name=name,
        extensibility=_metadata_value(plain_text, "Type"),
        version=_metadata_value(plain_text, "Version"),
    )


def _identifier_and_name_from_title(
    value: str, *, prefix: str, normalizer: Callable[[str | None], str | None]
) -> tuple[str | None, str | None]:
    pattern = rf"\b{re.escape(prefix)}\s*(?P<number>[0-9A-Za-z]+)\b[.\s:-]*(?P<name>.*)"
    match = re.search(pattern, normalize_text(value), flags=re.IGNORECASE)
    if match is None:
        return None, None
    normalized = normalizer(match.group("number"))
    name = match.group("name").strip(" .:-")
    return normalized, name or None


def _identifier_from_id(
    value: str | None, *, prefix: str, normalizer: Callable[[str | None], str | None]
) -> str | None:
    if value is None:
        return None
    pattern = rf"(?:^|[_-]){re.escape(prefix)}[_-]*(?P<number>[0-9A-Za-z]+)\b"
    match = re.search(pattern, value, flags=re.IGNORECASE)
    if match is None:
        return None
    return normalizer(match.group("number"))


def _metadata_value(text: str, label: str) -> str | None:
    pattern = rf"\b{re.escape(label)}:\s*(?P<value>.*?)(?=\s+[A-Z][A-Za-z ]*:\s|$)"
    match = re.search(pattern, normalize_text(text))
    if match is None:
        return None
    value = match.group("value").strip()
    return value or None


def _find_identifier(value: str | None, *, prefix: str) -> str | None:
    if value is None:
        return None
    match = re.search(
        rf"(?:^|[^A-Za-z0-9]){re.escape(prefix)}[\s_-]*(?P<number>[0-9A-Za-z]+)\b",
        normalize_text(value),
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    if prefix.upper() == "TID":
        return _normalize_tid(match.group("number"))
    if prefix.upper() == "CID":
        return _normalize_cid(match.group("number"))
    return match.group(0)


def _sr_template_include_target(row: ParsedRow) -> str | None:
    targets: list[str] = []
    for cell in row.cells:
        targets.append(cell.text)
        targets.extend(cell.xrefs)
    for target in targets:
        include_tid = _find_identifier(target, prefix="TID")
        if include_tid is not None:
            return include_tid
    return None


def _context_group_include_target(row: ParsedRow) -> str | None:
    """Return the CID an "Include CID n" row pulls in, or None for a code row.

    Only include rows count: a code row whose meaning mentions a CID is
    still a code.
    """
    first_cell = normalize_text(row.cells[0].text) if row.cells else ""
    if row.row_kind != "include" and not first_cell.lower().startswith("include"):
        return None
    targets = [row.include_table_ref or "", row.include_title or ""]
    for cell in row.cells:
        targets.extend(cell.xrefs)
    targets.extend(cell.text for cell in row.cells)
    for target in targets:
        include_cid = _find_identifier(target, prefix="CID")
        if include_cid is not None:
            return include_cid
    return None


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
    digest_input = "|".join(
        (code_value, coding_scheme_designator, coding_scheme_version)
    ).encode("utf-8")
    parts.append(hashlib.sha1(digest_input).hexdigest()[:8])
    return ".".join(parts)


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
