"""Read and search the standard's text."""

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
from dicom_kb.query.resolver import read_standard, search_standard

app = typer.Typer()


@app.command("read")
def read_command(
    ctx: typer.Context,
    ref: Annotated[
        str,
        typer.Argument(
            help="Section or table ('PS3.5 7.5.2', 'Table C.7-5a', 'CID 7010'), "
            "UID or UID keyword, or VR code ('OB')."
        ),
    ],
    page: Annotated[int, typer.Option("--page", help="Page to read.")] = 1,
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Read a section, table, UID or VR of the standard as markdown."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            read_standard(
                connection, reference=ref, edition=resolved_edition, page=page
            )
        )


@app.command("search")
def search_command(
    ctx: typer.Context,
    query: Annotated[str, typer.Argument(help="Words to find in the standard.")],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
    part: Annotated[
        str | None,
        typer.Option("--part", help="Only search one part, e.g. PS3.5."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum number of matches to return."),
    ] = 10,
) -> None:
    """Search every section and table of the standard."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            search_standard(
                connection,
                query=query,
                edition=resolved_edition,
                part=part,
                limit=limit,
            )
        )
