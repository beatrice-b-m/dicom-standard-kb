"""Typer command-line entrypoint."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Annotated

import typer

from dicom_kb.metadata import LEGAL_NOTICE, __version__
from dicom_kb.query.answer_contracts import ToolResponse
from dicom_kb.query.resolver import (
    list_attributes_for_module,
    list_modules_for_iod,
    lookup_data_element,
    lookup_iod,
    lookup_sop_class,
    lookup_uid,
    resolve_attribute_context,
)

app = typer.Typer(help="Build and query a local DICOM standard knowledge base.")
lookup_app = typer.Typer(help="Run exact lookups against a local SQLite KB.")
iod_app = typer.Typer(help="Query PS3.3 IOD graph records.")
module_app = typer.Typer(help="Query PS3.3 module graph records.")
resolve_app = typer.Typer(help="Resolve DICOM facts in a usage context.")
app.add_typer(lookup_app, name="lookup")
app.add_typer(iod_app, name="iod")
app.add_typer(module_app, name="module")
app.add_typer(resolve_app, name="resolve")


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


@lookup_app.command("tag")
def lookup_tag(
    tag_or_keyword: Annotated[
        str,
        typer.Argument(help="DICOM tag like (0008,0060), range tag, or keyword."),
    ],
    db: Annotated[
        Path,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ],
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
) -> None:
    """Look up a PS3.6 data element by tag or keyword."""
    with _connect_existing_db(db) as connection:
        _echo_response(
            lookup_data_element(
                connection,
                tag_or_keyword=tag_or_keyword,
                edition=edition,
            )
        )


@lookup_app.command("uid")
def lookup_uid_command(
    uid_or_keyword: Annotated[
        str,
        typer.Argument(help="DICOM UID value or UID keyword."),
    ],
    db: Annotated[
        Path,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ],
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
) -> None:
    """Look up a PS3.6 UID registry entry by UID value or keyword."""
    with _connect_existing_db(db) as connection:
        _echo_response(
            lookup_uid(
                connection,
                uid_or_keyword=uid_or_keyword,
                edition=edition,
            )
        )


@lookup_app.command("iod")
def lookup_iod_command(
    iod_name: Annotated[
        str,
        typer.Argument(help="DICOM IOD name or keyword, for example 'CT Image'."),
    ],
    db: Annotated[
        Path,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ],
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
) -> None:
    """Look up a PS3.3 IOD by name or keyword."""
    with _connect_existing_db(db) as connection:
        _echo_response(
            lookup_iod(
                connection,
                iod_name=iod_name,
                edition=edition,
            )
        )


@lookup_app.command("sop-class")
def lookup_sop_class_command(
    uid_or_name_or_keyword: Annotated[
        str,
        typer.Argument(help="DICOM SOP Class UID, name, or UID keyword."),
    ],
    db: Annotated[
        Path,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ],
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
) -> None:
    """Look up a PS3.4 SOP Class and linked IODs."""
    with _connect_existing_db(db) as connection:
        _echo_response(
            lookup_sop_class(
                connection,
                uid_or_name_or_keyword=uid_or_name_or_keyword,
                edition=edition,
            )
        )


@iod_app.command("modules")
def iod_modules(
    iod_name: Annotated[
        str,
        typer.Argument(help="DICOM IOD name or keyword, for example 'CT Image'."),
    ],
    db: Annotated[
        Path,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ],
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
) -> None:
    """List PS3.3 modules used by an IOD."""
    with _connect_existing_db(db) as connection:
        _echo_response(
            list_modules_for_iod(
                connection,
                iod_name=iod_name,
                edition=edition,
            )
        )


@module_app.command("attributes")
def module_attributes(
    module_name: Annotated[
        str,
        typer.Argument(help="DICOM module name, for example 'Patient'."),
    ],
    db: Annotated[
        Path,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ],
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
    expand_macros: Annotated[
        bool,
        typer.Option(
            "--expand-macros/--no-expand-macros",
            help="Inline attributes from included macros after each include row.",
        ),
    ] = False,
) -> None:
    """List PS3.3 attributes used by a module."""
    with _connect_existing_db(db) as connection:
        _echo_response(
            list_attributes_for_module(
                connection,
                module_name=module_name,
                edition=edition,
                expand_macros=expand_macros,
            )
        )


@resolve_app.command("attribute-context")
def resolve_attribute_context_command(
    attribute: Annotated[
        str,
        typer.Argument(help="DICOM attribute tag, keyword, or name."),
    ],
    db: Annotated[
        Path,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ],
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
    iod_name: Annotated[
        str | None,
        typer.Option("--iod", help="DICOM IOD name or keyword context."),
    ] = None,
    sop_class: Annotated[
        str | None,
        typer.Option("--sop-class", help="DICOM SOP Class UID, name, or keyword."),
    ] = None,
) -> None:
    """Resolve an attribute's PS3.3 use and effective type in context."""
    with _connect_existing_db(db) as connection:
        _echo_response(
            resolve_attribute_context(
                connection,
                attribute=attribute,
                edition=edition,
                iod_name=iod_name,
                sop_class=sop_class,
            )
        )


def _connect_existing_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise typer.BadParameter(f"SQLite KB does not exist: {path}")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _echo_response(response: ToolResponse) -> None:
    payload = response.model_dump(mode="json", exclude_none=True)
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))
