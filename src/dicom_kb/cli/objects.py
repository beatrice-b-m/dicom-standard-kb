"""IOD, module, data element and value commands: what an object needs."""

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
    attribute_values,
    code_lookup,
    element_usage,
    iod_modules,
    module_attributes,
)

app = typer.Typer()

PageOption = Annotated[int, typer.Option("--page", help="Page to read.")]
TypeOption = Annotated[
    str | None,
    typer.Option(
        "--type",
        help="Keep these Types, e.g. '1,1C', or 'required' for 1/1C/2/2C.",
    ),
]


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
        typer.Option("--expand", help="List the attributes of its modules."),
    ] = False,
    type_: TypeOption = None,
    usage: Annotated[
        str | None,
        typer.Option("--usage", help="Module usages to list, default 'M,C'."),
    ] = None,
    module: Annotated[
        str | None,
        typer.Option("--module", help="Only these modules, comma-separated."),
    ] = None,
    page: PageOption = 1,
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """List an IOD's modules, or with --expand the attributes it needs."""
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
                types=type_,
                usage=usage,
                module=module,
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
    full: Annotated[
        bool,
        typer.Option("--full", help="Expand macros, with full descriptions."),
    ] = False,
    type_: TypeOption = None,
    page: PageOption = 1,
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Outline a module's or macro's attributes; --full expands its macros."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            module_attributes(
                connection,
                name=name,
                edition=resolved_edition,
                detail="full" if full else "outline",
                types=type_,
                page=page,
            )
        )


@app.command("values")
def values_command(
    ctx: typer.Context,
    name: Annotated[
        str,
        typer.Argument(help="Tag like (0010,0040), keyword, or name."),
    ],
    within: Annotated[
        str | None,
        typer.Option("--within", help="Keep what applies in this IOD or module."),
    ] = None,
    page: PageOption = 1,
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """List an attribute's enumerated values, defined terms and CIDs."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            attribute_values(
                connection,
                name=name,
                edition=resolved_edition,
                within=within,
                page=page,
            )
        )


@app.command("code")
def code_command(
    ctx: typer.Context,
    query: Annotated[
        str,
        typer.Argument(help="'CID 4031', 'TID 1500', a code value, or a name."),
    ],
    scheme: Annotated[
        str | None,
        typer.Option("--scheme", help="Coding scheme designator, e.g. DCM."),
    ] = None,
    page: PageOption = 1,
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Look up a context group, template or code from PS3.16."""
    resolved_edition = resolve_query_edition(ctx, edition, db=db, cache_dir=cache_dir)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            code_lookup(
                connection,
                query=query,
                edition=resolved_edition,
                scheme=scheme,
                page=page,
            )
        )
