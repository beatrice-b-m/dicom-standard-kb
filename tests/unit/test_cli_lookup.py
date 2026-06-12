from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from dicom_kb.cli.main import app
from dicom_kb.db.importers import import_part06
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from tests.unit.test_part06_parser import PS36_FIXTURE


def _fixture_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "kb.sqlite"
    connection = connect_sqlite(db_path)
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
