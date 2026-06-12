from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from dicom_kb.db.importers import import_part03, import_part06
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part03_iods import parse_part03
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from dicom_kb.query.resolver import (
    list_attributes_for_module,
    list_modules_for_iod,
    lookup_data_element,
    lookup_uid,
)
from tests.unit.test_part03_parser import PS33_FIXTURE
from tests.unit.test_part06_parser import PS36_FIXTURE

RESOLVED_AT = datetime(2026, 6, 11, tzinfo=UTC)


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    parsed = parse_part06(
        parse_docbook_xml(PS36_FIXTURE, part="PS3.6"),
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
        parse_docbook_xml(PS33_FIXTURE, part="PS3.3"),
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
        },
        {
            "module_id": "2026b.module.contrast_bolus",
            "module_name": "Contrast/Bolus",
            "section": "C.7.6.4",
            "information_entity": "Image",
            "usage": "C",
            "usage_condition_text": "Required if contrast media was used",
        },
        {
            "module_id": "2026b.module.ct_image",
            "module_name": "CT Image",
            "section": "C.8.2.1",
            "information_entity": "Image",
            "usage": "M",
            "usage_condition_text": None,
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
