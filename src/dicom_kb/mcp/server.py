"""Model Context Protocol server adapter for query resolvers."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from dicom_kb.build import default_db_path
from dicom_kb.query.answer_contracts import ToolResponse
from dicom_kb.query.resolver import (
    list_attributes_for_module,
    list_modules_for_iod,
    lookup_data_element,
    lookup_iod,
    lookup_sop_class,
    lookup_uid,
    resolve_attribute_context,
    retrieve_standard_text,
    search_standard_text,
)
from dicom_kb.sources.downloader import DEFAULT_CACHE_DIR

MCP_TOOL_NAMES = (
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

MCPToolFunction = Callable[..., dict[str, Any]]
MCPToolDecorator = Callable[[MCPToolFunction], MCPToolFunction]


@dataclass(frozen=True)
class MCPServerConfig:
    """Runtime configuration shared by MCP tool calls."""

    edition: str
    db_path: Path | None = None
    cache_dir: Path = DEFAULT_CACHE_DIR

    @property
    def resolved_db_path(self) -> Path:
        """Return the explicit or conventional SQLite database path."""
        return self.db_path or default_db_path(self.cache_dir, self.edition)


class MissingMCPDependencyError(RuntimeError):
    """Raised when the optional mcp dependency is unavailable."""


def validate_mcp_database(config: MCPServerConfig) -> None:
    """Fail early with an actionable message when the configured KB is missing."""
    path = config.resolved_db_path
    if path.exists():
        return
    raise FileNotFoundError(
        f"SQLite KB does not exist: {path}. Build a local KB with "
        "`dicom-kb fetch --edition current` followed by "
        "`dicom-kb build --edition <resolved-edition>`, or build the offline "
        f"fixture with `dicom-kb build-fixture --edition {config.edition}`. "
        "Pass --db to use a non-default SQLite path."
    )


def execute_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    config: MCPServerConfig,
) -> dict[str, Any]:
    """Execute one MCP tool and return the public JSON response envelope."""
    if tool_name not in MCP_TOOL_NAMES:
        raise ValueError(f"unknown MCP tool: {tool_name}")

    with _connect_query_db(config.resolved_db_path) as connection:
        response = _dispatch_tool(
            connection,
            tool_name=tool_name,
            arguments=arguments,
            edition=config.edition,
        )
    return response.model_dump(mode="json", exclude_none=True)


def create_mcp_server(config: MCPServerConfig) -> Any:
    """Create a FastMCP server with all v1 DICOM query tools registered."""
    fast_mcp = _load_fastmcp()
    server = fast_mcp("dicom-standard-kb")

    @_tool(
        server,
        name="dicom_lookup_data_element",
        description="Look up a DICOM PS3.6 data element by tag, range tag, or keyword.",
    )
    def dicom_lookup_data_element(tag_or_keyword: str) -> dict[str, Any]:
        return execute_mcp_tool(
            "dicom_lookup_data_element",
            {"tag_or_keyword": tag_or_keyword},
            config=config,
        )

    @_tool(
        server,
        name="dicom_lookup_uid",
        description="Look up a DICOM PS3.6 UID registry entry by UID or keyword.",
    )
    def dicom_lookup_uid(uid_or_keyword: str) -> dict[str, Any]:
        return execute_mcp_tool(
            "dicom_lookup_uid",
            {"uid_or_keyword": uid_or_keyword},
            config=config,
        )

    @_tool(
        server,
        name="dicom_lookup_sop_class",
        description="Look up a DICOM PS3.4 SOP Class and linked IOD records.",
    )
    def dicom_lookup_sop_class(uid_or_name_or_keyword: str) -> dict[str, Any]:
        return execute_mcp_tool(
            "dicom_lookup_sop_class",
            {"uid_or_name_or_keyword": uid_or_name_or_keyword},
            config=config,
        )

    @_tool(
        server,
        name="dicom_lookup_iod",
        description="Look up a DICOM PS3.3 IOD by name or keyword.",
    )
    def dicom_lookup_iod(iod_name: str) -> dict[str, Any]:
        return execute_mcp_tool(
            "dicom_lookup_iod",
            {"iod_name": iod_name},
            config=config,
        )

    @_tool(
        server,
        name="dicom_list_modules_for_iod",
        description="List PS3.3 modules used by an IOD.",
    )
    def dicom_list_modules_for_iod(iod_name: str) -> dict[str, Any]:
        return execute_mcp_tool(
            "dicom_list_modules_for_iod",
            {"iod_name": iod_name},
            config=config,
        )

    @_tool(
        server,
        name="dicom_list_attributes_for_module",
        description="List PS3.3 attribute rows for a module.",
    )
    def dicom_list_attributes_for_module(
        module_name: str,
        expand_macros: bool = False,
    ) -> dict[str, Any]:
        return execute_mcp_tool(
            "dicom_list_attributes_for_module",
            {"module_name": module_name, "expand_macros": expand_macros},
            config=config,
        )

    @_tool(
        server,
        name="dicom_resolve_attribute_context",
        description="Resolve a DICOM attribute's effective PS3.3 type in context.",
    )
    def dicom_resolve_attribute_context(
        attribute: str,
        iod_name: str | None = None,
        sop_class: str | None = None,
    ) -> dict[str, Any]:
        return execute_mcp_tool(
            "dicom_resolve_attribute_context",
            {
                "attribute": attribute,
                "iod_name": iod_name,
                "sop_class": sop_class,
            },
            config=config,
        )

    @_tool(
        server,
        name="dicom_retrieve_standard_text",
        description="Retrieve a capped excerpt from persisted DICOM standard text.",
    )
    def dicom_retrieve_standard_text(
        part: str,
        section_or_anchor: str,
        max_chars: int = 800,
    ) -> dict[str, Any]:
        return execute_mcp_tool(
            "dicom_retrieve_standard_text",
            {
                "part": part,
                "section_or_anchor": section_or_anchor,
                "max_chars": max_chars,
            },
            config=config,
        )

    @_tool(
        server,
        name="dicom_search_standard_text",
        description="Search persisted DICOM standard text.",
    )
    def dicom_search_standard_text(
        query: str,
        part_filter: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        return execute_mcp_tool(
            "dicom_search_standard_text",
            {"query": query, "part_filter": part_filter, "limit": limit},
            config=config,
        )

    return server


def serve_mcp_stdio(config: MCPServerConfig) -> None:
    """Run the MCP server over stdio."""
    validate_mcp_database(config)
    server = create_mcp_server(config)
    server.run(transport="stdio")


def _connect_query_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError(f"SQLite KB does not exist: {path}")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _dispatch_tool(
    connection: sqlite3.Connection,
    *,
    tool_name: str,
    arguments: dict[str, Any],
    edition: str,
) -> ToolResponse:
    handlers: dict[str, Callable[[], ToolResponse]] = {
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


def _load_fastmcp() -> Any:
    try:
        module = import_module("mcp.server.fastmcp")
    except ModuleNotFoundError as exc:
        raise MissingMCPDependencyError(
            "MCP support requires the optional dependency; install with "
            "`uv sync --all-extras --dev` or `pip install dicom-standard-kb[mcp]`."
        ) from exc
    return module.FastMCP
