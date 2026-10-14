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
    create_mcp_server,
    execute_mcp_tool,
    serve_mcp_stdio,
)
from tests.fixtures_synthetic import EDITION

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


def test_create_mcp_server_registers_all_supported_tools(
    fixture_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dicom_kb.mcp import server

    monkeypatch.setattr(server, "_load_fastmcp", lambda: _FakeFastMCP)
    fake_server = create_mcp_server(
        MCPServerConfig(edition=EDITION, db_path=fixture_db)
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
    fixture_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dicom_kb.mcp import server

    _FakeFastMCP.last_instance = None
    monkeypatch.setattr(server, "_load_fastmcp", lambda: _FakeFastMCP)

    serve_mcp_stdio(MCPServerConfig(edition=EDITION, db_path=fixture_db))

    assert _FakeFastMCP.last_instance is not None
    assert _FakeFastMCP.last_instance.run_transport == "stdio"


def test_execute_mcp_tool_returns_compact_markdown(fixture_db: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_element",
        {"name": "PatientName"},
        config=MCPServerConfig(edition=EDITION, db_path=fixture_db),
    )

    assert payload == (
        "**(0010,0010) Patient's Name** `PatientName` · VR PN · VM 1\n"
        "\n"
        "| Used in | Reference | Type | Within |\n"
        "|---|---|---|---|\n"
        "| Patient Module | C.7.1.1, Table C.7-1 | 2 |  |\n"
        "\n"
        "In IODs: CT Image.\n"
        "\n"
        f"Source: PS3.6 Table 6-1 ({EDITION})\n"
    )


@pytest.mark.parametrize(
    ("tool", "arguments", "expected"),
    [
        (
            "dicom_module",
            {"name": "Patient", "detail": "full"},
            [
                "| Attribute | Tag | VR | VM | Type |",
                "Include",
                "AnatomicRegionSequence",
            ],
        ),
        (
            "dicom_module",
            {"name": "Table 10-7"},
            ["**General Anatomy Optional Macro** (Table 10-7)"],
        ),
        (
            "dicom_iod",
            {"name": "1.2.840.10008.5.1.4.1.1.2", "expand": True},
            ["### Patient Module: M", "| PatientName | (0010,0010) | PN |"],
        ),
        (
            "dicom_element",
            {"name": "PatientName", "iod": "CT Image Storage"},
            ["In the CT Image IOD:", "| Patient Module | M | 2 |"],
        ),
        (
            "dicom_read",
            {"ref": "VR ob"},
            ["**OB** Other Byte", "**Explicit VR header:**", "Source: PS3.5"],
        ),
        (
            "dicom_read",
            {"ref": "ImplicitVRLittleEndian"},
            [
                "1.2.840.10008.1.2",
                "| Implicit VR | Little Endian | Native | No |",
                "Rules: PS3.5 Section A.1",
            ],
        ),
        (
            "dicom_code",
            {"query": "TID 1500"},
            ["TID 1500", "Measurement Report"],
        ),
        (
            "dicom_code",
            {"query": "CID 29"},
            [
                "**CID 29 Acquisition Modality**",
                "| DCM | CT | Computed Tomography |",
                "Includes CID 34",
            ],
        ),
        (
            "dicom_code",
            {"query": "CT", "scheme": "DCM"},
            ['**(CT, DCM, "Computed Tomography")**', "In CID 29"],
        ),
        (
            "dicom_values",
            {"name": "PatientName"},
            ["**Defined Terms** (Section C.7.1.1.1)", "| ALPHA |", "| IDEOGRAPHIC |"],
        ),
    ],
)
def test_execute_mcp_tool_renders_each_answer_shape(
    fixture_db: Path, tool: str, arguments: dict[str, Any], expected: list[str]
) -> None:
    payload = execute_mcp_tool(
        tool,  # type: ignore[arg-type]
        arguments,
        config=MCPServerConfig(edition=EDITION, db_path=fixture_db),
    )

    for fragment in expected:
        assert fragment in payload
    assert payload.rstrip().splitlines()[-1].startswith("Source: ")
    assert '"status"' not in payload


def test_execute_mcp_tool_not_found_is_one_line(fixture_db: Path) -> None:
    payload = execute_mcp_tool(
        "dicom_element",
        {"name": "(0008,9999)"},
        config=MCPServerConfig(edition=EDITION, db_path=fixture_db),
    )

    assert payload == "No data element is named '(0008,9999)'.\n"


def test_execute_mcp_tool_reports_missing_db(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="SQLite KB does not exist"):
        execute_mcp_tool(
            "dicom_read",
            {"ref": "ExplicitVRLittleEndian"},
            config=MCPServerConfig(
                edition=EDITION,
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
            EDITION,
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
