"""IOD, module and data element commands: what an object needs."""

from __future__ import annotations

from typing import Annotated

import typer

from dicom_kb.cli.context import (
    connect_query_db,
    echo_response,
    resolve_cache_dir,
    resolve_db_path,
    resolve_query_edition,
)
from dicom_kb.cli.options import CacheDirectoryOption, DatabaseOption, EditionOption
from dicom_kb.query.resolver import element_usage, iod_modules, module_attributes

app = typer.Typer()

PageOption = Annotated[int, typer.Option("--page", help="Page to read.")]


@app.command("element")
def element_command(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Tag like (0028,0030), keyword, or name."),
    ],
    iod: Annotated[
        str | None,
        typer.Option("--iod", help="Show its Type and nesting in this IOD."),
    ] = None,
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Look up a data element and the modules that use it."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            element_usage(connection, name=name, edition=resolved_edition, iod=iod)
        )


@app.command("iod")
def iod_command(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="IOD name, or SOP Class name, UID or keyword."),
    ],
    expand: Annotated[
        bool,
        typer.Option("--expand", help="List every attribute of every module."),
    ] = False,
    page: PageOption = 1,
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """List an IOD's modules, or with --expand every attribute it needs."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            iod_modules(
                connection,
                name=name,
                edition=resolved_edition,
                expand=expand,
                page=page,
            )
        )


@app.command("module")
def module_command(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Module or macro name, or a table like 'C.7-5a'."),
    ],
    page: PageOption = 1,
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """List a module's or macro's attributes with its macros expanded."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            module_attributes(
                connection, name=name, edition=resolved_edition, page=page
            )
        )
