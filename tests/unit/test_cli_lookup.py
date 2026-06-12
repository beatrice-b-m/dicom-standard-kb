from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
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
from dicom_kb.sources.downloader import (
    official_archive_release_url,
    official_artifact_url,
    official_chtml_directory_url,
    official_docbook_xml_url,
)
from tests.fixtures_synthetic import (
    FIXTURE_DIR,
    PS33_CT_IMAGE_DOCBOOK,
    PS34_SOP_CLASSES_DOCBOOK,
    PS36_REGISTRY_DOCBOOK,
)


class _FakeResponse(BytesIO):
    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()


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


def test_cli_build_fixture_creates_default_db_for_lookups(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    runner = CliRunner()

    build_result = runner.invoke(
        app,
        [
            "build-fixture",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cache_dir),
        ],
    )

    assert build_result.exit_code == 0, build_result.output
    build_payload = json.loads(build_result.output)
    assert build_payload["db_path"] == str(cache_dir / "db" / "2026b.sqlite")

    lookup_result = runner.invoke(
        app,
        [
            "lookup",
            "tag",
            "Modality",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cache_dir),
        ],
    )

    assert lookup_result.exit_code == 0, lookup_result.output
    payload = json.loads(lookup_result.output)
    assert payload["status"] == "ok"
    assert payload["result"]["tag"] == "(0008,0060)"


def test_cli_fetch_registers_local_docbook_for_build(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    runner = CliRunner()

    fetch_result = runner.invoke(
        app,
        [
            "fetch",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cache_dir),
            "--docbook-xml",
            f"PS3.6={FIXTURE_DIR / 'synthetic_ps3_6_registry_docbook.xml'}",
        ],
    )

    assert fetch_result.exit_code == 0, fetch_result.output
    fetch_payload = json.loads(fetch_result.output)
    assert fetch_payload["edition"] == "2026b"
    assert fetch_payload["artifacts"][0]["local_path"] == (
        "artifacts/2026b/raw/source/docbook/part06/part06.xml"
    )

    build_result = runner.invoke(
        app,
        [
            "build",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cache_dir),
        ],
    )

    assert build_result.exit_code == 0, build_result.output

    lookup_result = runner.invoke(
        app,
        [
            "lookup",
            "tag",
            "Modality",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cache_dir),
        ],
    )

    assert lookup_result.exit_code == 0, lookup_result.output
    payload = json.loads(lookup_result.output)
    assert payload["status"] == "ok"
    assert payload["result"]["keyword"] == "Modality"


def test_cli_fetch_downloads_official_docbook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_url = "https://dicom.example/current/"
    part_url = official_docbook_xml_url(base_url, "PS3.6")
    responses = {
        base_url: (
            b'<a href="DocBookDICOM2026b_release_docbook_20260327091344.zip">'
            b"docbook</a>"
        ),
        part_url: b"<book><title>Part 6</title></book>",
    }

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        assert timeout == 60
        return _FakeResponse(responses[url])

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)
    cache_dir = tmp_path / "cache"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "fetch",
            "--edition",
            "current",
            "--cache-dir",
            str(cache_dir),
            "--source-base-url",
            base_url,
            "--part",
            "PS3.6",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["edition"] == "2026b"
    assert payload["resolved_from"] == "current"
    assert payload["artifacts"][0]["source_url"] == part_url
    assert payload["artifacts"][0]["local_path"] == (
        "artifacts/2026b/raw/source/docbook/part06/part06.xml"
    )


def test_cli_fetch_downloads_requested_official_formats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_url = "https://dicom.example/current/"
    docbook_url = official_artifact_url(
        base_url, part="PS3.6", artifact_format="docbook_xml"
    )
    pdf_url = official_artifact_url(base_url, part="PS3.6", artifact_format="pdf")
    responses = {
        base_url: (
            b'<a href="DocBookDICOM2026b_release_docbook_20260327091344.zip">'
            b"docbook</a>"
        ),
        docbook_url: b"<book><title>Part 6</title></book>",
        pdf_url: b"%PDF-1.7\n",
    }

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        assert timeout == 60
        return _FakeResponse(responses[url])

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)
    cache_dir = tmp_path / "cache"

    result = CliRunner().invoke(
        app,
        [
            "fetch",
            "--edition",
            "current",
            "--cache-dir",
            str(cache_dir),
            "--source-base-url",
            base_url,
            "--part",
            "PS3.6",
            "--format",
            "docbook_xml",
            "--format",
            "pdf",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [artifact["format"] for artifact in payload["artifacts"]] == [
        "docbook_xml",
        "pdf",
    ]
    assert [artifact["source_url"] for artifact in payload["artifacts"]] == [
        docbook_url,
        pdf_url,
    ]
    assert payload["artifacts"][1]["local_path"] == (
        "artifacts/2026b/raw/pdf/part06.pdf"
    )


def test_cli_fetch_mirrors_chtml_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_url = "https://dicom.example/current/"
    chtml_root = official_chtml_directory_url(base_url, part="PS3.6")
    entry_url = f"{chtml_root}PS3.6.html"
    section_url = f"{chtml_root}chapter/sect_A.html"
    responses = {
        base_url: (
            b'<a href="DocBookDICOM2026b_release_docbook_20260327091344.zip">'
            b"docbook</a>"
        ),
        chtml_root: b'<a href="PS3.6.html">entry</a><a href="chapter/">chapter</a>',
        entry_url: b"<html>Part 6 entry</html>",
        f"{chtml_root}chapter/": b'<a href="sect_A.html">section</a>',
        section_url: b"<html>Section A</html>",
    }

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        assert timeout == 60
        return _FakeResponse(responses[url])

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)
    cache_dir = tmp_path / "cache"

    result = CliRunner().invoke(
        app,
        [
            "fetch",
            "--edition",
            "current",
            "--cache-dir",
            str(cache_dir),
            "--source-base-url",
            base_url,
            "--part",
            "PS3.6",
            "--format",
            "chtml",
            "--mirror-chtml-tree",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [artifact["source_url"] for artifact in payload["artifacts"]] == [
        entry_url,
        section_url,
    ]
    assert [artifact["local_path"] for artifact in payload["artifacts"]] == [
        "artifacts/2026b/raw/chtml/part06/PS3.6.html",
        "artifacts/2026b/raw/chtml/part06/chapter/sect_A.html",
    ]


def test_cli_fetch_downloads_concrete_edition_from_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current_url = "https://dicom.example/current/"
    archive_url = "https://dicom.example/dicom/"
    release_url = official_archive_release_url(archive_url, edition="2025e")
    part_url = official_docbook_xml_url(release_url, "PS3.6")
    responses = {
        archive_url: b'<a href="2025e/">2025e</a>',
        part_url: b"<book><title>Archived Part 6</title></book>",
    }

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        assert timeout == 60
        assert url != current_url
        return _FakeResponse(responses[url])

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)
    cache_dir = tmp_path / "cache"

    result = CliRunner().invoke(
        app,
        [
            "fetch",
            "--edition",
            "2025e",
            "--cache-dir",
            str(cache_dir),
            "--source-base-url",
            current_url,
            "--archive-base-url",
            archive_url,
            "--part",
            "PS3.6",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["edition"] == "2025e"
    assert payload["resolved_from"] == "2025e"
    assert payload["artifacts"][0]["source_url"] == part_url
    assert payload["artifacts"][0]["local_path"] == (
        "artifacts/2025e/raw/source/docbook/part06/part06.xml"
    )


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


def test_cli_eval_score_outputs_agent_report(tmp_path: Path) -> None:
    transcript = tmp_path / "agent-runs.json"
    transcript.write_text(
        json.dumps(
            [
                {
                    "case_id": "agent.ps36.transfer_syntax",
                    "edition": "2026b",
                    "answer": (
                        "For edition 2026b, Explicit VR Big Endian is retired; "
                        "PS3.6 source references are present."
                    ),
                    "tool_calls": [
                        {
                            "tool": "dicom_lookup_uid",
                            "arguments": {"uid_or_keyword": "ExplicitVRBigEndian"},
                            "response_status": "ok",
                            "response_edition": "2026b",
                            "response_ref_count": 1,
                        }
                    ],
                },
                {
                    "case_id": "agent.unknown",
                    "edition": "2026b",
                    "answer": "No committed prompt case exists.",
                    "tool_calls": [],
                },
            ]
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "eval",
            "score",
            str(transcript),
            "--no-fail-on-issues",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["total_runs"] == 2
    assert payload["passed_runs"] == 1
    assert payload["failed_runs"] == 1
    assert payload["scorecards"][1]["issues"][0]["code"] == "unknown_case"
