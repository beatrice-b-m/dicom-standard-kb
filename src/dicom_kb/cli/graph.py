"""Graph traversal and attribute-context commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from dicom_kb.cli.context import (
    connect_query_db,
    echo_response,
    resolve_cache_dir,
    resolve_db_path,
    resolve_edition,
)
from dicom_kb.cli.options import CacheDirectoryOption, DatabaseOption, EditionOption
from dicom_kb.query.resolver import (
    list_attributes_for_module,
    list_modules_for_iod,
    resolve_attribute_context,
)

iod_app = typer.Typer(help="Query PS3.3 IOD graph records.")
module_app = typer.Typer(help="Query PS3.3 module graph records.")
resolve_app = typer.Typer(help="Resolve DICOM facts in a usage context.")
context_app = typer.Typer(help="Resolve documented DICOM context examples.")


@iod_app.command("modules")
def iod_modules(
    ctx: typer.Context,
    iod_name: Annotated[
        str,
        typer.Argument(help="DICOM IOD name or keyword, for example 'CT Image'."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """List PS3.3 modules used by an IOD."""
    resolved_edition = resolve_edition(ctx, edition)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            list_modules_for_iod(
                connection,
                iod_name=iod_name,
                edition=resolved_edition,
            )
        )


@module_app.command("attributes")
def module_attributes(
    ctx: typer.Context,
    module_name: Annotated[
        str,
        typer.Argument(help="DICOM module name, for example 'Patient'."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
    expand_macros: Annotated[
        bool,
        typer.Option(
            "--expand-macros/--no-expand-macros",
            help="Inline attributes from included macros after each include row.",
        ),
    ] = False,
) -> None:
    """List PS3.3 attributes used by a module."""
    resolved_edition = resolve_edition(ctx, edition)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            list_attributes_for_module(
                connection,
                module_name=module_name,
                edition=resolved_edition,
                expand_macros=expand_macros,
            )
        )


@resolve_app.command("attribute-context")
def resolve_attribute_context_command(
    ctx: typer.Context,
    attribute: Annotated[
        str,
        typer.Argument(help="DICOM attribute tag, keyword, or name."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
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
    resolved_edition = resolve_edition(ctx, edition)
    _echo_attribute_context_response(
        attribute=attribute,
        edition=resolved_edition,
        db=resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        iod_name=iod_name,
        sop_class=sop_class,
    )


@context_app.command("attribute")
def context_attribute_command(
    ctx: typer.Context,
    attribute: Annotated[
        str,
        typer.Argument(help="DICOM attribute tag, keyword, or name."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
    iod_name: Annotated[
        str | None,
        typer.Option("--iod", help="DICOM IOD name or keyword context."),
    ] = None,
    sop_class: Annotated[
        str | None,
        typer.Option("--sop-class", help="DICOM SOP Class UID, name, or keyword."),
    ] = None,
) -> None:
    """Alias for the documented context attribute resolver example."""
    resolved_edition = resolve_edition(ctx, edition)
    _echo_attribute_context_response(
        attribute=attribute,
        edition=resolved_edition,
        db=resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        iod_name=iod_name,
        sop_class=sop_class,
    )


def _echo_attribute_context_response(
    *,
    attribute: str,
    edition: str,
    db: Path | None,
    cache_dir: Path,
    iod_name: str | None,
    sop_class: str | None,
) -> None:
    with connect_query_db(db, cache_dir=cache_dir, edition=edition) as connection:
        echo_response(
            resolve_attribute_context(
                connection,
                attribute=attribute,
                edition=edition,
                iod_name=iod_name,
                sop_class=sop_class,
            )
        )
