from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import anyio
import pytest

from dicom_kb.mcp.server import MCP_TOOL_NAMES
from tests.unit.test_cli_lookup import _fixture_db

mcp = pytest.importorskip("mcp")
stdio = pytest.importorskip("mcp.client.stdio")


def test_mcp_stdio_protocol_with_official_client(tmp_path: Path) -> None:
    db_path = _fixture_db(tmp_path)

    async def run_client() -> None:
        from mcp import ClientSession
        from mcp.client.stdio import StdioServerParameters, stdio_client

        parameters = StdioServerParameters(
            command=sys.executable,
            args=[
                "-c",
                "from dicom_kb.cli.main import app; app()",
                "mcp",
                "serve",
                "--edition",
                "2026b",
                "--db",
                str(db_path),
            ],
            cwd=Path.cwd(),
        )
        async with (
            stdio_client(parameters) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            initialized = await session.initialize()
            assert initialized.serverInfo.name == "dicom-standard-kb"

            listed = await session.list_tools()
            tools_by_name = {tool.name: tool for tool in listed.tools}
            assert tuple(tools_by_name) == MCP_TOOL_NAMES
            for tool_name in MCP_TOOL_NAMES:
                schema = tools_by_name[tool_name].inputSchema
                assert schema["type"] == "object"
                assert schema["properties"]

            element_result = await session.call_tool(
                "dicom_element",
                {"name": "Modality"},
            )
            assert element_result.structuredContent is None
            assert _tool_text(element_result) == (
                "**(0008,0060) Modality** `Modality` · VR CS · VM 1\n"
                "\n"
                "No PS3.3 module or macro lists it.\n"
                "\n"
                "Source: PS3.6 Table 6-1 (2026b)\n"
            )

            modules_result = await session.call_tool(
                "dicom_iod",
                {"name": "CT Image"},
            )
            modules_text = _tool_text(modules_result)
            assert modules_text.startswith("**CT Image IOD**")
            assert "| Patient | Patient | C.7.1.1, Table C.7-1 | M |" in modules_text

            code_meaning_result = await session.call_tool(
                "dicom_lookup_code_meaning",
                {"code_value": "CT", "scheme": "DCM"},
            )
            assert "**Code meaning:** Computed Tomography" in _tool_text(
                code_meaning_result
            )

    anyio.run(run_client)


def _tool_text(result: Any) -> str:
    assert not result.isError
    assert len(result.content) == 1
    return str(result.content[0].text)
