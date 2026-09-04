"""Tool registration and dispatch for the MCP adapter."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any, cast

from dicom_kb.query.answer_contracts import ToolResponse
from dicom_kb.query.resolver import (
    explain_encoding_rule,
    list_attributes_for_module,
    list_modules_for_iod,
    lookup_code_meaning,
    lookup_context_group,
    lookup_data_element,
    lookup_defined_terms,
    lookup_dicomweb_transaction,
    lookup_enumerated_values,
    lookup_iod,
    lookup_media_type,
    lookup_sop_class,
    lookup_sr_template,
    lookup_transfer_syntax,
    lookup_uid,
    lookup_vr,
    resolve_attribute_context,
    retrieve_standard_text,
    search_standard_text,
)

from .schemas import MCP_TOOL_SPECS, MCPToolName

MCPToolFunction = Callable[..., dict[str, Any]]
MCPToolDecorator = Callable[[MCPToolFunction], MCPToolFunction]
MCPToolExecutor = Callable[[MCPToolName, dict[str, Any]], dict[str, Any]]


def dispatch_mcp_tool(
    connection: sqlite3.Connection,
    *,
    tool_name: MCPToolName,
    arguments: dict[str, Any],
    edition: str,
) -> ToolResponse:
    """Dispatch an MCP tool name into the public resolver layer."""
    handlers: dict[MCPToolName, Callable[[], ToolResponse]] = {
        "dicom_lookup_data_element": lambda: lookup_data_element(
            connection,
            tag_or_keyword=str(arguments["tag_or_keyword"]),
            edition=edition,
        ),
        "dicom_lookup_uid": lambda: lookup_uid(
            connection,
            uid_or_keyword=str(arguments["uid_or_keyword"]),
            edition=edition,
        ),
        "dicom_lookup_sop_class": lambda: lookup_sop_class(
            connection,
            uid_or_name_or_keyword=str(arguments["uid_or_name_or_keyword"]),
            edition=edition,
        ),
        "dicom_lookup_iod": lambda: lookup_iod(
            connection,
            iod_name=str(arguments["iod_name"]),
            edition=edition,
        ),
        "dicom_lookup_enumerated_values": lambda: lookup_enumerated_values(
            connection,
            attribute=str(arguments["attribute"]),
            edition=edition,
            context=_optional_string(arguments.get("context")),
        ),
        "dicom_lookup_defined_terms": lambda: lookup_defined_terms(
            connection,
            attribute=str(arguments["attribute"]),
            edition=edition,
            context=_optional_string(arguments.get("context")),
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
        "dicom_lookup_sr_template": lambda: lookup_sr_template(
            connection,
            tid_or_name=str(arguments["tid_or_name"]),
            edition=edition,
        ),
        "dicom_lookup_context_group": lambda: lookup_context_group(
            connection,
            cid_or_name=str(arguments["cid_or_name"]),
            edition=edition,
        ),
        "dicom_lookup_code_meaning": lambda: lookup_code_meaning(
            connection,
            code_value=str(arguments["code_value"]),
            scheme=_optional_string(arguments.get("scheme")),
            edition=edition,
        ),
        "dicom_list_modules_for_iod": lambda: list_modules_for_iod(
            connection,
            iod_name=str(arguments["iod_name"]),
            edition=edition,
        ),
        "dicom_list_attributes_for_module": lambda: list_attributes_for_module(
            connection,
            module_name=str(arguments["module_name"]),
            edition=edition,
            expand_macros=bool(arguments.get("expand_macros", False)),
        ),
        "dicom_resolve_attribute_context": lambda: resolve_attribute_context(
            connection,
            attribute=str(arguments["attribute"]),
            edition=edition,
            iod_name=_optional_string(arguments.get("iod_name")),
            sop_class=_optional_string(arguments.get("sop_class")),
        ),
        "dicom_retrieve_standard_text": lambda: retrieve_standard_text(
            connection,
            part=str(arguments["part"]),
            section_or_anchor=str(arguments["section_or_anchor"]),
            edition=edition,
            max_chars=int(arguments.get("max_chars", 800)),
        ),
        "dicom_search_standard_text": lambda: search_standard_text(
            connection,
            query=str(arguments["query"]),
            edition=edition,
            part_filter=_optional_string(arguments.get("part_filter")),
            limit=int(arguments.get("limit", 10)),
        ),
    }
    return handlers[tool_name]()


def register_mcp_tools(server: Any, executor: MCPToolExecutor) -> None:
    """Register all supported DICOM MCP tools on a FastMCP server."""
    for spec in MCP_TOOL_SPECS:
        if spec["name"] == "dicom_lookup_data_element":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_data_element(tag_or_keyword: str) -> dict[str, Any]:
                return executor(
                    "dicom_lookup_data_element",
                    {"tag_or_keyword": tag_or_keyword},
                )

        elif spec["name"] == "dicom_lookup_uid":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_uid(uid_or_keyword: str) -> dict[str, Any]:
                return executor("dicom_lookup_uid", {"uid_or_keyword": uid_or_keyword})

        elif spec["name"] == "dicom_lookup_sop_class":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_sop_class(
                uid_or_name_or_keyword: str,
            ) -> dict[str, Any]:
                return executor(
                    "dicom_lookup_sop_class",
                    {"uid_or_name_or_keyword": uid_or_name_or_keyword},
                )

        elif spec["name"] == "dicom_lookup_iod":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_iod(iod_name: str) -> dict[str, Any]:
                return executor("dicom_lookup_iod", {"iod_name": iod_name})

        elif spec["name"] == "dicom_lookup_enumerated_values":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_enumerated_values(
                attribute: str,
                context: str | None = None,
            ) -> dict[str, Any]:
                return executor(
                    "dicom_lookup_enumerated_values",
                    {"attribute": attribute, "context": context},
                )

        elif spec["name"] == "dicom_lookup_defined_terms":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_defined_terms(
                attribute: str,
                context: str | None = None,
            ) -> dict[str, Any]:
                return executor(
                    "dicom_lookup_defined_terms",
                    {"attribute": attribute, "context": context},
                )

        elif spec["name"] == "dicom_lookup_vr":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_vr(vr: str) -> dict[str, Any]:
                return executor("dicom_lookup_vr", {"vr": vr})

        elif spec["name"] == "dicom_lookup_transfer_syntax":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_transfer_syntax(uid_or_keyword: str) -> dict[str, Any]:
                return executor(
                    "dicom_lookup_transfer_syntax",
                    {"uid_or_keyword": uid_or_keyword},
                )

        elif spec["name"] == "dicom_explain_encoding_rule":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_explain_encoding_rule(topic: str) -> dict[str, Any]:
                return executor("dicom_explain_encoding_rule", {"topic": topic})

        elif spec["name"] == "dicom_lookup_media_type":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_media_type(
                media_type_or_context: str,
            ) -> dict[str, Any]:
                return executor(
                    "dicom_lookup_media_type",
                    {"media_type_or_context": media_type_or_context},
                )

        elif spec["name"] == "dicom_lookup_dicomweb_transaction":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_dicomweb_transaction(
                name_or_route: str,
            ) -> dict[str, Any]:
                return executor(
                    "dicom_lookup_dicomweb_transaction",
                    {"name_or_route": name_or_route},
                )

        elif spec["name"] == "dicom_lookup_sr_template":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_sr_template(tid_or_name: str) -> dict[str, Any]:
                return executor(
                    "dicom_lookup_sr_template",
                    {"tid_or_name": tid_or_name},
                )

        elif spec["name"] == "dicom_lookup_context_group":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_context_group(cid_or_name: str) -> dict[str, Any]:
                return executor(
                    "dicom_lookup_context_group",
                    {"cid_or_name": cid_or_name},
                )

        elif spec["name"] == "dicom_lookup_code_meaning":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_lookup_code_meaning(
                code_value: str,
                scheme: str | None = None,
            ) -> dict[str, Any]:
                return executor(
                    "dicom_lookup_code_meaning",
                    {"code_value": code_value, "scheme": scheme},
                )

        elif spec["name"] == "dicom_list_modules_for_iod":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_list_modules_for_iod(iod_name: str) -> dict[str, Any]:
                return executor("dicom_list_modules_for_iod", {"iod_name": iod_name})

        elif spec["name"] == "dicom_list_attributes_for_module":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_list_attributes_for_module(
                module_name: str,
                expand_macros: bool = False,
            ) -> dict[str, Any]:
                return executor(
                    "dicom_list_attributes_for_module",
                    {
                        "module_name": module_name,
                        "expand_macros": expand_macros,
                    },
                )

        elif spec["name"] == "dicom_resolve_attribute_context":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_resolve_attribute_context(
                attribute: str,
                iod_name: str | None = None,
                sop_class: str | None = None,
            ) -> dict[str, Any]:
                return executor(
                    "dicom_resolve_attribute_context",
                    {
                        "attribute": attribute,
                        "iod_name": iod_name,
                        "sop_class": sop_class,
                    },
                )

        elif spec["name"] == "dicom_retrieve_standard_text":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_retrieve_standard_text(
                part: str,
                section_or_anchor: str,
                max_chars: int = 800,
            ) -> dict[str, Any]:
                return executor(
                    "dicom_retrieve_standard_text",
                    {
                        "part": part,
                        "section_or_anchor": section_or_anchor,
                        "max_chars": max_chars,
                    },
                )

        elif spec["name"] == "dicom_search_standard_text":

            @_tool(server, name=spec["name"], description=spec["description"])
            def dicom_search_standard_text(
                query: str,
                part_filter: str | None = None,
                limit: int = 10,
            ) -> dict[str, Any]:
                return executor(
                    "dicom_search_standard_text",
                    {
                        "query": query,
                        "part_filter": part_filter,
                        "limit": limit,
                    },
                )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _tool(server: Any, *, name: str, description: str) -> MCPToolDecorator:
    return cast(
        MCPToolDecorator,
        server.tool(name=name, description=description),
    )
