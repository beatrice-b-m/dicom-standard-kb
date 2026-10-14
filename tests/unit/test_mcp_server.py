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
    function: Callable[..., str]


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
        structured_output: bool | None = None,
    ) -> Callable[[Callable[..., str]], Callable[..., str]]:
        assert structured_output is False

        def decorator(
            function: Callable[..., str],
        ) -> Callable[..., str]:
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
        "dicom_search",
        "dicom_read",
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

    payload = fake_server.tools["dicom_search"].function(
        "Patient name",
        part="PS3.3",
        limit=2,
    )

    assert payload.startswith("| Ref | Title | Context |")
    assert len([line for line in payload.splitlines() if "| PS3.3 " in line]) <= 2


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


def test_execute_mcp_tool_returns_compact_markdown(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_lookup_data_element",
        {"tag_or_keyword": "Modality"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload == (
        "**(0008,0060) Modality**\n"
        "Keyword `Modality` · VR CS · VM 1\n"
        "\n"
        "Source: PS3.6 Table 6-1 (2026b)\n"
    )


@pytest.mark.parametrize(
    ("tool", "arguments", "expected"),
    [
        (
            "dicom_list_attributes_for_module",
            {"module_name": "Patient", "expand_macros": True},
            ["| Attribute | Tag | Type |", "Include", "Anatomic Region Sequence"],
        ),
        (
            "dicom_resolve_attribute_context",
            {"attribute": "PatientName", "iod_name": "CT Image"},
            ["Effective Type: 2", "| CT Image | Patient |"],
        ),
        (
            "dicom_lookup_vr",
            {"vr": "ob"},
            ["**Vr:** OB", "**Binary or text:** binary", "Source: PS3.5"],
        ),
        (
            "dicom_lookup_transfer_syntax",
            {"uid_or_keyword": "ImplicitVRLittleEndian"},
            ["1.2.840.10008.1.2", "**Explicit vr:** no", "**Endian:** little"],
        ),
        (
            "dicom_explain_encoding_rule",
            {"topic": "PN"},
            ["PN is the Person Name VR.", "value representation class"],
        ),
        (
            "dicom_lookup_media_type",
            {"media_type_or_context": "file"},
            ["**Media type:** application/dicom", "Source: PS3.10"],
        ),
        (
            "dicom_lookup_media_type",
            {"media_type_or_context": "STOW-RS request"},
            ["**Media type:** multipart/related", "Source: PS3.18"],
        ),
        (
            "dicom_lookup_dicomweb_transaction",
            {"name_or_route": "RetrieveStudy"},
            ["**Route template:** /studies/{studyInstanceUID}", "- 404"],
        ),
        (
            "dicom_lookup_sr_template",
            {"tid_or_name": "TID 1500"},
            ["**TID 1500 Measurement Report**", "Include TID 1501"],
        ),
        (
            "dicom_lookup_context_group",
            {"cid_or_name": "CID 29"},
            ["**CID 29 Acquisition Modality**", "| DCM | CT |", "Include CID 30"],
        ),
        (
            "dicom_lookup_code_meaning",
            {"code_value": "CT", "scheme": "DCM"},
            ["**Code meaning:** Computed Tomography", "- CID 29"],
        ),
        (
            "dicom_lookup_defined_terms",
            {"attribute": "PatientName", "context": "CT Image"},
            ["| ALPHA |", "| IDEOGRAPHIC |"],
        ),
    ],
)
def test_execute_mcp_tool_renders_each_answer_shape(
    tmp_path: Path, tool: str, arguments: dict[str, Any], expected: list[str]
) -> None:
    payload = execute_mcp_tool(
        tool,  # type: ignore[arg-type]
        arguments,
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    for fragment in expected:
        assert fragment in payload
    assert payload.rstrip().splitlines()[-1].startswith("Source: ")
    assert '"status"' not in payload


def test_execute_mcp_tool_not_found_is_one_line(tmp_path: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_lookup_data_element",
        {"tag_or_keyword": "(0008,9999)"},
        config=MCPServerConfig(edition="2026b", db_path=_fixture_db(tmp_path)),
    )

    assert payload == "No DICOM data element matched the input.\n"


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
    assert "`dicom-kb fetch` followed by `dicom-kb build`" in output


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
