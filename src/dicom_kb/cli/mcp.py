"""MCP stdio launch command."""

from __future__ import annotations

import typer

from dicom_kb.cli.context import (
    resolve_cache_dir,
    resolve_db_path,
    resolve_edition,
)
from dicom_kb.cli.options import CacheDirectoryOption, DatabaseOption, EditionOption
from dicom_kb.mcp.server import (
    MCPServerConfig,
    MissingMCPDependencyError,
    serve_mcp_stdio,
)

mcp_app = typer.Typer(help="Run the MCP server adapter.")


@mcp_app.command("serve")
def mcp_serve_command(
    ctx: typer.Context,
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Serve query tools over MCP stdio."""
    config = MCPServerConfig(
        edition=resolve_edition(ctx, edition),
        db_path=resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
    )
    try:
        serve_mcp_stdio(config)
    except MissingMCPDependencyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
