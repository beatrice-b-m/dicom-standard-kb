"""Cited text retrieval and encoding explanation commands."""

from __future__ import annotations

from typing import Annotated

import typer

from dicom_kb.cli.context import (
    connect_query_db,
    echo_response,
    resolve_cache_dir,
    resolve_db_path,
    resolve_edition,
    resolve_max_text_chars,
)
from dicom_kb.cli.options import CacheDirectoryOption, DatabaseOption, EditionOption
from dicom_kb.query.resolver import (
    explain_encoding_rule,
    retrieve_standard_text,
    search_standard_text,
)

app = typer.Typer()
explain_app = typer.Typer(help="Explain cited DICOM rules from a local KB.")


@app.command("retrieve-text")
def retrieve_text_command(
    ctx: typer.Context,
    part: Annotated[
        str,
        typer.Argument(help="DICOM part label, for example PS3.3."),
    ],
    section_or_anchor: Annotated[
        str,
        typer.Argument(help="DocBook xml:id, HTML anchor, or section number."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
    max_chars: Annotated[
        int | None,
        typer.Option("--max-chars", help="Maximum excerpt characters to return."),
    ] = None,
) -> None:
    """Retrieve a capped excerpt from persisted standard text."""
    resolved_edition = resolve_edition(ctx, edition)
    resolved_max_chars = resolve_max_text_chars(ctx, max_chars, default=800)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            retrieve_standard_text(
                connection,
                part=part,
                section_or_anchor=section_or_anchor,
                edition=resolved_edition,
                max_chars=resolved_max_chars,
            )
        )


@app.command("search-text")
def search_text_command(
    ctx: typer.Context,
    query: Annotated[
        str,
        typer.Argument(help="Full-text query over persisted DocBook text."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
    part_filter: Annotated[
        str | None,
        typer.Option("--part", help="Optional DICOM part label, for example PS3.3."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum number of matches to return."),
    ] = 10,
) -> None:
    """Search persisted standard text with SQLite FTS5."""
    resolved_edition = resolve_edition(ctx, edition)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            search_standard_text(
                connection,
                query=query,
                edition=resolved_edition,
                part_filter=part_filter,
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
    resolved_edition = resolve_edition(ctx, edition)
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
