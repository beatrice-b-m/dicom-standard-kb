"""Model Context Protocol server creation and stdio serving."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from dicom_kb.build import default_db_path
from dicom_kb.db.models import read_sqlite
from dicom_kb.mcp.schemas import MCP_TOOL_NAMES
from dicom_kb.mcp.tools import dispatch_mcp_tool, register_mcp_tools
from dicom_kb.sources.downloader import DEFAULT_CACHE_DIR


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

    with read_sqlite(config.resolved_db_path) as connection:
        response = dispatch_mcp_tool(
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
    register_mcp_tools(
        server,
        lambda tool_name, arguments: execute_mcp_tool(
            tool_name,
            arguments,
            config=config,
        ),
    )
    return server


def serve_mcp_stdio(config: MCPServerConfig) -> None:
    """Run the MCP server over stdio."""
    validate_mcp_database(config)
    server = create_mcp_server(config)
    server.run(transport="stdio")


def _load_fastmcp() -> Any:
    try:
        module = import_module("mcp.server.fastmcp")
    except ModuleNotFoundError as exc:
        raise MissingMCPDependencyError(
            "MCP support requires the optional dependency; install with "
            "`uv sync --all-extras --dev` or `pip install dicom-standard-kb[mcp]`."
        ) from exc
    return module.FastMCP
