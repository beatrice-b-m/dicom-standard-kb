"""Typer command-line entrypoint."""

from __future__ import annotations

import typer

from dicom_kb.metadata import LEGAL_NOTICE, __version__

app = typer.Typer(help="Build and query a local DICOM standard knowledge base.")


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", help="Show version and exit."),
) -> None:
    """Show startup metadata for every CLI invocation."""
    if version:
        typer.echo(f"dicom-standard-kb {__version__}")
        raise typer.Exit()


@app.command()
def doctor() -> None:
    """Print local diagnostic metadata."""
    typer.echo(f"dicom-standard-kb {__version__}")
    typer.echo(LEGAL_NOTICE)


@app.command("build-fixture")
def build_fixture() -> None:
    """Placeholder command for synthetic fixture ingestion."""
    typer.echo("Synthetic fixture ingestion is not implemented yet.")
