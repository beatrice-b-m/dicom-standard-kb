"""Read and search the standard's text, and explain encoding rules."""

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
from dicom_kb.query.resolver import (
    explain_encoding_rule,
    read_standard,
    search_standard,
)

app = typer.Typer()
explain_app = typer.Typer(help="Explain cited DICOM rules from a local KB.")


@app.command("read")
def read_command(
    ctx: typer.Context,
    ref: Annotated[
        str,
        typer.Argument(
            help="Section or table, e.g. 'PS3.5 7.5.2', 'Table C.7-5a', 'CID 7010'."
        ),
    ],
    page: Annotated[int, typer.Option("--page", help="Page to read.")] = 1,
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Read a section or table of the standard as markdown."""
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


@explain_app.command("encoding")
def explain_encoding_command(
    ctx: typer.Context,
    topic: Annotated[
        str,
        typer.Argument(help="PS3.5 encoding topic, VR, or transfer syntax name."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Explain a PS3.5 encoding rule with citations."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            explain_encoding_rule(
                connection,
                topic=topic,
                edition=resolved_edition,
            )
        )
