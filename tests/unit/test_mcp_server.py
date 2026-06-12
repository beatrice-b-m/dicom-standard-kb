from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from dicom_kb.cli.main import app
from dicom_kb.mcp.server import (
    MCP_TOOL_NAMES,
    MCPServerConfig,
    MissingMCPDependencyError,
    execute_mcp_tool,
    serve_mcp_stdio,
)
from tests.unit.test_cli_lookup import _fixture_db


def test_mcp_tool_names_match_v1_spec() -> None:
    assert MCP_TOOL_NAMES == (
        "dicom_lookup_data_element",
        "dicom_lookup_uid",
        "dicom_lookup_sop_class",
        "dicom_lookup_iod",
        "dicom_list_modules_for_iod",
        "dicom_list_attributes_for_module",
        "dicom_resolve_attribute_context",
        "dicom_retrieve_standard_text",
        "dicom_search_standard_text",
    )


def test_execute_mcp_tool_returns_public_lookup_envelope(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_lookup_data_element",
        {"tag_or_keyword": "Modality"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload["tool"] == "lookup_data_element"
    assert payload["status"] == "ok"
    assert payload["result"]["tag"] == "(0008,0060)"
    assert payload["refs"][0]["part"] == "PS3.6"
    assert payload["warnings"] == []


def test_execute_mcp_tool_expands_module_macros(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_list_attributes_for_module",
        {"module_name": "Patient", "expand_macros": True},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload["tool"] == "list_attributes_for_module"
    assert payload["status"] == "ok"
    assert payload["result"]["attributes"][-1]["attribute_name"] == (
        "Anatomic Region Sequence"
    )
    assert payload["result"]["attributes"][-1]["expanded_from_include_id"] == (
        "2026b.module.patient.attribute_use.3"
    )


def test_execute_mcp_tool_resolves_attribute_context(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_resolve_attribute_context",
        {"attribute": "PatientName", "iod_name": "CT Image"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload["tool"] == "resolve_attribute_context"
    assert payload["status"] == "ok"
    assert payload["result"]["effective_type"] == "2"


def test_execute_mcp_tool_reports_missing_db(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="SQLite KB does not exist"):
        execute_mcp_tool(
            "dicom_lookup_uid",
            {"uid_or_keyword": "ExplicitVRLittleEndian"},
            config=MCPServerConfig(
                edition="2026b",
                db_path=tmp_path / "missing.sqlite",
            ),
        )


def test_mcp_cli_exposes_serve_command_without_optional_dependency() -> None:
    result = CliRunner().invoke(app, ["mcp", "serve", "--help"])

    assert result.exit_code == 0, result.output
    assert "--edition" in result.output
    assert "--db" in result.output


def test_serve_mcp_stdio_reports_missing_optional_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dicom_kb.mcp import server

    def fail_load_fastmcp() -> object:
        raise MissingMCPDependencyError("missing mcp")

    monkeypatch.setattr(server, "_load_fastmcp", fail_load_fastmcp)

    with pytest.raises(MissingMCPDependencyError, match="missing mcp"):
        serve_mcp_stdio(MCPServerConfig(edition="2026b"))

