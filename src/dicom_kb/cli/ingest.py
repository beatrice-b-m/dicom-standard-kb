"""Source acquisition, verification, and database build commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from urllib.error import URLError

import typer

from dicom_kb.build import (
    BuildSummary,
    build_sqlite_database,
    gap_log_path,
    latest_edition,
)
from dicom_kb.cli.context import (
    resolve_cache_dir,
    resolve_db_path,
    resolve_edition,
)
from dicom_kb.cli.options import CacheDirectoryOption, EditionOption
from dicom_kb.sources.downloader import (
    DEFAULT_DICOM_CURRENT_BASE_URL,
    DEFAULT_DOCBOOK_PARTS,
    DOCBOOK_XML_FORMAT,
    ArtifactExistsError,
    ArtifactRequest,
    OfficialFetchError,
    fetch_current_docbook,
    official_artifact_destination,
    register_local_artifacts,
)
from dicom_kb.sources.manifest import ManifestExistsError

app = typer.Typer()


@app.command("build-fixture")
def build_fixture(
    ctx: typer.Context,
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete synthetic fixture edition label."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option(
            "--cache-dir",
            help="Local dicom-kb cache directory.",
        ),
    ] = None,
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
    resolved_edition = resolve_edition(ctx, edition, default="2026b")
    resolved_cache_dir = resolve_cache_dir(ctx, cache_dir)
    resolved_db = resolve_db_path(ctx, db)
    artifacts = _synthetic_fixture_artifacts(resolved_edition)
    register_local_artifacts(
        edition=resolved_edition,
        artifacts=artifacts,
        cache_dir=resolved_cache_dir,
        force=force,
    )
    summary = _run_sqlite_build(
        edition=resolved_edition,
        cache_dir=resolved_cache_dir,
        db_path=resolved_db,
        force=force,
    )
    _echo_summary(summary)


@app.command("fetch")
def fetch_command(
    ctx: typer.Context,
    part: Annotated[
        list[str] | None,
        typer.Option(
            "--part",
            help="DICOM part to download, e.g. PS3.3; repeatable. Defaults to every "
            "published part.",
        ),
    ] = None,
    docbook_xml: Annotated[
        list[str] | None,
        typer.Option(
            "--docbook-xml",
            help="Register a local DocBook XML file as PART=PATH instead of "
            "downloading; repeatable. Requires --edition.",
        ),
    ] = None,
    edition: Annotated[
        str | None,
        typer.Option(
            "--edition",
            help="Edition label for --docbook-xml files, e.g. 2026d.",
        ),
    ] = None,
    source_base_url: Annotated[
        str,
        typer.Option(
            "--source-base-url",
            help="Base URL of the current DICOM release.",
        ),
    ] = DEFAULT_DICOM_CURRENT_BASE_URL,
    cache_dir: CacheDirectoryOption = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite files already in the cache."),
    ] = False,
) -> None:
    """Download the current DICOM edition's DocBook from NEMA into the cache."""
    resolved_cache_dir = resolve_cache_dir(ctx, cache_dir)
    try:
        if docbook_xml:
            if edition is None:
                raise typer.BadParameter("--docbook-xml requires --edition")
            manifest = register_local_artifacts(
                edition=edition,
                artifacts=_docbook_xml_artifacts(docbook_xml, edition=edition),
                cache_dir=resolved_cache_dir,
                force=force,
            )
        else:
            parts = (
                tuple(_normalize_part(value) for value in part)
                if part
                else DEFAULT_DOCBOOK_PARTS
            )
            manifest = fetch_current_docbook(
                parts=parts,
                cache_dir=resolved_cache_dir,
                base_url=source_base_url,
                force=force,
            )
    except (ArtifactExistsError, ManifestExistsError) as exc:
        raise typer.BadParameter(
            f"{exc}. That edition is already fetched; pass --force to replace it."
        ) from exc
    except (OfficialFetchError, URLError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    total = sum(artifact.byte_size for artifact in manifest.artifacts)
    typer.echo(
        f"Fetched DICOM {manifest.edition}: {len(manifest.artifacts)} parts, "
        f"{total / 1_000_000:.1f} MB in {resolved_cache_dir}"
    )
    typer.echo(f"Next: dicom-kb build --edition {manifest.edition}")


@app.command("build")
def build_command(
    ctx: typer.Context,
    edition: EditionOption = None,
    cache_dir: CacheDirectoryOption = None,
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
    resolved_cache_dir = resolve_cache_dir(ctx, cache_dir)
    resolved_edition = resolve_edition(
        ctx, edition, fallback=latest_edition(resolved_cache_dir, built=False)
    )
    resolved_db = resolve_db_path(ctx, db)
    summary = _run_sqlite_build(
        edition=resolved_edition,
        cache_dir=resolved_cache_dir,
        db_path=resolved_db,
        force=force,
    )
    _echo_summary(summary)


def _echo_summary(summary: BuildSummary) -> None:
    metrics = summary.metrics
    typer.echo(f"Built DICOM {summary.edition} KB: {summary.db_path}")
    typer.echo(
        f"{metrics.data_elements} data elements, {metrics.uids} UIDs, "
        f"{metrics.iods} IODs, {metrics.modules} modules, {metrics.macros} macros, "
        f"{metrics.sop_classes} SOP Classes"
    )
    by_part = metrics.parse_warnings_by_part or {}
    counts = ", ".join(
        f"{part} {count}" for part, count in sorted(by_part.items()) if count
    )
    typer.echo(
        f"{metrics.parse_warnings} gaps logged"
        + (f" ({counts})" if counts else "")
        + f": {gap_log_path(summary.db_path)}"
    )


def _run_sqlite_build(
    *,
    edition: str,
    cache_dir: Path,
    db_path: Path | None,
    force: bool,
) -> BuildSummary:
    return build_sqlite_database(
        edition=edition,
        cache_dir=cache_dir,
        db_path=db_path,
        force=force,
    )


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
        "PS3.5": fixture_dir / "synthetic_ps3_5_encoding_docbook.xml",
        "PS3.6": fixture_dir / "synthetic_ps3_6_registry_docbook.xml",
        "PS3.7": fixture_dir / "synthetic_ps3_7_messages_docbook.xml",
        "PS3.8": fixture_dir / "synthetic_ps3_8_network_docbook.xml",
        "PS3.10": fixture_dir / "synthetic_ps3_10_media_storage_docbook.xml",
        "PS3.16": fixture_dir / "synthetic_ps3_16_content_mapping_docbook.xml",
        "PS3.18": fixture_dir / "synthetic_ps3_18_web_services_docbook.xml",
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
