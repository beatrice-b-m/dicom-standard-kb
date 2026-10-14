"""Exact entity lookup commands."""

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
    lookup_dicomweb_transaction,
    lookup_media_type,
    lookup_transfer_syntax,
    lookup_uid,
    lookup_vr,
)

lookup_app = typer.Typer(help="Run exact lookups against a local SQLite KB.")


@lookup_app.command("uid")
def lookup_uid_command(
    ctx: typer.Context,
    uid_or_keyword: Annotated[
        str,
        typer.Argument(help="DICOM UID value or UID keyword."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Look up a PS3.6 UID registry entry by UID value or keyword."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            lookup_uid(
                connection,
                uid_or_keyword=uid_or_keyword,
                edition=resolved_edition,
            )
        )


@lookup_app.command("vr")
def lookup_vr_command(
    ctx: typer.Context,
    vr: Annotated[
        str,
        typer.Argument(help="Two-letter DICOM Value Representation code."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Look up a PS3.5 Value Representation definition."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            lookup_vr(
                connection,
                vr=vr,
                edition=resolved_edition,
            )
        )


@lookup_app.command("transfer-syntax")
def lookup_transfer_syntax_command(
    ctx: typer.Context,
    uid_or_keyword: Annotated[
        str,
        typer.Argument(help="DICOM Transfer Syntax UID value, name, or keyword."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Look up transfer syntax UID metadata and encoding details."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            lookup_transfer_syntax(
                connection,
                uid_or_keyword=uid_or_keyword,
                edition=resolved_edition,
            )
        )


@lookup_app.command("media-type")
def lookup_media_type_command(
    ctx: typer.Context,
    media_type_or_context: Annotated[
        str,
        typer.Argument(help="DICOM media type or service context."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Look up DICOM media type constraints by media type or context."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            lookup_media_type(
                connection,
                media_type_or_context=media_type_or_context,
                edition=resolved_edition,
            )
        )


@lookup_app.command("dicomweb")
def lookup_dicomweb_command(
    ctx: typer.Context,
    name_or_route: Annotated[
        str,
        typer.Argument(help="DICOMweb transaction name or route template."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Look up a PS3.18 DICOMweb transaction by name or route."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            lookup_dicomweb_transaction(
                connection,
                name_or_route=name_or_route,
                edition=resolved_edition,
            )
        )
