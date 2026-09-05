"""Compose the public CLI from focused command modules."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from dicom_kb.cli import evaluation, graph, ingest, lookup, mcp, text
from dicom_kb.config import ConfigError, DicomKBConfig, load_config_profile
from dicom_kb.metadata import LEGAL_NOTICE, __version__

app = typer.Typer(
    help="Build and query a local DICOM standard knowledge base.",
    invoke_without_command=True,
    no_args_is_help=True,
)
app.add_typer(ingest.app)
app.add_typer(text.app)
app.add_typer(lookup.lookup_app, name="lookup")
app.add_typer(graph.iod_app, name="iod")
app.add_typer(graph.module_app, name="module")
app.add_typer(graph.resolve_app, name="resolve")
app.add_typer(graph.context_app, name="context")
app.add_typer(text.explain_app, name="explain")
app.add_typer(mcp.mcp_app, name="mcp")
app.add_typer(evaluation.eval_app, name="eval")


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", help="Show version and exit."),
    ] = False,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            help="YAML config profile with a top-level dicom_kb mapping.",
        ),
    ] = None,
) -> None:
    """Show startup metadata for every CLI invocation."""
    if version:
        typer.echo(f"dicom-standard-kb {__version__}")
        raise typer.Exit()
    ctx.obj = DicomKBConfig()
    if config is not None:
        try:
            ctx.obj = load_config_profile(config)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc


@app.command()
def doctor() -> None:
    """Print local diagnostic metadata."""
    typer.echo(f"dicom-standard-kb {__version__}")
    typer.echo(LEGAL_NOTICE)
