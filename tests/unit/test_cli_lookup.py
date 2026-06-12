from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from dicom_kb.cli.main import app
from dicom_kb.db.importers import (
    import_docbook_structure,
    import_part03,
    import_part04,
    import_part06,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part03_iods import parse_part03
from dicom_kb.parsers.part04_sop_classes import parse_part04
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from tests.fixtures_synthetic import (
    PS33_CT_IMAGE_DOCBOOK,
    PS34_SOP_CLASSES_DOCBOOK,
    PS36_REGISTRY_DOCBOOK,
)


def _fixture_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "kb.sqlite"
    connection = connect_sqlite(db_path)
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
    part03_document = parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3")
    import_docbook_structure(
        connection,
        edition="2026b",
        document=part03_document,
    )
    parsed_part03 = parse_part03(part03_document, edition="2026b")
    import_part03(
        connection,
        edition="2026b",
        iods=parsed_part03.iods,
        modules=parsed_part03.modules,
        macros=parsed_part03.macros,
        iod_module_uses=parsed_part03.iod_module_uses,
        iod_functional_group_uses=parsed_part03.iod_functional_group_uses,
        attribute_uses=parsed_part03.attribute_uses,
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
    connection.close()
    return db_path


def _invoke_json(tmp_path: Path, *args: str) -> dict[str, Any]:
    result = CliRunner().invoke(app, [*args, "--db", str(_fixture_db(tmp_path))])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_cli_lookup_tag_outputs_success_envelope(tmp_path: Path) -> None:
    payload = _invoke_json(
        tmp_path,
        "lookup",
        "tag",
        "(0008,0060)",
        "--edition",
        "2026b",
    )

    assert payload["tool"] == "lookup_data_element"
    assert payload["status"] == "ok"
    assert payload["result"] == {
        "keyword": "Modality",
        "name": "Modality",
        "retired": False,
        "tag": "(0008,0060)",
        "vm": "1",
        "vr": "CS",
    }
    assert payload["refs"][0]["part"] == "PS3.6"
    assert payload["warnings"] == []
    assert payload["trace"]["query_id"]
    assert payload["trace"]["resolved_at"]


def test_cli_lookup_tag_reports_validation_error(tmp_path: Path) -> None:
    payload = _invoke_json(
        tmp_path,
        "lookup",
        "tag",
        "0008,0060",
        "--edition",
        "2026b",
    )

    assert payload["status"] == "validation_error"
    assert "malformed DICOM tag" in payload["result"]["message"]
    assert payload["refs"] == []


def test_cli_lookup_tag_reports_range_match_warning(tmp_path: Path) -> None:
    payload = _invoke_json(
        tmp_path,
        "lookup",
        "tag",
        "(6002,3000)",
        "--edition",
        "2026b",
    )

    assert payload["status"] == "ok"
    assert payload["result"]["tag"] == "(60xx,3000)"
    assert payload["warnings"] == [
        "concrete tag (6002,3000) matched range row (60xx,3000)"
    ]


def test_cli_lookup_uid_outputs_retired_entry(tmp_path: Path) -> None:
    payload = _invoke_json(
        tmp_path,
        "lookup",
        "uid",
        "ExplicitVRBigEndian",
        "--edition",
        "2026b",
    )

    assert payload["tool"] == "lookup_uid"
    assert payload["status"] == "ok"
    assert payload["result"]["uid_value"] == "1.2.840.10008.1.2.2"
    assert payload["result"]["retired"] is True
    assert payload["refs"][0]["part"] == "PS3.6"


def test_cli_retrieve_text_outputs_capped_excerpt(tmp_path: Path) -> None:
    payload = _invoke_json(
        tmp_path,
        "retrieve-text",
        "PS3.3",
        "sect_A.3",
        "--edition",
        "2026b",
        "--max-chars",
        "60",
    )

    assert payload["tool"] == "retrieve_standard_text"
    assert payload["status"] == "ok"
    assert payload["result"]["title"] == "CT Image IOD"
    assert len(payload["result"]["text_excerpt"]) == 60
    assert payload["result"]["tables"] == [
        {"table_id": "table_A.3-1", "title": "CT Image IOD Modules"}
    ]
    assert payload["warnings"] == ["text excerpt truncated to 60 characters"]


def test_cli_search_text_outputs_matches(tmp_path: Path) -> None:
    payload = _invoke_json(
        tmp_path,
        "search-text",
        "Patient name",
        "--edition",
        "2026b",
        "--part",
        "PS3.3",
        "--limit",
        "3",
    )

    assert payload["tool"] == "search_standard_text"
    assert payload["status"] == "ok"
    assert payload["input"] == {
        "limit": "3",
        "part_filter": "PS3.3",
        "query": "Patient name",
    }
    assert payload["result"]["matches"][0]["part"] == "PS3.3"
    assert "Patient" in payload["result"]["matches"][0]["snippet"]
    assert {ref["part"] for ref in payload["refs"]} == {"PS3.3"}


def test_cli_lookup_iod_outputs_ps33_iod(tmp_path: Path) -> None:
    payload = _invoke_json(
        tmp_path,
        "lookup",
        "iod",
        "CT Image",
        "--edition",
        "2026b",
    )

    assert payload["tool"] == "lookup_iod"
    assert payload["status"] == "ok"
    assert payload["result"]["name"] == "CT Image"
    assert payload["refs"][0]["part"] == "PS3.3"


def test_cli_lookup_sop_class_outputs_linked_iod(tmp_path: Path) -> None:
    payload = _invoke_json(
        tmp_path,
        "lookup",
        "sop-class",
        "CT Image Storage",
        "--edition",
        "2026b",
    )

    assert payload["tool"] == "lookup_sop_class"
    assert payload["status"] == "ok"
    assert payload["result"]["sop_class"]["uid_value"] == (
        "1.2.840.10008.5.1.4.1.1.2"
    )
    assert payload["result"]["iods"][0]["iod_name"] == "CT Image"
    assert {ref["part"] for ref in payload["refs"]} == {"PS3.3", "PS3.4"}


def test_cli_lookup_tag_requires_existing_db(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "lookup",
            "tag",
            "Modality",
            "--edition",
            "2026b",
            "--db",
            str(tmp_path / "missing.sqlite"),
        ],
    )

    assert result.exit_code != 0
    assert "SQLite KB does not exist" in result.output


def test_cli_iod_modules_outputs_ps33_module_envelope(tmp_path: Path) -> None:
    payload = _invoke_json(
        tmp_path,
        "iod",
        "modules",
        "CT Image",
        "--edition",
        "2026b",
    )

    assert payload["tool"] == "list_modules_for_iod"
    assert payload["status"] == "ok"
    assert payload["result"]["iod"]["name"] == "CT Image"
    assert [row["module_name"] for row in payload["result"]["modules"]] == [
        "Patient",
        "Contrast/Bolus",
        "CT Image",
    ]
    assert payload["refs"][0]["part"] == "PS3.3"


def test_cli_module_attributes_expands_macros(tmp_path: Path) -> None:
    payload = _invoke_json(
        tmp_path,
        "module",
        "attributes",
        "Patient",
        "--edition",
        "2026b",
        "--expand-macros",
    )

    assert payload["tool"] == "list_attributes_for_module"
    assert payload["status"] == "ok"
    assert payload["result"]["module"]["name"] == "Patient"
    assert payload["result"]["attributes"][-1]["attribute_name"] == (
        "Anatomic Region Sequence"
    )
    assert payload["result"]["attributes"][-1]["expanded_from_include_id"] == (
        "2026b.module.patient.attribute_use.3"
    )


def test_cli_resolve_attribute_context_outputs_effective_type(
    tmp_path: Path,
) -> None:
    payload = _invoke_json(
        tmp_path,
        "resolve",
        "attribute-context",
        "PatientName",
        "--edition",
        "2026b",
        "--iod",
        "CT Image",
    )

    assert payload["tool"] == "resolve_attribute_context"
    assert payload["status"] == "ok"
    assert payload["result"]["attribute"]["tag"] == "(0010,0010)"
    assert payload["result"]["uses"][0]["module"] == "Patient"
    assert payload["result"]["effective_type"] == "2"
