"""Parser for PS3.3 IOD, module, macro, and attribute tables."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.tables import ParsedRow, ParsedTable
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.ir.models import (
    IOD,
    AttributeUse,
    IODFunctionalGroupUse,
    IODModuleUse,
    Macro,
    Module,
    ParserWarning,
    SourceRef,
)
from dicom_kb.ir.validators import IdentifierValidationError, normalize_tag

USAGE_RE = re.compile(r"^(?P<usage>[A-Z0-9]+(?:C)?)\b\s*-?\s*(?P<condition>.*)$")
MODULE_TABLE_TITLE_RE = re.compile(r"^(?P<name>.+?)\s+IOD\s+Modules?$", re.I)
FUNCTIONAL_GROUP_TITLE_RE = re.compile(
    r"^(?P<name>.+?)\s+Functional\s+Group\s+Macros?$", re.I
)
MODULE_ATTR_TITLE_RE = re.compile(r"^(?P<name>.+?)\s+Module\s+Attributes?$", re.I)
MACRO_TITLE_RE = re.compile(r"^(?P<name>.+?\bMacro)\s+Attributes?$", re.I)
DEPTH_RE = re.compile(r"^(?P<marks>>+)\s*(?P<name>.*)$")


@dataclass(frozen=True)
class Part03ParseResult:
    """Parsed PS3.3 graph facts."""

    iods: tuple[IOD, ...]
    modules: tuple[Module, ...]
    macros: tuple[Macro, ...]
    iod_module_uses: tuple[IODModuleUse, ...]
    iod_functional_group_uses: tuple[IODFunctionalGroupUse, ...]
    attribute_uses: tuple[AttributeUse, ...]
    warnings: tuple[ParserWarning, ...]


def parse_part03(document: ParsedDocument, *, edition: str) -> Part03ParseResult:
    """Parse PS3.3 graph records from DocBook table IR."""
    iods: dict[str, IOD] = {}
    modules: dict[str, Module] = {}
    macros: dict[str, Macro] = {}
    module_uses: list[IODModuleUse] = []
    functional_group_uses: list[IODFunctionalGroupUse] = []
    attribute_uses: list[AttributeUse] = []
    warnings: list[ParserWarning] = []

    for table in document.tables:
        if _is_macro_attribute_table(table):
            macro = _macro_from_table(table, edition)
            macros[macro.id] = macro

    macro_by_ref = _macro_ref_index(macros.values())

    for table in document.tables:
        headers = _headers(table)
        if _is_iod_module_table(table, headers):
            iod = _iod_from_table(table, edition)
            iods[iod.id] = iod
            uses, table_modules = _parse_iod_module_table(table, headers, iod, edition)
            module_uses.extend(uses)
            for module in table_modules:
                modules.setdefault(module.id, module)
        elif _is_functional_group_table(headers):
            iod = _iod_from_table(table, edition)
            iods.setdefault(iod.id, iod)
            functional_group_uses.extend(
                _parse_functional_group_table(
                    table, headers, iod, edition, macro_by_ref, warnings
                )
            )
        elif _is_module_attribute_table(table):
            module = _module_from_attribute_table(table, edition)
            modules[module.id] = module
            attribute_uses.extend(
                _parse_attribute_table(
                    table,
                    headers,
                    edition,
                    owner_type="module",
                    owner_id=module.id,
                    macro_by_ref=macro_by_ref,
                    warnings=warnings,
                )
            )
        elif _is_macro_attribute_table(table):
            macro = _macro_from_table(table, edition)
            attribute_uses.extend(
                _parse_attribute_table(
                    table,
                    headers,
                    edition,
                    owner_type="macro",
                    owner_id=macro.id,
                    macro_by_ref=macro_by_ref,
                    warnings=warnings,
                )
            )

    return Part03ParseResult(
        iods=tuple(iods.values()),
        modules=tuple(modules.values()),
        macros=tuple(macros.values()),
        iod_module_uses=tuple(module_uses),
        iod_functional_group_uses=tuple(functional_group_uses),
        attribute_uses=tuple(attribute_uses),
        warnings=tuple(warnings),
    )


def _headers(table: ParsedTable) -> dict[str, int]:
    for row in table.rows:
        if row.section == "thead":
            return {_key(cell.text): cell.column for cell in row.cells}
    if not table.rows:
        return {}
    return {_key(cell.text): cell.column for cell in table.rows[0].cells}


def _is_iod_module_table(table: ParsedTable, headers: dict[str, int]) -> bool:
    return (
        "module" in headers
        and bool(table.title and MODULE_TABLE_TITLE_RE.match(table.title))
        and ("usage" in headers or "reference" in headers)
    )


def _is_functional_group_table(headers: dict[str, int]) -> bool:
    return (
        "functional group macro" in headers
        and "usage" in headers
        and "module" not in headers
    )


def _is_attribute_headers(headers: dict[str, int]) -> bool:
    return "attribute name" in headers and "tag" in headers and "type" in headers


def _is_module_attribute_table(table: ParsedTable) -> bool:
    return bool(
        table.title
        and MODULE_ATTR_TITLE_RE.match(table.title)
        and _is_attribute_headers(_headers(table))
    )


def _is_macro_attribute_table(table: ParsedTable) -> bool:
    return bool(
        table.title
        and MACRO_TITLE_RE.match(table.title)
        and _is_attribute_headers(_headers(table))
    )


def _parse_iod_module_table(
    table: ParsedTable,
    headers: dict[str, int],
    iod: IOD,
    edition: str,
) -> tuple[list[IODModuleUse], list[Module]]:
    source_ref = _source_ref(edition, table)
    uses: list[IODModuleUse] = []
    modules: list[Module] = []
    last_ie: str | None = None
    information_entity_column = _information_entity_column(headers)
    for order, row in enumerate(_data_rows(table)):
        information_entity = _optional_cell(row, information_entity_column)
        if information_entity:
            last_ie = information_entity
        else:
            information_entity = last_ie

        module_name = _cell(row, headers["module"])
        if not module_name:
            continue

        reference = _reference_text(row, headers.get("reference"))
        module = Module(
            id=_id(edition, "module", module_name),
            edition_id=edition,
            name=module_name,
            section=reference,
            description=None,
            source_ref=source_ref,
        )
        modules.append(module)
        usage, condition = (
            _usage(_cell(row, headers["usage"])) if "usage" in headers else ("", None)
        )
        uses.append(
            IODModuleUse(
                id=f"{iod.id}.module_use.{order}",
                edition_id=edition,
                iod_id=iod.id,
                information_entity=information_entity,
                module_id=module.id,
                usage=usage,
                usage_condition_text=condition,
                source_ref=source_ref,
            )
        )
    return uses, modules


def _information_entity_column(headers: dict[str, int]) -> int | None:
    column = headers.get("information entity")
    if column is not None:
        return column
    return headers.get("ie")


def _parse_functional_group_table(
    table: ParsedTable,
    headers: dict[str, int],
    iod: IOD,
    edition: str,
    macro_by_ref: dict[str, Macro],
    warnings: list[ParserWarning],
) -> list[IODFunctionalGroupUse]:
    source_ref = _source_ref(edition, table)
    uses: list[IODFunctionalGroupUse] = []
    for order, row in enumerate(_data_rows(table)):
        macro_text = _cell(row, headers["functional group macro"])
        macro = _macro_for_row(row, macro_text, macro_by_ref)
        if macro is None:
            warnings.append(
                _warning(table, row, f"unresolved functional group: {macro_text}")
            )
            continue
        usage, condition = _usage(_cell(row, headers["usage"]))
        uses.append(
            IODFunctionalGroupUse(
                id=f"{iod.id}.functional_group_use.{order}",
                edition_id=edition,
                iod_id=iod.id,
                macro_id=macro.id,
                usage=usage,
                usage_condition_text=condition,
                source_ref=source_ref,
            )
        )
    return uses


def _parse_attribute_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    *,
    owner_type: str,
    owner_id: str,
    macro_by_ref: dict[str, Macro],
    warnings: list[ParserWarning],
) -> list[AttributeUse]:
    source_ref = _source_ref(edition, table)
    uses: list[AttributeUse] = []
    stack: dict[int, str] = {}
    for order, row in enumerate(_data_rows(table)):
        if row.row_kind == "include":
            macro = _macro_for_row(row, row.include_title, macro_by_ref)
            if macro is None:
                target = row.include_title or row.include_table_ref or _row_text(row)
                warnings.append(
                    _warning(table, row, f"unresolved include row: {target}")
                )
            uses.append(
                AttributeUse(
                    id=f"{owner_id}.attribute_use.{order}",
                    edition_id=edition,
                    owner_type=owner_type,
                    owner_id=owner_id,
                    row_kind="include",
                    included_macro_id=macro.id if macro else None,
                    include_target_text=_row_text(row),
                    row_order=order,
                    source_ref=source_ref,
                )
            )
            continue

        raw_name = _cell(row, headers["attribute name"])
        if not raw_name:
            continue
        sequence_depth, attribute_name = _attribute_depth_and_name(raw_name)
        attribute_id = f"{owner_id}.attribute_use.{order}"
        parent_id = stack.get(sequence_depth - 1) if sequence_depth > 0 else None
        stack[sequence_depth] = attribute_id
        for deeper_depth in [depth for depth in stack if depth > sequence_depth]:
            del stack[deeper_depth]

        uses.append(
            AttributeUse(
                id=attribute_id,
                edition_id=edition,
                owner_type=owner_type,
                owner_id=owner_id,
                parent_attribute_use_id=parent_id,
                row_kind="attribute",
                attribute_tag=_normalized_tag_or_none(_cell(row, headers["tag"])),
                attribute_keyword=None,
                attribute_name=attribute_name,
                type_designation=_cell(row, headers["type"]),
                description_text=_optional_cell(row, _description_column(headers)),
                sequence_depth=sequence_depth,
                row_order=order,
                source_ref=source_ref,
            )
        )
    return uses


def _iod_from_table(table: ParsedTable, edition: str) -> IOD:
    title = table.title or table.xml_id or "Unknown IOD"
    match = MODULE_TABLE_TITLE_RE.match(title) or FUNCTIONAL_GROUP_TITLE_RE.match(title)
    name = match.group("name") if match else title
    return IOD(
        id=_id(edition, "iod", name),
        edition_id=edition,
        name=name,
        keyword=_slug(name),
        iod_type="composite",
        section=table.xml_id,
        source_ref=_source_ref(edition, table),
    )


def _module_from_attribute_table(table: ParsedTable, edition: str) -> Module:
    title = table.title or table.xml_id or "Unknown Module"
    match = MODULE_ATTR_TITLE_RE.match(title)
    name = match.group("name") if match else title
    return Module(
        id=_id(edition, "module", name),
        edition_id=edition,
        name=name,
        section=table.xml_id,
        source_ref=_source_ref(edition, table),
    )


def _macro_from_table(table: ParsedTable, edition: str) -> Macro:
    title = table.title or table.xml_id or "Unknown Macro"
    match = MACRO_TITLE_RE.match(title)
    name = match.group("name") if match else title
    return Macro(
        id=_id(edition, "macro", table.xml_id or name),
        edition_id=edition,
        name=name,
        table_id=table.xml_id,
        section=table.xml_id,
        macro_kind=(
            "functional_group_macro"
            if "functional group" in name.lower()
            else "attribute_macro"
        ),
        source_ref=_source_ref(edition, table),
    )


def _macro_ref_index(macros: Iterable[Macro]) -> dict[str, Macro]:
    index: dict[str, Macro] = {}
    for macro in macros:
        for value in (macro.table_id, macro.name):
            if value:
                index[_ref_key(value)] = macro
    return index


def _macro_for_row(
    row: ParsedRow, text: str | None, macro_by_ref: dict[str, Macro]
) -> Macro | None:
    candidates = [
        row.include_table_ref,
        text,
        *[xref for cell in row.cells for xref in cell.xrefs],
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        macro = macro_by_ref.get(_ref_key(candidate))
        if macro is not None:
            return macro
    return None


def _source_ref(edition: str, table: ParsedTable) -> SourceRef:
    table_id = table.xml_id or "unknown"
    return SourceRef(
        id=f"{edition}.PS3.3.{table_id}",
        edition_id=edition,
        part="PS3.3",
        section=table.parent_xml_id or table.xml_id,
        table_id=table_id,
        xml_id=table.xml_id,
        title=table.title,
    )


def _data_rows(table: ParsedTable) -> list[ParsedRow]:
    return [
        row
        for row in table.rows
        if row.section != "thead" and row.row_kind in {"data", "include"}
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


def _reference_text(row: ParsedRow, column: int | None) -> str | None:
    if column is None:
        return None
    for cell in row.cells:
        if cell.column == column:
            if cell.xrefs:
                return cell.xrefs[0]
            return cell.text or None
    return None


def _description_column(headers: dict[str, int]) -> int | None:
    return headers.get("attribute description") or headers.get("description")


def _usage(value: str) -> tuple[str, str | None]:
    normalized = normalize_text(value)
    match = USAGE_RE.match(normalized)
    if not match:
        return normalized, None
    condition = match.group("condition") or None
    return match.group("usage"), condition


def _attribute_depth_and_name(value: str) -> tuple[int, str]:
    normalized = normalize_text(value)
    match = DEPTH_RE.match(normalized)
    if not match:
        return 0, normalized
    return len(match.group("marks")), normalize_text(match.group("name"))


def _normalized_tag_or_none(value: str) -> str | None:
    if not value:
        return None
    try:
        return normalize_tag(value)
    except IdentifierValidationError:
        return normalize_text(value)


def _key(value: str) -> str:
    return normalize_text(value).lower()


def _row_text(row: ParsedRow) -> str:
    return normalize_text(" ".join(cell.text for cell in row.cells))


def _warning(table: ParsedTable, row: ParsedRow, message: str) -> ParserWarning:
    return ParserWarning(
        part="PS3.3",
        table_id=table.xml_id,
        row_index=row.row_index,
        message=message,
    )


def _id(edition: str, kind: str, value: str) -> str:
    return f"{edition}.{kind}.{_slug(value)}"


def _slug(value: str) -> str:
    normalized = normalize_text(value).lower()
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")


def _ref_key(value: str) -> str:
    normalized = normalize_text(value).lower()
    normalized = normalized.removeprefix("table_").removeprefix("table ")
    return normalized.replace("_", "-").strip()
