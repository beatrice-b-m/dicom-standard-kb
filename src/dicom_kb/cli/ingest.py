"""Source acquisition, verification, and database build commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from dicom_kb.build import (
    BuildQualityGateError,
    BuildSummary,
    QualityGateSettings,
    build_sqlite_database,
    default_db_path,
)
from dicom_kb.cli.context import (
    json_model,
    resolve_cache_dir,
    resolve_db_path,
    resolve_edition,
)
from dicom_kb.cli.options import CacheDirectoryOption, EditionOption
from dicom_kb.sources.downloader import (
    DEFAULT_DICOM_ARCHIVE_BASE_URL,
    DEFAULT_DICOM_CURRENT_BASE_URL,
    DEFAULT_DOCBOOK_PARTS,
    DOCBOOK_XML_FORMAT,
    OFFICIAL_ARTIFACT_FORMATS,
    ArtifactRequest,
    OfficialFetchError,
    fetch_official_artifacts,
    official_artifact_destination,
    register_local_artifacts,
)
from dicom_kb.sources.edition_resolver import EditionResolver
from dicom_kb.sources.verify import verify_edition_cache

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
    max_unresolved_xref_rate: Annotated[
        float | None,
        typer.Option(
            "--max-unresolved-xref-rate",
            help="Fail when unresolved xref rate exceeds this value.",
        ),
    ] = None,
    max_unresolved_include_rate: Annotated[
        float | None,
        typer.Option(
            "--max-unresolved-include-rate",
            help="Fail when unresolved include-row rate exceeds this value.",
        ),
    ] = None,
    max_parse_warnings: Annotated[
        int | None,
        typer.Option(
            "--max-parse-warnings",
            help="Fail when parser warning count exceeds this value.",
        ),
    ] = None,
    allow_gate_failures: Annotated[
        bool,
        typer.Option(
            "--allow-gate-failures",
            help="Emit gate failures as warnings and exit zero.",
        ),
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
        quality_gates=_quality_gate_settings(
            max_unresolved_xref_rate=max_unresolved_xref_rate,
            max_unresolved_include_rate=max_unresolved_include_rate,
            max_parse_warnings=max_parse_warnings,
            allow_gate_failures=allow_gate_failures,
        ),
    )
    typer.echo(json.dumps(summary.as_jsonable(), indent=2, sort_keys=True))


@app.command("fetch")
def fetch_command(
    ctx: typer.Context,
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="DICOM edition label to register."),
    ] = None,
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
                "repeatable. Defaults to the v2 baseline DocBook parts."
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
    mirror_chtml_tree: Annotated[
        bool,
        typer.Option(
            "--mirror-chtml-tree",
            help=(
                "When --format chtml is requested, recursively mirror the full "
                "per-part CHTML directory instead of only the part entry page."
            ),
        ),
    ] = False,
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
    cache_dir: CacheDirectoryOption = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing cached artifacts/manifest."),
    ] = False,
) -> None:
    """Fetch or register source artifacts into the dicom-kb cache."""
    resolved_edition_input = resolve_edition(ctx, edition)
    resolved_cache_dir = resolve_cache_dir(ctx, cache_dir)
    if docbook_xml:
        if mirror_chtml_tree:
            raise typer.BadParameter(
                "--mirror-chtml-tree is only valid for official --format chtml fetches"
            )
        resolved = EditionResolver(current_edition=current_edition).resolve(
            resolved_edition_input
        )
        artifacts = _docbook_xml_artifacts(docbook_xml, edition=resolved.edition)
        manifest = register_local_artifacts(
            edition=resolved_edition_input,
            current_edition=current_edition,
            artifacts=artifacts,
            cache_dir=resolved_cache_dir,
            force=force,
        )
    else:
        parts = (
            tuple(_normalize_part(value) for value in part)
            if part
            else DEFAULT_DOCBOOK_PARTS
        )
        try:
            formats = (
                tuple(artifact_format) if artifact_format else (DOCBOOK_XML_FORMAT,)
            )
            if mirror_chtml_tree and not any(
                value.strip().lower().replace("-", "_") == "chtml" for value in formats
            ):
                raise typer.BadParameter("--mirror-chtml-tree requires --format chtml")
            manifest = fetch_official_artifacts(
                edition=resolved_edition_input,
                parts=parts,
                formats=formats,
                cache_dir=resolved_cache_dir,
                base_url=source_base_url,
                archive_base_url=archive_base_url,
                mirror_chtml_tree=mirror_chtml_tree,
                force=force,
            )
        except OfficialFetchError as exc:
            raise typer.BadParameter(str(exc)) from exc
    typer.echo(json_model(manifest))


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
    max_unresolved_xref_rate: Annotated[
        float | None,
        typer.Option(
            "--max-unresolved-xref-rate",
            help="Fail when unresolved xref rate exceeds this value.",
        ),
    ] = None,
    max_unresolved_include_rate: Annotated[
        float | None,
        typer.Option(
            "--max-unresolved-include-rate",
            help="Fail when unresolved include-row rate exceeds this value.",
        ),
    ] = None,
    max_parse_warnings: Annotated[
        int | None,
        typer.Option(
            "--max-parse-warnings",
            help="Fail when parser warning count exceeds this value.",
        ),
    ] = None,
    allow_gate_failures: Annotated[
        bool,
        typer.Option(
            "--allow-gate-failures",
            help="Emit gate failures as warnings and exit zero.",
        ),
    ] = False,
) -> None:
    """Build a SQLite KB from cached DocBook artifacts."""
    if backend != "sqlite":
        raise typer.BadParameter("only the sqlite backend is supported in v1")
    resolved_edition = resolve_edition(ctx, edition)
    resolved_cache_dir = resolve_cache_dir(ctx, cache_dir)
    resolved_db = resolve_db_path(ctx, db)
    summary = _run_sqlite_build(
        edition=resolved_edition,
        cache_dir=resolved_cache_dir,
        db_path=resolved_db,
        force=force,
        quality_gates=_quality_gate_settings(
            max_unresolved_xref_rate=max_unresolved_xref_rate,
            max_unresolved_include_rate=max_unresolved_include_rate,
            max_parse_warnings=max_parse_warnings,
            allow_gate_failures=allow_gate_failures,
        ),
    )
    typer.echo(json.dumps(summary.as_jsonable(), indent=2, sort_keys=True))


@app.command("verify")
def verify_command(
    ctx: typer.Context,
    edition: EditionOption = None,
    cache_dir: CacheDirectoryOption = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="SQLite path. Defaults under cache db/."),
    ] = None,
) -> None:
    """Verify cached source artifacts and an optional SQLite KB."""
    resolved_edition = resolve_edition(ctx, edition)
    resolved_cache_dir = resolve_cache_dir(ctx, cache_dir)
    resolved_db = resolve_db_path(ctx, db)
    db_path = (
        resolved_db
        if resolved_db is not None
        else default_db_path(resolved_cache_dir, resolved_edition)
    )
    result = verify_edition_cache(
        edition=resolved_edition,
        cache_dir=resolved_cache_dir,
        db_path=db_path,
    )
    typer.echo(json.dumps(result.as_jsonable(), indent=2, sort_keys=True))
    if not result.ok:
        raise typer.Exit(code=1)


def _quality_gate_settings(
    *,
    max_unresolved_xref_rate: float | None,
    max_unresolved_include_rate: float | None,
    max_parse_warnings: int | None,
    allow_gate_failures: bool,
) -> QualityGateSettings:
    _validate_rate_option(
        max_unresolved_xref_rate,
        option_name="--max-unresolved-xref-rate",
    )
    _validate_rate_option(
        max_unresolved_include_rate,
        option_name="--max-unresolved-include-rate",
    )
    if max_parse_warnings is not None and max_parse_warnings < 0:
        raise typer.BadParameter("--max-parse-warnings must be zero or greater")
    return QualityGateSettings(
        max_unresolved_xref_rate=max_unresolved_xref_rate,
        max_unresolved_include_rate=max_unresolved_include_rate,
        max_parse_warnings=max_parse_warnings,
        allow_gate_failures=allow_gate_failures,
    )


def _validate_rate_option(value: float | None, *, option_name: str) -> None:
    if value is not None and not 0 <= value <= 1:
        raise typer.BadParameter(f"{option_name} must be between 0 and 1")


def _run_sqlite_build(
    *,
    edition: str,
    cache_dir: Path,
    db_path: Path | None,
    force: bool,
    quality_gates: QualityGateSettings,
) -> BuildSummary:
    try:
        return build_sqlite_database(
            edition=edition,
            cache_dir=cache_dir,
            db_path=db_path,
            force=force,
            quality_gates=quality_gates,
        )
    except BuildQualityGateError as exc:
        typer.echo(json.dumps(exc.summary.as_jsonable(), indent=2, sort_keys=True))
        raise typer.Exit(code=1) from exc


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
