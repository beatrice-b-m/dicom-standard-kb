"""Parser scaffold for PS3.18 web services tables."""

from __future__ import annotations

import re
from dataclasses import dataclass

from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.tables import ParsedRow, ParsedTable
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.ir.models import (
    DicomMediaType,
    DicomwebTransaction,
    ParserWarning,
    SourceRef,
)


@dataclass(frozen=True)
class Part18TableSummary:
    """A recognized PS3.18 table and its source reference."""

    table_id: str | None
    title: str | None
    table_kind: str
    source_ref: SourceRef


@dataclass(frozen=True)
class Part18ParseResult:
    """Parsed PS3.18 scaffold metadata and parser gap warnings."""

    recognized_tables: tuple[Part18TableSummary, ...]
    dicomweb_transactions: tuple[DicomwebTransaction, ...]
    media_types: tuple[DicomMediaType, ...]
    warnings: tuple[ParserWarning, ...]


@dataclass(frozen=True)
class _TransactionOverview:
    transaction_name: str
    http_method: str
    request_payload: str | None
    response_payload: str | None
    description: str | None


def parse_part18(document: ParsedDocument, *, edition: str) -> Part18ParseResult:
    """Parse supported PS3.18 web-service tables and report parser gaps."""
    recognized: list[Part18TableSummary] = []
    transactions: list[DicomwebTransaction] = []
    media_types: list[DicomMediaType] = []
    warnings: list[ParserWarning] = []
    official_overviews = _official_transaction_overviews(document)

    for table in document.tables:
        headers = _headers(table)
        header_names = _header_names_by_column(table)
        if _is_dicomweb_transaction_table(headers):
            recognized.append(
                Part18TableSummary(
                    table_id=table.xml_id,
                    title=table.title,
                    table_kind="dicomweb_transaction",
                    source_ref=_source_ref(edition, table),
                )
            )
            transactions.extend(
                _parse_dicomweb_transaction_table(table, headers, edition, warnings)
            )
        elif _is_official_transaction_overview_table(header_names):
            recognized.append(
                Part18TableSummary(
                    table_id=table.xml_id,
                    title=table.title,
                    table_kind="dicomweb_transaction_overview",
                    source_ref=_source_ref(edition, table),
                )
            )
        elif _is_official_transaction_resource_table(table, header_names):
            recognized.append(
                Part18TableSummary(
                    table_id=table.xml_id,
                    title=table.title,
                    table_kind="dicomweb_transaction_resource",
                    source_ref=_source_ref(edition, table),
                )
            )
            transactions.extend(
                _parse_official_transaction_resource_table(
                    table,
                    header_names,
                    edition,
                    official_overviews,
                    warnings,
                )
            )
        elif _is_media_type_table(headers):
            recognized.append(
                Part18TableSummary(
                    table_id=table.xml_id,
                    title=table.title,
                    table_kind="media_type",
                    source_ref=_source_ref(edition, table),
                )
            )
            media_types.extend(
                _parse_media_type_table(table, headers, edition, warnings)
            )
        elif _is_official_application_dicom_media_type_table(table, header_names):
            recognized.append(
                Part18TableSummary(
                    table_id=table.xml_id,
                    title=table.title,
                    table_kind="media_type",
                    source_ref=_source_ref(edition, table),
                )
            )
            media_types.append(_application_dicom_media_type(table, edition))
        else:
            warnings.append(
                ParserWarning(
                    part="PS3.18",
                    table_id=table.xml_id,
                    row_index=None,
                    message="unsupported PS3.18 table shape",
                )
            )

    return Part18ParseResult(
        recognized_tables=tuple(recognized),
        dicomweb_transactions=tuple(transactions),
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


def _header_names_by_column(table: ParsedTable) -> dict[int, tuple[str, ...]]:
    names: dict[int, list[str]] = {}
    for row in table.rows:
        if row.section != "thead":
            continue
        for cell in row.cells:
            key = _key(cell.text)
            if not key:
                continue
            for offset in range(cell.colspan):
                names.setdefault(cell.column + offset, []).append(key)
    return {column: tuple(values) for column, values in names.items()}


def _is_dicomweb_transaction_table(headers: dict[str, int]) -> bool:
    keys = headers.keys()
    return (
        bool(keys & {"transaction", "transaction name", "name", "service"})
        and bool(keys & {"method", "http method"})
        and bool(keys & {"route", "resource", "uri"})
    )


def _is_media_type_table(headers: dict[str, int]) -> bool:
    return "media type" in headers and bool(
        headers.keys() & {"service context", "context", "transaction"}
    )


def _is_official_transaction_overview_table(
    header_names: dict[int, tuple[str, ...]]
) -> bool:
    return (
        _column_with_header(header_names, "transaction name") is not None
        and _column_with_header(header_names, "method") is not None
        and _column_with_header(header_names, "request") is not None
        and _column_with_header(header_names, "success response") is not None
    )


def _is_official_transaction_resource_table(
    table: ParsedTable, header_names: dict[int, tuple[str, ...]]
) -> bool:
    title = _key(table.title or "")
    return (
        title.startswith(
            ("retrieve transaction", "store transaction", "search transaction")
        )
        and title.endswith("resources")
        and _column_with_header(header_names, "resource") is not None
        and _column_with_header(header_names, "uri template") is not None
    )


def _is_official_application_dicom_media_type_table(
    table: ParsedTable, header_names: dict[int, tuple[str, ...]]
) -> bool:
    title = _key(table.title or "")
    return (
        "application/dicom media types" in title
        and _column_with_header(header_names, "transfer syntax uid") is not None
        and _column_with_header(header_names, "optionality") is not None
    )


def _official_transaction_overviews(
    document: ParsedDocument,
) -> dict[str, _TransactionOverview]:
    overviews: dict[str, _TransactionOverview] = {}
    for table in document.tables:
        header_names = _header_names_by_column(table)
        if not _is_official_transaction_overview_table(header_names):
            continue
        for overview in _parse_official_transaction_overview_table(
            table, header_names
        ):
            overviews[overview.transaction_name.casefold()] = overview
    return overviews


def _parse_official_transaction_overview_table(
    table: ParsedTable, header_names: dict[int, tuple[str, ...]]
) -> list[_TransactionOverview]:
    transaction_column = _column_with_header(header_names, "transaction name")
    method_column = _column_with_header(header_names, "method")
    request_column = _column_with_header(header_names, "request")
    response_column = _column_with_header(header_names, "success response")
    description_column = _column_with_header(header_names, "description")
    if (
        transaction_column is None
        or method_column is None
        or request_column is None
        or response_column is None
    ):
        return []

    overviews: list[_TransactionOverview] = []
    for row in _data_rows(table):
        transaction_name = _cell(row, transaction_column)
        http_method = _cell(row, method_column).upper()
        if not transaction_name or not http_method:
            continue
        overviews.append(
            _TransactionOverview(
                transaction_name=transaction_name,
                http_method=http_method,
                request_payload=_none_if_na(_cell(row, request_column)),
                response_payload=_none_if_na(_cell(row, response_column)),
                description=_optional_cell(row, description_column),
            )
        )
    return overviews


def _parse_dicomweb_transaction_table(
    table: ParsedTable,
    headers: dict[str, int],
    edition: str,
    warnings: list[ParserWarning],
) -> list[DicomwebTransaction]:
    records: list[DicomwebTransaction] = []
    transaction_column = _first_header(headers, "transaction", "name", "service")
    method_column = _first_header(headers, "method", "http method")
    route_column = _first_header(headers, "route", "uri")
    if transaction_column is None or method_column is None or route_column is None:
        warnings.append(
            ParserWarning(
                part="PS3.18",
                table_id=table.xml_id,
                row_index=None,
                message=(
                    "skipped DICOMweb transaction table without transaction, "
                    "method, and route"
                ),
            )
        )
        return records

    resource_column = _first_header(headers, "resource category", "resource")
    request_column = _first_header(
        headers,
        "request constraints",
        "request constraint",
        "request",
    )
    response_column = _first_header(
        headers,
        "response constraints",
        "response constraint",
        "response",
    )
    status_column = _first_header(headers, "status codes", "status code", "status")
    media_column = _first_header(
        headers,
        "media type refs",
        "media type references",
        "media types",
        "media type",
    )

    for row in _data_rows(table):
        transaction_name = _cell(row, transaction_column)
        http_method = _cell(row, method_column).upper()
        route_template = _cell(row, route_column)
        if not transaction_name or not http_method or not route_template:
            warnings.append(_warning(table, row, "skipped incomplete DICOMweb row"))
            continue

        records.append(
            DicomwebTransaction(
                id=(
                    f"{edition}.PS3.18.dicomweb_transaction."
                    f"{_identifier_fragment(transaction_name)}."
                    f"{_identifier_fragment(http_method)}."
                    f"{_identifier_fragment(route_template)}"
                ),
                edition_id=edition,
                transaction_name=transaction_name,
                resource_category=_optional_cell(row, resource_column),
                http_method=http_method,
                route_template=route_template,
                request_constraints=_optional_tuple(row, request_column),
                response_constraints=_optional_tuple(row, response_column),
                status_codes=_optional_tuple(row, status_column),
                media_type_refs=_optional_tuple(row, media_column),
                source_ref=_source_ref(edition, table),
            )
        )
    return records


def _parse_official_transaction_resource_table(
    table: ParsedTable,
    header_names: dict[int, tuple[str, ...]],
    edition: str,
    overviews: dict[str, _TransactionOverview],
    warnings: list[ParserWarning],
) -> list[DicomwebTransaction]:
    base_transaction = _base_transaction_from_resource_title(table.title or "")
    if base_transaction is None:
        return []
    overview = overviews.get(base_transaction.casefold())
    if overview is None:
        warnings.append(
            ParserWarning(
                part="PS3.18",
                table_id=table.xml_id,
                row_index=None,
                message="skipped official transaction resources without overview row",
            )
        )
        return []

    resource_column = _column_with_header(header_names, "resource")
    route_column = _column_with_header(header_names, "uri template")
    if resource_column is None or route_column is None:
        return []

    records: list[DicomwebTransaction] = []
    for row in _data_rows(table):
        resource = _cell(row, resource_column)
        route_template = _cell(row, route_column)
        if not resource or not route_template:
            warnings.append(_warning(table, row, "skipped incomplete resource row"))
            continue

        transaction_name = _official_transaction_name(
            base_transaction=overview.transaction_name,
            resource=resource,
        )
        request_constraints: tuple[str, ...] = (f"Target resource: {resource}",)
        if overview.request_payload is not None:
            request_constraints += (f"Request payload: {overview.request_payload}",)
        response_constraints: tuple[str, ...] = ()
        if overview.response_payload is not None:
            response_constraints += (
                f"Success response payload: {overview.response_payload}",
            )
        if overview.description is not None:
            response_constraints += (overview.description,)

        records.append(
            DicomwebTransaction(
                id=(
                    f"{edition}.PS3.18.dicomweb_transaction."
                    f"{_identifier_fragment(transaction_name)}."
                    f"{_identifier_fragment(overview.http_method)}."
                    f"{_identifier_fragment(route_template)}"
                ),
                edition_id=edition,
                transaction_name=transaction_name,
                resource_category=_resource_category(resource),
                http_method=overview.http_method,
                route_template=route_template,
                request_constraints=request_constraints,
                response_constraints=response_constraints,
                status_codes=(),
                media_type_refs=_media_type_refs_for_transaction(
                    overview.transaction_name
                ),
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
                part="PS3.18",
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

        records.append(
            DicomMediaType(
                id=(
                    f"{edition}.PS3.18.media_type."
                    f"{_identifier_fragment(service_context)}."
                    f"{_identifier_fragment(media_type)}"
                ),
                edition_id=edition,
                media_type=media_type,
                service_context=service_context,
                transfer_syntax_constraints=_optional_tuple(row, constraints_column),
                directions=tuple(
                    part.lower() for part in _optional_tuple(row, directions_column)
                ),
                source_ref=_source_ref(edition, table),
            )
        )
    return records


def _application_dicom_media_type(table: ParsedTable, edition: str) -> DicomMediaType:
    constraints: list[str] = []
    uid_column = _column_with_header(
        _header_names_by_column(table), "transfer syntax uid"
    )
    name_column = _column_with_header(
        _header_names_by_column(table), "transfer syntax name"
    )
    optionality_column = _column_with_header(
        _header_names_by_column(table), "optionality"
    )
    if uid_column is not None and name_column is not None:
        for row in _data_rows(table):
            uid = _cell(row, uid_column)
            name = _cell(row, name_column)
            optionality = _optional_cell(row, optionality_column)
            if not uid or not name:
                continue
            constraint = f"{uid} {name}"
            if optionality:
                constraint = f"{constraint} ({optionality})"
            constraints.append(constraint)
    if not constraints:
        constraints.append(table.title or "application/dicom transfer syntax table")

    return DicomMediaType(
        id=f"{edition}.PS3.18.media_type.application_dicom",
        edition_id=edition,
        media_type="application/dicom",
        service_context="Instance Media Types",
        transfer_syntax_constraints=tuple(constraints),
        directions=("response",),
        source_ref=_source_ref(edition, table),
    )


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


def _column_with_header(
    header_names: dict[int, tuple[str, ...]], *names: str
) -> int | None:
    expected = set(names)
    for column, values in sorted(header_names.items()):
        if expected & set(values):
            return column
    return None


def _key(value: str) -> str:
    return normalize_text(value).lower()


def _none_if_na(value: str) -> str | None:
    normalized = normalize_text(value)
    if not normalized or normalized.upper() == "N/A":
        return None
    return normalized


def _base_transaction_from_resource_title(title: str) -> str | None:
    match = re.match(r"^(Retrieve|Store|Search) Transaction\b", title, re.IGNORECASE)
    if match is None:
        return None
    return match.group(1)


def _official_transaction_name(*, base_transaction: str, resource: str) -> str:
    tokens = [
        token
        for token in re.findall(r"[A-Za-z0-9]+", resource)
        if token.casefold() not in {"instances", "resources"}
    ]
    if tokens:
        return base_transaction + "".join(tokens)
    return base_transaction


def _resource_category(resource: str) -> str | None:
    normalized = resource.casefold()
    for category in ("study", "series", "instance", "metadata", "bulk data"):
        if category in normalized:
            return category.replace(" ", "_")
    return normalize_text(resource).lower() or None


def _media_type_refs_for_transaction(transaction_name: str) -> tuple[str, ...]:
    normalized = transaction_name.casefold()
    if normalized == "retrieve":
        return ("application/dicom", "application/dicom+json")
    if normalized == "store":
        return ("multipart/related", "application/dicom")
    return ("application/dicom+json",)


def _identifier_fragment(value: str) -> str:
    normalized = normalize_text(value).lower().replace("+", "_plus_")
    return re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")


def _warning(table: ParsedTable, row: ParsedRow, message: str) -> ParserWarning:
    return ParserWarning(
        part="PS3.18",
        table_id=table.xml_id,
        row_index=row.row_index,
        message=message,
    )


def _source_ref(edition: str, table: ParsedTable) -> SourceRef:
    table_id = table.xml_id or "unknown"
    return SourceRef(
        id=f"{edition}.PS3.18.{table_id}",
        edition_id=edition,
        part="PS3.18",
        section=table.parent_xml_id,
        table_id=table_id,
        xml_id=table.xml_id,
        title=table.title,
    )
