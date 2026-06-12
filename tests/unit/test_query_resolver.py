from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from dicom_kb.db.importers import (
    import_attribute_value_terms,
    import_docbook_structure,
    import_part03,
    import_part04,
    import_part06,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.ir.models import AttributeUse, Macro, SourceRef
from dicom_kb.parsers.part03_iods import parse_part03
from dicom_kb.parsers.part04_sop_classes import parse_part04
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from dicom_kb.query.resolver import (
    list_attributes_for_module,
    list_modules_for_iod,
    lookup_data_element,
    lookup_defined_terms,
    lookup_enumerated_values,
    lookup_iod,
    lookup_sop_class,
    lookup_uid,
    resolve_attribute_context,
    retrieve_standard_text,
    search_standard_text,
)
from tests.fixtures_synthetic import (
    PS33_CT_IMAGE_DOCBOOK,
    PS34_SOP_CLASSES_DOCBOOK,
    PS36_REGISTRY_DOCBOOK,
)

RESOLVED_AT = datetime(2026, 6, 11, tzinfo=UTC)


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    parsed = parse_part06(
        parse_docbook_xml(PS36_REGISTRY_DOCBOOK, part="PS3.6"),
        edition="2026b",
    )
    import_part06(
        connection,
        edition="2026b",
        data_elements=parsed.data_elements,
        uid_registry_entries=parsed.uid_registry_entries,
    )
    return connection


def _part03_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    parsed = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"),
        edition="2026b",
    )
    import_part03(
        connection,
        edition="2026b",
        iods=parsed.iods,
        modules=parsed.modules,
        macros=parsed.macros,
        iod_module_uses=parsed.iod_module_uses,
        iod_functional_group_uses=parsed.iod_functional_group_uses,
        attribute_uses=parsed.attribute_uses,
        conditions=parsed.conditions,
    )
    return connection


def _doc_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    document = parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3")
    import_docbook_structure(
        connection,
        edition="2026b",
        document=document,
    )
    return connection


def _part034_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = _part03_connection(tmp_path)
    parsed = parse_part04(
        parse_docbook_xml(PS34_SOP_CLASSES_DOCBOOK, part="PS3.4"),
        edition="2026b",
    )
    import_part04(
        connection,
        edition="2026b",
        service_classes=parsed.service_classes,
        sop_classes=parsed.sop_classes,
        sop_class_iods=parsed.sop_class_iods,
    )
    return connection


def _context_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = _connection(tmp_path)
    parsed_part03 = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"),
        edition="2026b",
    )
    import_part03(
        connection,
        edition="2026b",
        iods=parsed_part03.iods,
        modules=parsed_part03.modules,
        macros=parsed_part03.macros,
        iod_module_uses=parsed_part03.iod_module_uses,
        iod_functional_group_uses=parsed_part03.iod_functional_group_uses,
        attribute_uses=parsed_part03.attribute_uses,
        conditions=parsed_part03.conditions,
    )
    import_attribute_value_terms(
        connection,
        edition="2026b",
        document=parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"),
    )
    parsed_part04 = parse_part04(
        parse_docbook_xml(PS34_SOP_CLASSES_DOCBOOK, part="PS3.4"),
        edition="2026b",
    )
    import_part04(
        connection,
        edition="2026b",
        service_classes=parsed_part04.service_classes,
        sop_classes=parsed_part04.sop_classes,
        sop_class_iods=parsed_part04.sop_class_iods,
    )
    return connection


def _context_connection_with_duplicate_attribute(tmp_path: Path) -> sqlite3.Connection:
    connection = _connection(tmp_path)
    parsed_part03 = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"),
        edition="2026b",
    )
    duplicate = AttributeUse(
        id="2026b.module.ct_image.attribute_use.0",
        edition_id="2026b",
        owner_type="module",
        owner_id="2026b.module.ct_image",
        row_kind="attribute",
        attribute_tag="(0010,0010)",
        attribute_name="Patient's Name",
        type_designation="1",
        description_text="Duplicate contextual use.",
        sequence_depth=0,
        row_order=0,
        source_ref=parsed_part03.modules[2].source_ref,
    )
    import_part03(
        connection,
        edition="2026b",
        iods=parsed_part03.iods,
        modules=parsed_part03.modules,
        macros=parsed_part03.macros,
        iod_module_uses=parsed_part03.iod_module_uses,
        iod_functional_group_uses=parsed_part03.iod_functional_group_uses,
        attribute_uses=[*parsed_part03.attribute_uses, duplicate],
        conditions=parsed_part03.conditions,
    )
    return connection


def _part03_connection_with_recursive_macros(
    tmp_path: Path,
    *,
    include_cycle: bool = False,
) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    parsed = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"),
        edition="2026b",
    )
    nested_source_ref = SourceRef(
        id="2026b.ps3_3.table_11_1",
        edition_id="2026b",
        part="PS3.3",
        section="11.1",
        table_id="table_11-1",
        xml_id="table_11-1",
        title="Nested Device Macro Attributes",
    )
    nested_macro = Macro(
        id="2026b.macro.table_11_1",
        edition_id="2026b",
        name="Nested Device Macro",
        table_id="table_11-1",
        section="11.1",
        macro_kind="attribute",
        source_ref=nested_source_ref,
    )
    attribute_uses = [
        row.model_copy(update={"sequence_depth": 1})
        if row.id == "2026b.module.patient.attribute_use.3"
        else row
        for row in parsed.attribute_uses
    ]
    attribute_uses.extend(
        [
            AttributeUse(
                id="2026b.macro.table_10_7.attribute_use.1",
                edition_id="2026b",
                owner_type="macro",
                owner_id="2026b.macro.table_10_7",
                row_kind="include",
                included_macro_id=nested_macro.id,
                include_target_text='Include Table 11-1 "Nested Device Macro"',
                sequence_depth=1,
                row_order=1,
                source_ref=parsed.macros[0].source_ref,
            ),
            AttributeUse(
                id="2026b.macro.table_11_1.attribute_use.0",
                edition_id="2026b",
                owner_type="macro",
                owner_id=nested_macro.id,
                row_kind="attribute",
                attribute_tag="(0018,1000)",
                attribute_keyword="DeviceSerialNumber",
                attribute_name="Device Serial Number",
                type_designation="3",
                description_text="Nested device identifier.",
                sequence_depth=0,
                row_order=0,
                source_ref=nested_source_ref,
            ),
        ]
    )
    if include_cycle:
        attribute_uses.append(
            AttributeUse(
                id="2026b.macro.table_11_1.attribute_use.1",
                edition_id="2026b",
                owner_type="macro",
                owner_id=nested_macro.id,
                row_kind="include",
                included_macro_id="2026b.macro.table_10_7",
                include_target_text=(
                    'Include Table 10-7 "General Anatomy Optional Macro"'
                ),
                sequence_depth=0,
                row_order=1,
                source_ref=nested_source_ref,
            )
        )
    import_part03(
        connection,
        edition="2026b",
        iods=parsed.iods,
        modules=parsed.modules,
        macros=[*parsed.macros, nested_macro],
        iod_module_uses=parsed.iod_module_uses,
        iod_functional_group_uses=parsed.iod_functional_group_uses,
        attribute_uses=attribute_uses,
        conditions=parsed.conditions,
    )
    return connection


def test_lookup_data_element_tag_and_keyword_return_same_entity(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)

    by_tag = lookup_data_element(
        connection,
        tag_or_keyword="(0008,0060)",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )
    by_keyword = lookup_data_element(
        connection,
        tag_or_keyword="modality",
        edition="2026b",
        query_id="query-2",
        resolved_at=RESOLVED_AT,
    )

    assert by_tag.status == "ok"
    assert by_keyword.status == "ok"
    assert by_tag.result == by_keyword.result
    assert by_tag.result == {
        "tag": "(0008,0060)",
        "name": "Modality",
        "keyword": "Modality",
        "vr": "CS",
        "vm": "1",
        "retired": False,
    }
    assert by_tag.refs[0].part == "PS3.6"
    assert by_tag.trace.query_id == "query-1"
    assert by_tag.trace.resolved_at == RESOLVED_AT


def test_lookup_data_element_returns_validation_error_for_malformed_tag(
    tmp_path: Path,
) -> None:
    response = lookup_data_element(
        _connection(tmp_path),
        tag_or_keyword="0008,0060",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "validation_error"
    assert response.result is not None
    assert "malformed DICOM tag" in str(response.result["message"])
    assert response.refs == []


def test_lookup_data_element_returns_not_found_for_unknown_tag(tmp_path: Path) -> None:
    response = lookup_data_element(
        _connection(tmp_path),
        tag_or_keyword="(0008,9999)",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "not_found"
    assert response.result == {"message": "No DICOM data element matched the input."}
    assert response.refs == []


def test_lookup_data_element_reports_retired_and_range_matches(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)

    retired = lookup_data_element(
        connection,
        tag_or_keyword="CurveData",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )
    range_match = lookup_data_element(
        connection,
        tag_or_keyword="(6002,3000)",
        edition="2026b",
        query_id="query-2",
        resolved_at=RESOLVED_AT,
    )

    assert retired.status == "ok"
    assert retired.result is not None
    assert retired.result["retired"] is True
    assert range_match.status == "ok"
    assert range_match.result is not None
    assert range_match.result["tag"] == "(60xx,3000)"
    assert range_match.warnings == [
        "concrete tag (6002,3000) matched range row (60xx,3000)"
    ]


def test_lookup_uid_reports_retired_entry(tmp_path: Path) -> None:
    response = lookup_uid(
        _connection(tmp_path),
        uid_or_keyword="ExplicitVRBigEndian",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result == {
        "uid_value": "1.2.840.10008.1.2.2",
        "uid_name": "Explicit VR Big Endian",
        "uid_keyword": "ExplicitVRBigEndian",
        "uid_type": "Transfer Syntax",
        "part": "PS3.5",
        "retired": True,
    }
    assert response.refs[0].part == "PS3.6"


def test_retrieve_standard_text_returns_capped_excerpt_and_tables(
    tmp_path: Path,
) -> None:
    response = retrieve_standard_text(
        _doc_connection(tmp_path),
        part="PS3.3",
        section_or_anchor="sect_A.3",
        edition="2026b",
        max_chars=80,
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["part"] == "PS3.3"
    assert response.result["section"] == "sect_A.3"
    assert response.result["title"] == "CT Image IOD"
    assert len(str(response.result["text_excerpt"])) == 80
    assert response.result["tables"] == [
        {"table_id": "table_A.3-1", "title": "CT Image IOD Modules"}
    ]
    assert response.warnings == ["text excerpt truncated to 80 characters"]
    assert [ref.part for ref in response.refs] == ["PS3.3", "PS3.3"]
    assert response.refs[1].table == "CT Image IOD Modules"
    assert response.trace.query_id == "query-1"


def test_retrieve_standard_text_validates_inputs(tmp_path: Path) -> None:
    connection = _doc_connection(tmp_path)
    response = retrieve_standard_text(
        connection,
        part="3.3",
        section_or_anchor="sect_A.3",
        edition="2026b",
        max_chars=80,
    )

    assert response.status == "validation_error"
    assert response.result is not None
    assert "part must be" in str(response.result["message"])

    response = retrieve_standard_text(
        connection,
        part="PS3.3",
        section_or_anchor="sect_A.3",
        edition="2026b",
        max_chars=0,
    )

    assert response.status == "validation_error"
    assert response.result is not None
    assert "max_chars" in str(response.result["message"])


def test_retrieve_standard_text_reports_not_found(tmp_path: Path) -> None:
    response = retrieve_standard_text(
        _doc_connection(tmp_path),
        part="PS3.3",
        section_or_anchor="missing",
        edition="2026b",
        max_chars=80,
    )

    assert response.status == "not_found"
    assert response.result == {"message": "No standard text node matched the input."}
    assert response.refs == []


def test_search_standard_text_returns_cited_matches(tmp_path: Path) -> None:
    response = search_standard_text(
        _doc_connection(tmp_path),
        query="Patient name",
        edition="2026b",
        part_filter="PS3.3",
        limit=5,
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    matches = response.result["matches"]
    assert matches[0]["part"] == "PS3.3"
    assert matches[0]["title"] in {"Patient Module", "Patient Module Attributes"}
    assert "Patient" in matches[0]["snippet"]
    assert {ref.part for ref in response.refs} == {"PS3.3"}
    assert response.input == {
        "query": "Patient name",
        "limit": "5",
        "part_filter": "PS3.3",
    }
    assert response.trace.query_id == "query-1"


def test_search_standard_text_validates_inputs(tmp_path: Path) -> None:
    connection = _doc_connection(tmp_path)

    response = search_standard_text(
        connection,
        query="   ",
        edition="2026b",
    )
    assert response.status == "validation_error"
    assert response.result is not None
    assert "query must not be empty" in str(response.result["message"])

    response = search_standard_text(
        connection,
        query="Patient",
        edition="2026b",
        part_filter="3.3",
    )
    assert response.status == "validation_error"
    assert response.result is not None
    assert "part_filter" in str(response.result["message"])

    response = search_standard_text(
        connection,
        query="Patient",
        edition="2026b",
        limit=0,
    )
    assert response.status == "validation_error"
    assert response.result is not None
    assert "limit" in str(response.result["message"])


def test_search_standard_text_reports_not_found(tmp_path: Path) -> None:
    response = search_standard_text(
        _doc_connection(tmp_path),
        query="ultrasound elastography",
        edition="2026b",
    )

    assert response.status == "not_found"
    assert response.result == {"message": "No standard text matched the query."}
    assert response.refs == []


def test_lookup_iod_returns_ps33_iod(tmp_path: Path) -> None:
    response = lookup_iod(
        _part03_connection(tmp_path),
        iod_name="ct_image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result == {
        "id": "2026b.iod.ct_image",
        "name": "CT Image",
        "keyword": "ct_image",
        "iod_type": "composite",
        "part": "PS3.3",
        "section": "table_A.3-1",
    }
    assert response.refs[0].part == "PS3.3"


def test_lookup_sop_class_returns_linked_iod(tmp_path: Path) -> None:
    response = lookup_sop_class(
        _part034_connection(tmp_path),
        uid_or_name_or_keyword="1.2.840.10008.5.1.4.1.1.2",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["sop_class"] == {
        "id": "2026b.sop_class.1.2.840.10008.5.1.4.1.1.2",
        "name": "CT Image Storage",
        "uid_value": "1.2.840.10008.5.1.4.1.1.2",
    }
    assert response.result["service_class"]["name"] == "Storage Service Class"
    assert response.result["iods"] == [
        {
            "iod_id": "2026b.iod.ct_image",
            "iod_name": "CT Image",
            "iod_keyword": "ct_image",
            "resolution": "parsed",
            "resolution_warning": None,
        }
    ]
    assert {ref.part for ref in response.refs} == {"PS3.3", "PS3.4"}


def test_lookup_sop_class_by_name_and_malformed_uid_paths(tmp_path: Path) -> None:
    connection = _part034_connection(tmp_path)
    by_name = lookup_sop_class(
        connection,
        uid_or_name_or_keyword="enhanced ct image storage",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )
    malformed = lookup_sop_class(
        connection,
        uid_or_name_or_keyword="1.2.bad",
        edition="2026b",
        query_id="query-2",
        resolved_at=RESOLVED_AT,
    )

    assert by_name.status == "ok"
    assert by_name.result is not None
    assert by_name.result["iods"][0]["iod_name"] == "Enhanced CT Image"
    assert malformed.status == "validation_error"
    assert malformed.result is not None
    assert "malformed DICOM UID" in malformed.result["message"]


def test_resolve_attribute_context_for_iod_returns_effective_type(
    tmp_path: Path,
) -> None:
    response = resolve_attribute_context(
        _context_connection(tmp_path),
        attribute="PatientName",
        iod_name="CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["attribute"] == {
        "tag": "(0010,0010)",
        "name": "Patient's Name",
        "keyword": "PatientName",
        "vr": "PN",
        "vm": "1",
        "retired": False,
    }
    assert response.result["uses"] == [
        {
            "iod": "CT Image",
            "module": "Patient",
            "information_entity": "Patient",
            "module_usage": "M",
            "module_usage_condition_text": None,
            "attribute_use_id": "2026b.module.patient.attribute_use.0",
            "type_designation": "2",
            "sequence_path": [],
            "via_macro": None,
            "condition": None,
        }
    ]
    assert response.result["effective_type"] == "2"
    assert response.result["effective_type_explanation"] == (
        "Single applicable use in resolved context."
    )
    assert {ref.part for ref in response.refs} == {"PS3.3", "PS3.6"}


def test_resolve_attribute_context_for_sop_class_preserves_sequence_path(
    tmp_path: Path,
) -> None:
    response = resolve_attribute_context(
        _context_connection(tmp_path),
        attribute="ReferencedSOPClassUID",
        sop_class="CT Image Storage",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    use = response.result["uses"][0]
    assert use["iod"] == "CT Image"
    assert use["module"] == "Patient"
    assert use["type_designation"] == "1"
    assert use["sequence_path"] == ["Referenced Patient Sequence"]
    assert response.result["effective_type"] == "1"
    assert {ref.part for ref in response.refs} == {"PS3.3", "PS3.4", "PS3.6"}


def test_resolve_attribute_context_reports_macro_path(tmp_path: Path) -> None:
    response = resolve_attribute_context(
        _context_connection(tmp_path),
        attribute="AnatomicRegionSequence",
        iod_name="CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["uses"][0]["via_macro"] == ["General Anatomy Optional Macro"]
    assert response.result["effective_type"] == "3"


def test_resolve_attribute_context_traverses_functional_group_macros(
    tmp_path: Path,
) -> None:
    response = resolve_attribute_context(
        _context_connection(tmp_path),
        attribute="AnatomicRegionSequence",
        iod_name="Enhanced CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["uses"] == [
        {
            "iod": "Enhanced CT Image",
            "module": None,
            "functional_group_macro": "General Anatomy Optional Macro",
            "information_entity": None,
            "module_usage": "C",
            "module_usage_condition_text": "Required if anatomy is known",
            "attribute_use_id": "2026b.macro.table_10_7.attribute_use.0",
            "type_designation": "3",
            "sequence_path": [],
            "via_macro": ["General Anatomy Optional Macro"],
            "condition": None,
        }
    ]
    assert response.result["effective_type"] == "3"


def test_lookup_defined_terms_returns_attribute_value_terms(tmp_path: Path) -> None:
    response = lookup_defined_terms(
        _context_connection(tmp_path),
        attribute="PatientName",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["attribute"]["tag"] == "(0010,0010)"
    assert response.result["terms"] == [
        {
            "value": "ALPHA",
            "meaning": "Alphabetic representation.",
            "term_kind": "defined_term",
            "context_label": "Patient Module - Defined Terms:",
            "attribute_use_id": "2026b.module.patient.attribute_use.0",
        },
        {
            "value": "IDEOGRAPHIC",
            "meaning": "Ideographic representation.",
            "term_kind": "defined_term",
            "context_label": "Patient Module - Defined Terms:",
            "attribute_use_id": "2026b.module.patient.attribute_use.0",
        },
    ]
    assert {ref.part for ref in response.refs} == {"PS3.3", "PS3.6"}


def test_lookup_value_terms_supports_context_and_missing_term_kind(
    tmp_path: Path,
) -> None:
    connection = _context_connection(tmp_path)
    matched_context = lookup_defined_terms(
        connection,
        attribute="PatientName",
        edition="2026b",
        context="Patient",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )
    missing_context = lookup_defined_terms(
        connection,
        attribute="PatientName",
        edition="2026b",
        context="CT Image",
        query_id="query-2",
        resolved_at=RESOLVED_AT,
    )
    missing_kind = lookup_enumerated_values(
        connection,
        attribute="PatientName",
        edition="2026b",
        query_id="query-3",
        resolved_at=RESOLVED_AT,
    )

    assert matched_context.status == "ok"
    assert matched_context.result is not None
    assert len(matched_context.result["terms"]) == 2
    assert missing_context.status == "not_found"
    assert missing_kind.status == "not_found"


def test_resolve_attribute_context_computes_lowest_type_for_multiple_uses(
    tmp_path: Path,
) -> None:
    response = resolve_attribute_context(
        _context_connection_with_duplicate_attribute(tmp_path),
        attribute="Patient's Name",
        iod_name="CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert [use["type_designation"] for use in response.result["uses"]] == ["2", "1"]
    assert response.result["effective_type"] == "1"
    assert response.result["effective_type_explanation"].startswith(
        "Multiple applicable uses"
    )
    assert response.warnings == [
        "effective type assumes no attribute description overrides the "
        "multiple-module lowest-type rule"
    ]


def test_resolve_attribute_context_reports_missing_and_invalid_inputs(
    tmp_path: Path,
) -> None:
    connection = _context_connection(tmp_path)
    missing_attribute = resolve_attribute_context(
        connection,
        attribute="MissingAttribute",
        iod_name="CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )
    missing_context = resolve_attribute_context(
        connection,
        attribute="PatientName",
        iod_name="Missing IOD",
        edition="2026b",
        query_id="query-2",
        resolved_at=RESOLVED_AT,
    )
    invalid_context_choice = resolve_attribute_context(
        connection,
        attribute="PatientName",
        edition="2026b",
        query_id="query-3",
        resolved_at=RESOLVED_AT,
    )

    assert missing_attribute.status == "not_found"
    assert missing_attribute.result == {
        "message": "No DICOM data element matched the attribute input."
    }
    assert missing_context.status == "not_found"
    assert missing_context.result == {
        "message": "No DICOM IOD matched the context input."
    }
    assert invalid_context_choice.status == "validation_error"
    assert invalid_context_choice.result == {
        "message": "Provide exactly one context: iod_name or sop_class."
    }


def test_list_modules_for_iod_returns_ordered_ps33_modules(tmp_path: Path) -> None:
    response = list_modules_for_iod(
        _part03_connection(tmp_path),
        iod_name="CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["iod"]["name"] == "CT Image"
    assert response.result["modules"] == [
        {
            "module_id": "2026b.module.patient",
            "module_name": "Patient",
            "section": "table_C.7-1",
            "information_entity": "Patient",
            "usage": "M",
            "usage_condition_text": None,
            "condition": None,
        },
        {
            "module_id": "2026b.module.contrast_bolus",
            "module_name": "Contrast/Bolus",
            "section": "C.7.6.4",
            "information_entity": "Image",
            "usage": "C",
            "usage_condition_text": "Required if contrast media was used",
            "condition": {
                "condition_id": "2026b.iod.ct_image.module_use.1.condition",
                "source_text": "Required if contrast media was used",
                "condition_kind": "required_if",
                "machine_status": "raw_text",
                "dependencies": [],
                "evaluator": {"available": False},
                "refs": [
                    {
                        "part": "PS3.3",
                        "section": "sect_A.3",
                        "table": "CT Image IOD Modules",
                        "anchor": "table_A.3-1",
                        "official_url": None,
                        "edition": "2026b",
                    }
                ],
            },
        },
        {
            "module_id": "2026b.module.ct_image",
            "module_name": "CT Image",
            "section": "C.8.2.1",
            "information_entity": "Image",
            "usage": "M",
            "usage_condition_text": None,
            "condition": None,
        },
    ]
    assert {ref.part for ref in response.refs} == {"PS3.3"}


def test_list_modules_for_iod_returns_not_found(tmp_path: Path) -> None:
    response = list_modules_for_iod(
        _part03_connection(tmp_path),
        iod_name="Missing IOD",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "not_found"
    assert response.result == {"message": "No DICOM IOD matched the input."}
    assert response.refs == []


def test_list_attributes_for_module_preserves_include_rows(tmp_path: Path) -> None:
    response = list_attributes_for_module(
        _part03_connection(tmp_path),
        module_name="Patient",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["module"]["name"] == "Patient"
    attributes = response.result["attributes"]
    assert [row["row_kind"] for row in attributes] == [
        "attribute",
        "attribute",
        "attribute",
        "include",
    ]
    assert attributes[0]["attribute_tag"] == "(0010,0010)"
    assert attributes[2]["parent_attribute_use_id"] == (
        "2026b.module.patient.attribute_use.1"
    )
    assert attributes[3]["included_macro_name"] == "General Anatomy Optional Macro"


def test_list_attributes_for_module_exposes_attribute_conditions(
    tmp_path: Path,
) -> None:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    xml = PS33_CT_IMAGE_DOCBOOK.replace(
        "<entry>2</entry><entry>Patient name.</entry>",
        "<entry>1C</entry><entry>Required if patient identity is known.</entry>",
    )
    parsed = parse_part03(
        parse_docbook_xml(xml, part="PS3.3"),
        edition="2026b",
    )
    import_part03(
        connection,
        edition="2026b",
        iods=parsed.iods,
        modules=parsed.modules,
        macros=parsed.macros,
        iod_module_uses=parsed.iod_module_uses,
        iod_functional_group_uses=parsed.iod_functional_group_uses,
        attribute_uses=parsed.attribute_uses,
        conditions=parsed.conditions,
    )

    response = list_attributes_for_module(
        connection,
        module_name="Patient",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    patient_name = response.result["attributes"][0]
    assert patient_name["type_designation"] == "1C"
    assert patient_name["condition"] == {
        "condition_id": "2026b.module.patient.attribute_use.0.condition",
        "source_text": "Required if patient identity is known.",
        "condition_kind": "required_if",
        "machine_status": "raw_text",
        "dependencies": [],
        "evaluator": {"available": False},
        "refs": [
            {
                "part": "PS3.3",
                "section": "sect_C.7.1.1",
                "table": "Patient Module Attributes",
                "anchor": "table_C.7-1",
                "official_url": None,
                "edition": "2026b",
            }
        ],
    }


def test_list_attributes_for_module_expands_macros_after_include(
    tmp_path: Path,
) -> None:
    response = list_attributes_for_module(
        _part03_connection(tmp_path),
        module_name="Patient",
        edition="2026b",
        expand_macros=True,
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    attributes = response.result["attributes"]
    assert [
        row["attribute_name"] for row in attributes if row["row_kind"] == "attribute"
    ] == [
        "Patient's Name",
        "Referenced Patient Sequence",
        "Referenced SOP Class UID",
        "Anatomic Region Sequence",
    ]
    expanded = attributes[-1]
    assert expanded["owner_type"] == "macro"
    assert expanded["owner_name"] == "General Anatomy Optional Macro"
    assert expanded["expanded_from_include_id"] == (
        "2026b.module.patient.attribute_use.3"
    )
    assert {ref.table for ref in response.refs} >= {
        "Patient Module Attributes",
        "General Anatomy Optional Macro Attributes",
    }


def test_list_attributes_for_module_expands_nested_macros_with_effective_depth(
    tmp_path: Path,
) -> None:
    response = list_attributes_for_module(
        _part03_connection_with_recursive_macros(tmp_path),
        module_name="Patient",
        edition="2026b",
        expand_macros=True,
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.warnings == []
    assert response.result is not None
    attributes = response.result["attributes"]
    anatomic = next(
        row
        for row in attributes
        if row.get("attribute_name") == "Anatomic Region Sequence"
    )
    nested_include = next(
        row
        for row in attributes
        if row["id"] == "2026b.macro.table_10_7.attribute_use.1"
    )
    device = next(
        row for row in attributes if row.get("attribute_name") == "Device Serial Number"
    )

    assert anatomic["sequence_depth"] == 1
    assert anatomic["expanded_from_include_id"] == (
        "2026b.module.patient.attribute_use.3"
    )
    assert nested_include["sequence_depth"] == 2
    assert nested_include["included_macro_name"] == "Nested Device Macro"
    assert nested_include["expanded_from_include_id"] == (
        "2026b.module.patient.attribute_use.3"
    )
    assert device["sequence_depth"] == 2
    assert device["owner_name"] == "Nested Device Macro"
    assert device["expanded_from_include_id"] == (
        "2026b.macro.table_10_7.attribute_use.1"
    )
    assert {ref.table for ref in response.refs} >= {
        "General Anatomy Optional Macro Attributes",
        "Nested Device Macro Attributes",
    }


def test_list_attributes_for_module_reports_macro_include_cycles(
    tmp_path: Path,
) -> None:
    response = list_attributes_for_module(
        _part03_connection_with_recursive_macros(tmp_path, include_cycle=True),
        module_name="Patient",
        edition="2026b",
        expand_macros=True,
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.warnings == [
        "skipped recursive macro include cycle: "
        "2026b.macro.table_10_7 -> 2026b.macro.table_11_1 -> "
        "2026b.macro.table_10_7"
    ]
