from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import pytest
from click.utils import strip_ansi
from typer.main import get_command
from typer.testing import CliRunner

from dicom_kb.cli.main import app
from dicom_kb.mcp.server import (
    MCP_TOOL_NAMES,
    MCPServerConfig,
    MissingMCPDependencyError,
    create_mcp_server,
    execute_mcp_tool,
    serve_mcp_stdio,
)
from tests.unit.test_cli_lookup import _fixture_db

_RICH_BOX_CHARS = str.maketrans("", "", "\u256d\u2500\u256e\u2502\u2570\u256f")


@dataclass(frozen=True)
class _RegisteredTool:
    description: str
    function: Callable[..., dict[str, Any]]


class _FakeFastMCP:
    last_instance: ClassVar[_FakeFastMCP | None] = None

    def __init__(self, name: str) -> None:
        self.name = name
        self.tools: dict[str, _RegisteredTool] = {}
        self.run_transport: str | None = None
        _FakeFastMCP.last_instance = self

    def tool(
        self,
        *,
        name: str,
        description: str,
    ) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., dict[str, Any]]]:
        def decorator(
            function: Callable[..., dict[str, Any]],
        ) -> Callable[..., dict[str, Any]]:
            self.tools[name] = _RegisteredTool(
                description=description,
                function=function,
            )
            return function

        return decorator

    def run(self, *, transport: str) -> None:
        self.run_transport = transport


def test_mcp_tool_names_match_supported_spec() -> None:
    assert MCP_TOOL_NAMES == (
        "dicom_lookup_data_element",
        "dicom_lookup_uid",
        "dicom_lookup_sop_class",
        "dicom_lookup_iod",
        "dicom_lookup_enumerated_values",
        "dicom_lookup_defined_terms",
        "dicom_lookup_vr",
        "dicom_lookup_transfer_syntax",
        "dicom_explain_encoding_rule",
        "dicom_lookup_media_type",
        "dicom_lookup_dicomweb_transaction",
        "dicom_lookup_sr_template",
        "dicom_lookup_context_group",
        "dicom_lookup_code_meaning",
        "dicom_list_modules_for_iod",
        "dicom_list_attributes_for_module",
        "dicom_resolve_attribute_context",
        "dicom_retrieve_standard_text",
        "dicom_search_standard_text",
    )


def test_create_mcp_server_registers_all_supported_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dicom_kb.mcp import server

    monkeypatch.setattr(server, "_load_fastmcp", lambda: _FakeFastMCP)
    fake_server = create_mcp_server(
        MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path))
    )

    assert isinstance(fake_server, _FakeFastMCP)
    assert fake_server.name == "dicom-standard-kb"
    assert tuple(fake_server.tools) == MCP_TOOL_NAMES
    assert all(tool.description for tool in fake_server.tools.values())

    payload = fake_server.tools["dicom_search_standard_text"].function(
        "Patient name",
        part_filter="PS3.3",
        limit=2,
    )

    assert payload["tool"] == "search_standard_text"
    assert payload["status"] == "ok"
    assert payload["input"]["part_filter"] == "PS3.3"
    assert len(payload["result"]["matches"]) <= 2


def test_serve_mcp_stdio_runs_fastmcp_stdio_transport(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dicom_kb.mcp import server

    _FakeFastMCP.last_instance = None
    monkeypatch.setattr(server, "_load_fastmcp", lambda: _FakeFastMCP)

    serve_mcp_stdio(MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)))

    assert _FakeFastMCP.last_instance is not None
    assert _FakeFastMCP.last_instance.run_transport == "stdio"


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


def test_execute_mcp_tool_returns_vr_definition(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_lookup_vr",
        {"vr": "ob"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload["tool"] == "lookup_vr"
    assert payload["status"] == "ok"
    assert payload["result"]["vr"] == "OB"
    assert payload["result"]["binary_or_text"] == "binary"
    assert payload["refs"][0]["part"] == "PS3.5"


def test_execute_mcp_tool_returns_transfer_syntax_detail(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_lookup_transfer_syntax",
        {"uid_or_keyword": "ImplicitVRLittleEndian"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload["tool"] == "lookup_transfer_syntax"
    assert payload["status"] == "ok"
    assert payload["result"]["uid_value"] == "1.2.840.10008.1.2"
    assert payload["result"]["explicit_vr"] is False
    assert payload["result"]["endian"] == "little"


def test_execute_mcp_tool_explains_encoding_rule(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_explain_encoding_rule",
        {"topic": "PN"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload["tool"] == "explain_encoding_rule"
    assert payload["status"] == "ok"
    assert payload["result"]["summary"] == "PN is the Person Name VR."
    assert (
        "value representation class: character string"
        in (payload["result"]["structured_facts"])
    )


def test_execute_mcp_tool_returns_media_type_constraints(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_lookup_media_type",
        {"media_type_or_context": "file"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload["tool"] == "lookup_media_type"
    assert payload["status"] == "ok"
    assert payload["result"] == {
        "media_type": "application/dicom",
        "service_context": "PS3.10 file",
        "transfer_syntax_constraints": [
            "Encoded using the Transfer Syntax UID in the File Meta Information",
        ],
        "directions": ["file"],
    }
    assert payload["refs"][0]["part"] == "PS3.10"


def test_execute_mcp_tool_returns_ps318_media_type_context(
    tmp_path: Path,
) -> None:
    payload = execute_mcp_tool(
        "dicom_lookup_media_type",
        {"media_type_or_context": "STOW-RS request"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload["tool"] == "lookup_media_type"
    assert payload["status"] == "ok"
    assert payload["result"] == {
        "media_type": "multipart/related",
        "service_context": "STOW-RS request",
        "transfer_syntax_constraints": [
            "Each part supplies a DICOM instance payload",
        ],
        "directions": ["request"],
    }
    assert payload["refs"][0]["part"] == "PS3.18"


def test_execute_mcp_tool_returns_dicomweb_transaction(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_lookup_dicomweb_transaction",
        {"name_or_route": "RetrieveStudy"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload["tool"] == "lookup_dicomweb_transaction"
    assert payload["status"] == "ok"
    assert payload["result"] == {
        "transaction_name": "RetrieveStudy",
        "resource_category": "study",
        "http_method": "GET",
        "route_template": "/studies/{studyInstanceUID}",
        "request_constraints": ["Study Instance UID required"],
        "response_constraints": ["DICOM instances returned"],
        "status_codes": ["200", "400", "404"],
        "media_type_refs": ["application/dicom"],
    }
    assert payload["refs"][0]["part"] == "PS3.18"


def test_execute_mcp_tool_returns_sr_template(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_lookup_sr_template",
        {"tid_or_name": "TID 1500"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload["tool"] == "lookup_sr_template"
    assert payload["status"] == "ok"
    assert payload["result"] == {
        "tid": "TID 1500",
        "name": "Measurement Report",
        "extensibility": "EXTENSIBLE",
        "rows": [
            {
                "order": 1,
                "relationship_type": "CONTAINS",
                "value_type": "CONTAINER",
                "concept_name": "Measurement Report",
                "cardinality": "1",
                "condition": "Root container is required.",
                "include_tid": None,
            },
            {
                "order": 2,
                "relationship_type": "CONTAINS",
                "value_type": "INCLUDE",
                "concept_name": None,
                "cardinality": "1-n",
                "condition": "Include measurements when present.",
                "include_tid": "TID 1501",
            },
        ],
    }
    assert payload["refs"][0]["part"] == "PS3.16"


def test_execute_mcp_tool_returns_context_group(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_lookup_context_group",
        {"cid_or_name": "CID 29"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload["tool"] == "lookup_context_group"
    assert payload["status"] == "ok"
    assert payload["result"] == {
        "cid": "CID 29",
        "name": "Acquisition Modality",
        "extensibility": "EXTENSIBLE",
        "version": "20260101",
        "rows": [
            {
                "order": 1,
                "coding_scheme_designator": "DCM",
                "coding_scheme_version": None,
                "code_value": "CT",
                "code_meaning": "Computed Tomography",
                "include_cid": None,
            },
            {
                "order": 2,
                "coding_scheme_designator": None,
                "coding_scheme_version": None,
                "code_value": None,
                "code_meaning": None,
                "include_cid": "CID 30",
            },
        ],
    }
    assert payload["refs"][0]["part"] == "PS3.16"


def test_execute_mcp_tool_returns_code_meaning(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_lookup_code_meaning",
        {"code_value": "CT", "scheme": "DCM"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload["tool"] == "lookup_code_meaning"
    assert payload["status"] == "ok"
    assert payload["result"] == {
        "code_value": "CT",
        "coding_scheme_designator": "DCM",
        "coding_scheme_version": None,
        "code_meaning": "Computed Tomography",
        "context_groups": ["CID 29"],
    }
    assert payload["refs"][0]["part"] == "PS3.16"


def test_execute_mcp_tool_returns_defined_terms(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_lookup_defined_terms",
        {"attribute": "PatientName", "context": "CT Image"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload["tool"] == "lookup_defined_terms"
    assert payload["status"] == "ok"
    assert [term["value"] for term in payload["result"]["terms"]] == [
        "ALPHA",
        "IDEOGRAPHIC",
    ]
    assert {ref["part"] for ref in payload["refs"]} == {"PS3.3", "PS3.6"}


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


def test_mcp_cli_missing_db_names_fetch_and_build_commands(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "mcp",
            "serve",
            "--edition",
            "2026b",
            "--db",
            str(tmp_path / "missing.sqlite"),
        ],
    )

    output = _normalized_cli_output(result.output)

    assert result.exit_code != 0
    assert "SQLite KB does not exist" in output
    assert "dicom-kb fetch --edition current" in output
    assert "dicom-kb build --edition <resolved-edition>" in output
    assert "dicom-kb build-fixture --edition 2026b" in output


def _normalized_cli_output(output: str) -> str:
    return " ".join(strip_ansi(output).translate(_RICH_BOX_CHARS).split())


def test_mcp_cli_exposes_serve_command_without_optional_dependency() -> None:
    result = CliRunner().invoke(app, ["mcp", "serve", "--help"])

    assert result.exit_code == 0, result.output

    mcp_command = get_command(app).commands["mcp"]
    serve_command = mcp_command.commands["serve"]
    option_names = {
        option for parameter in serve_command.params for option in parameter.opts
    }
    assert "--edition" in option_names
    assert "--db" in option_names


def test_serve_mcp_stdio_reports_missing_optional_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dicom_kb.mcp import server

    def fail_load_fastmcp() -> object:
        raise MissingMCPDependencyError("missing mcp")

    monkeypatch.setattr(server, "_load_fastmcp", fail_load_fastmcp)

    with pytest.raises(MissingMCPDependencyError, match="missing mcp"):
        serve_mcp_stdio(MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)))
