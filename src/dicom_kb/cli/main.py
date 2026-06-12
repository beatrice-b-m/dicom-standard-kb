"""Typer command-line entrypoint."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel

from dicom_kb.build import build_sqlite_database, default_db_path
from dicom_kb.mcp.server import (
    MCPServerConfig,
    MissingMCPDependencyError,
    serve_mcp_stdio,
)
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
    retrieve_standard_text,
    search_standard_text,
)
from dicom_kb.sources.downloader import (
    DEFAULT_CACHE_DIR,
    DEFAULT_DICOM_ARCHIVE_BASE_URL,
    DEFAULT_DICOM_CURRENT_BASE_URL,
    DOCBOOK_XML_FORMAT,
    OFFICIAL_ARTIFACT_FORMATS,
    V1_DOCBOOK_PARTS,
    ArtifactRequest,
    OfficialFetchError,
    fetch_official_artifacts,
    official_artifact_destination,
    register_local_artifacts,
)
from dicom_kb.sources.edition_resolver import EditionResolver

app = typer.Typer(help="Build and query a local DICOM standard knowledge base.")
lookup_app = typer.Typer(help="Run exact lookups against a local SQLite KB.")
iod_app = typer.Typer(help="Query PS3.3 IOD graph records.")
module_app = typer.Typer(help="Query PS3.3 module graph records.")
resolve_app = typer.Typer(help="Resolve DICOM facts in a usage context.")
mcp_app = typer.Typer(help="Run the MCP server adapter.")
app.add_typer(lookup_app, name="lookup")
app.add_typer(iod_app, name="iod")
app.add_typer(module_app, name="module")
app.add_typer(resolve_app, name="resolve")
app.add_typer(mcp_app, name="mcp")


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
def build_fixture(
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete synthetic fixture edition label."),
    ] = "2026b",
    cache_dir: Annotated[
        Path,
        typer.Option(
            "--cache-dir",
            help="Local dicom-kb cache directory.",
        ),
    ] = DEFAULT_CACHE_DIR,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Output SQLite path. Defaults under cache db/."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing fixture artifacts and DB."),
    ] = False,
) -> None:
    """Build a small synthetic SQLite KB for offline development."""
    artifacts = _synthetic_fixture_artifacts(edition)
    register_local_artifacts(
        edition=edition,
        artifacts=artifacts,
        cache_dir=cache_dir,
        force=force,
    )
    summary = build_sqlite_database(
        edition=edition,
        cache_dir=cache_dir,
        db_path=db,
        force=force,
    )
    typer.echo(json.dumps(summary.as_jsonable(), indent=2, sort_keys=True))


@app.command("fetch")
def fetch_command(
    edition: Annotated[
        str,
        typer.Option("--edition", help="DICOM edition label to register."),
    ],
    docbook_xml: Annotated[
        list[str] | None,
        typer.Option(
            "--docbook-xml",
            help="Register a local DocBook XML artifact as PART=PATH; repeatable.",
        ),
    ] = None,
    part: Annotated[
        list[str] | None,
        typer.Option(
            "--part",
            help=(
                "Official DICOM part to download when --docbook-xml is omitted; "
                "repeatable. Defaults to v1 parts PS3.3, PS3.4, and PS3.6."
            ),
        ),
    ] = None,
    artifact_format: Annotated[
        list[str] | None,
        typer.Option(
            "--format",
            help=(
                "Official artifact format to download; repeatable. Supported: "
                f"{', '.join(OFFICIAL_ARTIFACT_FORMATS)}. Defaults to docbook_xml."
            ),
        ),
    ] = None,
    current_edition: Annotated[
        str | None,
        typer.Option(
            "--current-edition",
            help="Concrete edition used when --edition current is requested.",
        ),
    ] = None,
    source_base_url: Annotated[
        str,
        typer.Option(
            "--source-base-url",
            help="Official DICOM current release base URL.",
        ),
    ] = DEFAULT_DICOM_CURRENT_BASE_URL,
    archive_base_url: Annotated[
        str,
        typer.Option(
            "--archive-base-url",
            help="Official DICOM archive root URL for concrete editions.",
        ),
    ] = DEFAULT_DICOM_ARCHIVE_BASE_URL,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = DEFAULT_CACHE_DIR,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing cached artifacts/manifest."),
    ] = False,
) -> None:
    """Fetch or register source artifacts into the dicom-kb cache."""
    if docbook_xml:
        resolved = EditionResolver(current_edition=current_edition).resolve(edition)
        artifacts = _docbook_xml_artifacts(docbook_xml, edition=resolved.edition)
        manifest = register_local_artifacts(
            edition=edition,
            current_edition=current_edition,
            artifacts=artifacts,
            cache_dir=cache_dir,
            force=force,
        )
    else:
        parts = (
            tuple(_normalize_part(value) for value in part)
            if part
            else V1_DOCBOOK_PARTS
        )
        try:
            formats = (
                tuple(artifact_format)
                if artifact_format
                else (DOCBOOK_XML_FORMAT,)
            )
            manifest = fetch_official_artifacts(
                edition=edition,
                parts=parts,
                formats=formats,
                cache_dir=cache_dir,
                base_url=source_base_url,
                archive_base_url=archive_base_url,
                force=force,
            )
        except OfficialFetchError as exc:
            raise typer.BadParameter(str(exc)) from exc
    typer.echo(_json_model(manifest))


@app.command("build")
def build_command(
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = DEFAULT_CACHE_DIR,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Output SQLite path. Defaults under cache db/."),
    ] = None,
    backend: Annotated[
        str,
        typer.Option("--backend", help="Database backend. Only sqlite is supported."),
    ] = "sqlite",
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite an existing SQLite database."),
    ] = False,
) -> None:
    """Build a SQLite KB from cached DocBook artifacts."""
    if backend != "sqlite":
        raise typer.BadParameter("only the sqlite backend is supported in v1")
    summary = build_sqlite_database(
        edition=edition,
        cache_dir=cache_dir,
        db_path=db,
        force=force,
    )
    typer.echo(json.dumps(summary.as_jsonable(), indent=2, sort_keys=True))


@mcp_app.command("serve")
def mcp_serve_command(
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = DEFAULT_CACHE_DIR,
) -> None:
    """Serve v1 query tools over MCP stdio."""
    config = MCPServerConfig(edition=edition, db_path=db, cache_dir=cache_dir)
    try:
        serve_mcp_stdio(config)
    except MissingMCPDependencyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command("retrieve-text")
def retrieve_text_command(
    part: Annotated[
        str,
        typer.Argument(help="DICOM part label, for example PS3.3."),
    ],
    section_or_anchor: Annotated[
        str,
        typer.Argument(help="DocBook xml:id, HTML anchor, or section number."),
    ],
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = DEFAULT_CACHE_DIR,
    max_chars: Annotated[
        int,
        typer.Option("--max-chars", help="Maximum excerpt characters to return."),
    ] = 800,
) -> None:
    """Retrieve a capped excerpt from persisted standard text."""
    with _connect_query_db(db, cache_dir=cache_dir, edition=edition) as connection:
        _echo_response(
            retrieve_standard_text(
                connection,
                part=part,
                section_or_anchor=section_or_anchor,
                edition=edition,
                max_chars=max_chars,
            )
        )


@app.command("search-text")
def search_text_command(
    query: Annotated[
        str,
        typer.Argument(help="Full-text query over persisted DocBook text."),
    ],
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = DEFAULT_CACHE_DIR,
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
    with _connect_query_db(db, cache_dir=cache_dir, edition=edition) as connection:
        _echo_response(
            search_standard_text(
                connection,
                query=query,
                edition=edition,
                part_filter=part_filter,
                limit=limit,
            )
        )


@lookup_app.command("tag")
def lookup_tag(
    tag_or_keyword: Annotated[
        str,
        typer.Argument(help="DICOM tag like (0008,0060), range tag, or keyword."),
    ],
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = DEFAULT_CACHE_DIR,
) -> None:
    """Look up a PS3.6 data element by tag or keyword."""
    with _connect_query_db(db, cache_dir=cache_dir, edition=edition) as connection:
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
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = DEFAULT_CACHE_DIR,
) -> None:
    """Look up a PS3.6 UID registry entry by UID value or keyword."""
    with _connect_query_db(db, cache_dir=cache_dir, edition=edition) as connection:
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
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = DEFAULT_CACHE_DIR,
) -> None:
    """Look up a PS3.3 IOD by name or keyword."""
    with _connect_query_db(db, cache_dir=cache_dir, edition=edition) as connection:
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
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = DEFAULT_CACHE_DIR,
) -> None:
    """Look up a PS3.4 SOP Class and linked IODs."""
    with _connect_query_db(db, cache_dir=cache_dir, edition=edition) as connection:
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
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = DEFAULT_CACHE_DIR,
) -> None:
    """List PS3.3 modules used by an IOD."""
    with _connect_query_db(db, cache_dir=cache_dir, edition=edition) as connection:
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
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = DEFAULT_CACHE_DIR,
    expand_macros: Annotated[
        bool,
        typer.Option(
            "--expand-macros/--no-expand-macros",
            help="Inline attributes from included macros after each include row.",
        ),
    ] = False,
) -> None:
    """List PS3.3 attributes used by a module."""
    with _connect_query_db(db, cache_dir=cache_dir, edition=edition) as connection:
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
    edition: Annotated[
        str,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ],
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = DEFAULT_CACHE_DIR,
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
    with _connect_query_db(db, cache_dir=cache_dir, edition=edition) as connection:
        _echo_response(
            resolve_attribute_context(
                connection,
                attribute=attribute,
                edition=edition,
                iod_name=iod_name,
                sop_class=sop_class,
            )
        )


def _connect_query_db(
    path: Path | None, *, cache_dir: Path, edition: str
) -> sqlite3.Connection:
    return _connect_existing_db(
        path if path is not None else default_db_path(cache_dir, edition)
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


def _json_model(model: BaseModel) -> str:
    return json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)


def _docbook_xml_artifacts(
    specs: list[str] | None, *, edition: str
) -> list[ArtifactRequest]:
    if not specs:
        raise typer.BadParameter(
            "local artifact registration requires at least one --docbook-xml PART=PATH"
        )
    return [_docbook_xml_artifact(spec, edition=edition) for spec in specs]


def _docbook_xml_artifact(spec: str, *, edition: str) -> ArtifactRequest:
    part, separator, path_text = spec.partition("=")
    if not separator or not part.strip() or not path_text.strip():
        raise typer.BadParameter("--docbook-xml must use PART=PATH")
    normalized_part = _normalize_part(part)
    source = Path(path_text).expanduser()
    if not source.exists():
        raise typer.BadParameter(f"DocBook XML file does not exist: {source}")
    return ArtifactRequest(
        part=normalized_part,
        format="docbook_xml",
        source=source,
        destination=official_artifact_destination(
            edition,
            part=normalized_part,
            artifact_format=DOCBOOK_XML_FORMAT,
        ),
    )


def _synthetic_fixture_artifacts(edition: str) -> list[ArtifactRequest]:
    fixture_dir = Path(__file__).resolve().parents[3] / "tests" / "fixtures_synthetic"
    fixtures = {
        "PS3.3": fixture_dir / "synthetic_ps3_3_ct_image_docbook.xml",
        "PS3.4": fixture_dir / "synthetic_ps3_4_sop_classes_docbook.xml",
        "PS3.6": fixture_dir / "synthetic_ps3_6_registry_docbook.xml",
    }
    missing = [str(path) for path in fixtures.values() if not path.exists()]
    if missing:
        raise typer.BadParameter(
            "synthetic fixture files are unavailable: " + ", ".join(missing)
        )
    return [
        ArtifactRequest(
            part=part,
            format="docbook_xml",
            source=path,
            destination=official_artifact_destination(
                edition,
                part=part,
                artifact_format=DOCBOOK_XML_FORMAT,
            ),
        )
        for part, path in fixtures.items()
    ]


def _normalize_part(part: str) -> str:
    normalized = part.strip().upper()
    if not normalized.startswith("PS3."):
        normalized = f"PS3.{normalized}"
    part_number = normalized.removeprefix("PS3.")
    if not part_number.isdigit():
        raise typer.BadParameter(f"DICOM part must look like PS3.6, got {part!r}")
    return f"PS3.{int(part_number)}"
