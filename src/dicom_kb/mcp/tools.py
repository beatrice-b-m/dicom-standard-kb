"""Tool registration and dispatch for the MCP adapter."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any, cast

from dicom_kb.query.answer_contracts import ToolResponse
from dicom_kb.query.resolver import (
    attribute_values,
    code_lookup,
    explain_encoding_rule,
    lookup_dicomweb_transaction,
    lookup_media_type,
    lookup_transfer_syntax,
    lookup_uid,
    lookup_vr,
    read_standard,
    search_standard,
)
from dicom_kb.query.resolver.objects import (
    element_usage,
    iod_modules,
    module_attributes,
)

from .schemas import MCP_TOOL_SPECS, MCPToolName

MCPToolFunction = Callable[..., str]
MCPToolDecorator = Callable[[MCPToolFunction], MCPToolFunction]
MCPToolExecutor = Callable[[MCPToolName, dict[str, Any]], str]


def dispatch_mcp_tool(
    connection: sqlite3.Connection,
    *,
    tool_name: MCPToolName,
    arguments: dict[str, Any],
    edition: str,
) -> ToolResponse:
    """Dispatch an MCP tool name into the public resolver layer."""
    handlers: dict[MCPToolName, Callable[[], ToolResponse]] = {
        "dicom_lookup_uid": lambda: lookup_uid(
            connection,
            uid_or_keyword=str(arguments["uid_or_keyword"]),
            edition=edition,
        ),
        "dicom_lookup_vr": lambda: lookup_vr(
            connection,
            vr=str(arguments["vr"]),
            edition=edition,
        ),
        "dicom_lookup_transfer_syntax": lambda: lookup_transfer_syntax(
            connection,
            uid_or_keyword=str(arguments["uid_or_keyword"]),
            edition=edition,
        ),
        "dicom_explain_encoding_rule": lambda: explain_encoding_rule(
            connection,
            topic=str(arguments["topic"]),
            edition=edition,
        ),
        "dicom_lookup_media_type": lambda: lookup_media_type(
            connection,
            media_type_or_context=str(arguments["media_type_or_context"]),
            edition=edition,
        ),
        "dicom_lookup_dicomweb_transaction": lambda: lookup_dicomweb_transaction(
            connection,
            name_or_route=str(arguments["name_or_route"]),
            edition=edition,
        ),
        "dicom_element": lambda: element_usage(
            connection,
            name=str(arguments["name"]),
            edition=edition,
            iod=_optional_string(arguments.get("iod")),
        ),
        "dicom_iod": lambda: iod_modules(
            connection,
            name=str(arguments["name"]),
            edition=edition,
            expand=bool(arguments.get("expand", False)),
            page=int(arguments.get("page", 1)),
        ),
        "dicom_module": lambda: module_attributes(
            connection,
            name=str(arguments["name"]),
            edition=edition,
            page=int(arguments.get("page", 1)),
        ),
        "dicom_values": lambda: attribute_values(
            connection,
            name=str(arguments["name"]),
            edition=edition,
            within=_optional_string(arguments.get("within")),
            page=int(arguments.get("page", 1)),
        ),
        "dicom_code": lambda: code_lookup(
            connection,
            query=str(arguments["query"]),
            edition=edition,
            scheme=_optional_string(arguments.get("scheme")),
            page=int(arguments.get("page", 1)),
        ),
        "dicom_search": lambda: search_standard(
            connection,
            query=str(arguments["query"]),
            edition=edition,
            part=_optional_string(arguments.get("part")),
            limit=int(arguments.get("limit", 10)),
        ),
        "dicom_read": lambda: read_standard(
            connection,
            reference=str(arguments["ref"]),
            edition=edition,
            page=int(arguments.get("page", 1)),
        ),
    }
    return handlers[tool_name]()


def register_mcp_tools(server: Any, executor: MCPToolExecutor) -> None:
    """Register all supported DICOM MCP tools on a FastMCP server."""
    for spec in MCP_TOOL_SPECS:
        if spec["name"] == "dicom_lookup_uid":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_uid(uid_or_keyword: str) -> str:
                return executor("dicom_lookup_uid", {"uid_or_keyword": uid_or_keyword})

        elif spec["name"] == "dicom_lookup_vr":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_vr(vr: str) -> str:
                return executor("dicom_lookup_vr", {"vr": vr})

        elif spec["name"] == "dicom_lookup_transfer_syntax":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_transfer_syntax(uid_or_keyword: str) -> str:
                return executor(
                    "dicom_lookup_transfer_syntax",
                    {"uid_or_keyword": uid_or_keyword},
                )

        elif spec["name"] == "dicom_explain_encoding_rule":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_explain_encoding_rule(topic: str) -> str:
                return executor("dicom_explain_encoding_rule", {"topic": topic})

        elif spec["name"] == "dicom_lookup_media_type":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_media_type(
                media_type_or_context: str,
            ) -> str:
                return executor(
                    "dicom_lookup_media_type",
                    {"media_type_or_context": media_type_or_context},
                )

        elif spec["name"] == "dicom_lookup_dicomweb_transaction":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_dicomweb_transaction(
                name_or_route: str,
            ) -> str:
                return executor(
                    "dicom_lookup_dicomweb_transaction",
                    {"name_or_route": name_or_route},
                )

        elif spec["name"] == "dicom_element":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_element(name: str, iod: str | None = None) -> str:
                return executor("dicom_element", {"name": name, "iod": iod})

        elif spec["name"] == "dicom_iod":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_iod(name: str, expand: bool = False, page: int = 1) -> str:
                return executor(
                    "dicom_iod", {"name": name, "expand": expand, "page": page}
                )

        elif spec["name"] == "dicom_module":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_module(name: str, page: int = 1) -> str:
                return executor("dicom_module", {"name": name, "page": page})

        elif spec["name"] == "dicom_values":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_values(
                name: str, within: str | None = None, page: int = 1
            ) -> str:
                return executor(
                    "dicom_values", {"name": name, "within": within, "page": page}
                )

        elif spec["name"] == "dicom_code":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_code(query: str, scheme: str | None = None, page: int = 1) -> str:
                return executor(
                    "dicom_code", {"query": query, "scheme": scheme, "page": page}
                )

        elif spec["name"] == "dicom_search":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_search(
                query: str,
                part: str | None = None,
                limit: int = 10,
            ) -> str:
                return executor(
                    "dicom_search",
                    {"query": query, "part": part, "limit": limit},
                )

        elif spec["name"] == "dicom_read":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_read(ref: str, page: int = 1) -> str:
                return executor("dicom_read", {"ref": ref, "page": page})


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _tool(server: Any, *, name: str, description: str) -> MCPToolDecorator:
    # Markdown goes out as plain text content only; structured output would
    # send the same answer a second time as a JSON-wrapped copy.
    return cast(
        MCPToolDecorator,
        server.tool(name=name, description=description, structured_output=False),
    )
