from __future__ import annotations

import json
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
                    "dicom_lookup_data_element",
                    {"tag_or_keyword": "Modality"},
                )
                element_payload = _tool_payload(element_result)
                assert element_payload["edition"] == "2026b"
                assert element_payload["tool"] == "lookup_data_element"
                assert element_payload["status"] == "ok"
                assert element_payload["classification"] == {
                    "evidence_level": "parsed_registry",
                    "machine_decidability": "decidable",
                    "normativity": "normative",
                }
                assert element_payload["parse_confidence"] == {
                    "level": "high",
                    "source": "parsed_registry",
                }
                assert element_payload["refs"]
                assert element_payload["warnings"] == []
                assert "notice" not in element_payload

                modules_result = await session.call_tool(
                    "dicom_list_modules_for_iod",
                    {"iod_name": "CT Image"},
                )
                modules_payload = _tool_payload(modules_result)
                assert modules_payload["edition"] == "2026b"
                assert modules_payload["tool"] == "list_modules_for_iod"
                assert modules_payload["status"] == "ok"
                assert modules_payload["classification"] == {
                    "evidence_level": "parsed_table",
                    "machine_decidability": "decidable",
                    "normativity": "normative",
                }
                assert modules_payload["parse_confidence"] == {
                    "level": "high",
                    "source": "parsed_table",
                }
                assert modules_payload["refs"]
                assert modules_payload["warnings"] == []
                assert "notice" not in modules_payload
                assert modules_payload["result"]["modules"][0]["module_name"] == (
                    "Patient"
                )

    anyio.run(run_client)


def _tool_payload(result: object) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content = result.content
    return json.loads(content[0].text)
