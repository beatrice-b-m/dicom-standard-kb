"""Exact entity lookup commands."""

from __future__ import annotations

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
    lookup_code_meaning,
    lookup_context_group,
    lookup_data_element,
    lookup_defined_terms,
    lookup_dicomweb_transaction,
    lookup_enumerated_values,
    lookup_iod,
    lookup_media_type,
    lookup_sop_class,
    lookup_sr_template,
    lookup_transfer_syntax,
    lookup_uid,
    lookup_vr,
)

lookup_app = typer.Typer(help="Run exact lookups against a local SQLite KB.")


@lookup_app.command("tag")
def lookup_tag(
    ctx: typer.Context,
    tag_or_keyword: Annotated[
        str,
        typer.Argument(help="DICOM tag like (0008,0060), range tag, or keyword."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Look up a PS3.6 data element by tag or keyword."""
    resolved_edition = resolve_edition(ctx, edition)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            lookup_data_element(
                connection,
                tag_or_keyword=tag_or_keyword,
                edition=resolved_edition,
            )
        )


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
    resolved_edition = resolve_edition(ctx, edition)
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
    resolved_edition = resolve_edition(ctx, edition)
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
    resolved_edition = resolve_edition(ctx, edition)
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
    resolved_edition = resolve_edition(ctx, edition)
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
    resolved_edition = resolve_edition(ctx, edition)
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


@lookup_app.command("sr-template")
def lookup_sr_template_command(
    ctx: typer.Context,
    tid_or_name: Annotated[
        str,
        typer.Argument(help="PS3.16 SR template TID or exact template name."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Look up a PS3.16 SR template by TID or exact name."""
    resolved_edition = resolve_edition(ctx, edition)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            lookup_sr_template(
                connection,
                tid_or_name=tid_or_name,
                edition=resolved_edition,
            )
        )


@lookup_app.command("context-group")
def lookup_context_group_command(
    ctx: typer.Context,
    cid_or_name: Annotated[
        str,
        typer.Argument(help="PS3.16 context group CID or exact context group name."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Look up a PS3.16 context group by CID or exact name."""
    resolved_edition = resolve_edition(ctx, edition)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            lookup_context_group(
                connection,
                cid_or_name=cid_or_name,
                edition=resolved_edition,
            )
        )


@lookup_app.command("code")
def lookup_code_command(
    ctx: typer.Context,
    code_value: Annotated[
        str,
        typer.Argument(help="PS3.16 coded concept code value."),
    ],
    scheme: Annotated[
        str | None,
        typer.Option("--scheme", help="Optional coding scheme designator."),
    ] = None,
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Look up a PS3.16 coded concept by code value and optional scheme."""
    resolved_edition = resolve_edition(ctx, edition)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            lookup_code_meaning(
                connection,
                code_value=code_value,
                scheme=scheme,
                edition=resolved_edition,
            )
        )


@lookup_app.command("iod")
def lookup_iod_command(
    ctx: typer.Context,
    iod_name: Annotated[
        str,
        typer.Argument(help="DICOM IOD name or keyword, for example 'CT Image'."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Look up a PS3.3 IOD by name or keyword."""
    resolved_edition = resolve_edition(ctx, edition)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            lookup_iod(
                connection,
                iod_name=iod_name,
                edition=resolved_edition,
            )
        )


@lookup_app.command("sop-class")
def lookup_sop_class_command(
    ctx: typer.Context,
    uid_or_name_or_keyword: Annotated[
        str,
        typer.Argument(help="DICOM SOP Class UID, name, or UID keyword."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
) -> None:
    """Look up a PS3.4 SOP Class and linked IODs."""
    resolved_edition = resolve_edition(ctx, edition)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            lookup_sop_class(
                connection,
                uid_or_name_or_keyword=uid_or_name_or_keyword,
                edition=resolved_edition,
            )
        )


@lookup_app.command("enumerated-values")
def lookup_enumerated_values_command(
    ctx: typer.Context,
    attribute: Annotated[
        str,
        typer.Argument(help="DICOM attribute tag, keyword, or name."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
    context: Annotated[
        str | None,
        typer.Option("--context", help="Optional module, macro, or context label."),
    ] = None,
) -> None:
    """Look up parsed enumerated values for a DICOM attribute."""
    resolved_edition = resolve_edition(ctx, edition)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            lookup_enumerated_values(
                connection,
                attribute=attribute,
                edition=resolved_edition,
                context=context,
            )
        )


@lookup_app.command("defined-terms")
def lookup_defined_terms_command(
    ctx: typer.Context,
    attribute: Annotated[
        str,
        typer.Argument(help="DICOM attribute tag, keyword, or name."),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
    context: Annotated[
        str | None,
        typer.Option("--context", help="Optional module, macro, or context label."),
    ] = None,
) -> None:
    """Look up parsed defined terms for a DICOM attribute."""
    resolved_edition = resolve_edition(ctx, edition)
    with connect_query_db(
        resolve_db_path(ctx, db),
        cache_dir=resolve_cache_dir(ctx, cache_dir),
        edition=resolved_edition,
    ) as connection:
        echo_response(
            lookup_defined_terms(
                connection,
                attribute=attribute,
                edition=resolved_edition,
                context=context,
            )
        )
