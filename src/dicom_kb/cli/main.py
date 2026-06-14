"""Typer command-line entrypoint."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel

from dicom_kb.build import (
    BuildQualityGateError,
    BuildSummary,
    QualityGateSettings,
    build_sqlite_database,
    default_db_path,
)
from dicom_kb.config import (
    ConfigError,
    DicomKBConfig,
    int_env,
    load_config_profile,
    path_env,
    sqlite_url_path,
    str_env,
    value_with_precedence,
)
from dicom_kb.eval.reporting import report_as_jsonable, score_agent_run_file
from dicom_kb.eval.runner import (
    ExternalAgentError,
    external_agent_config,
    run_external_agent_cases,
    run_reference_agent_cases,
    select_agent_regression_cases,
    write_agent_runs,
)
from dicom_kb.mcp.server import (
    MCPServerConfig,
    MissingMCPDependencyError,
    serve_mcp_stdio,
)
from dicom_kb.metadata import LEGAL_NOTICE, __version__
from dicom_kb.query.answer_contracts import ToolResponse
from dicom_kb.query.resolver import (
    explain_encoding_rule,
    list_attributes_for_module,
    list_modules_for_iod,
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
    resolve_attribute_context,
    retrieve_standard_text,
    search_standard_text,
)
from dicom_kb.sources.downloader import (
    DEFAULT_CACHE_DIR,
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

app = typer.Typer(help="Build and query a local DICOM standard knowledge base.")
lookup_app = typer.Typer(help="Run exact lookups against a local SQLite KB.")
iod_app = typer.Typer(help="Query PS3.3 IOD graph records.")
module_app = typer.Typer(help="Query PS3.3 module graph records.")
resolve_app = typer.Typer(help="Resolve DICOM facts in a usage context.")
context_app = typer.Typer(help="Resolve documented DICOM context examples.")
explain_app = typer.Typer(help="Explain cited DICOM rules from a local KB.")
mcp_app = typer.Typer(help="Run the MCP server adapter.")
eval_app = typer.Typer(help="Run agent regression scoring utilities.")
app.add_typer(lookup_app, name="lookup")
app.add_typer(iod_app, name="iod")
app.add_typer(module_app, name="module")
app.add_typer(resolve_app, name="resolve")
app.add_typer(context_app, name="context")
app.add_typer(explain_app, name="explain")
app.add_typer(mcp_app, name="mcp")
app.add_typer(eval_app, name="eval")
_ACTIVE_CONFIG = DicomKBConfig()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", help="Show version and exit."),
    ] = False,
    config: Annotated[
        Path | None,
        typer.Option(
            "--config",
            help="YAML config profile with a top-level dicom_kb mapping.",
        ),
    ] = None,
) -> None:
    """Show startup metadata for every CLI invocation."""
    if version:
        typer.echo(f"dicom-standard-kb {__version__}")
        raise typer.Exit()
    global _ACTIVE_CONFIG
    _ACTIVE_CONFIG = DicomKBConfig()
    if config is not None:
        try:
            _ACTIVE_CONFIG = load_config_profile(config)
        except ConfigError as exc:
            raise typer.BadParameter(str(exc)) from exc


@app.command()
def doctor() -> None:
    """Print local diagnostic metadata."""
    typer.echo(f"dicom-standard-kb {__version__}")
    typer.echo(LEGAL_NOTICE)


@app.command("build-fixture")
def build_fixture(
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
    resolved_edition = _resolve_edition(edition, default="2026b")
    resolved_cache_dir = _resolve_cache_dir(cache_dir)
    resolved_db = _resolve_db_path(db)
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
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite existing cached artifacts/manifest."),
    ] = False,
) -> None:
    """Fetch or register source artifacts into the dicom-kb cache."""
    resolved_edition_input = _resolve_edition(edition)
    resolved_cache_dir = _resolve_cache_dir(cache_dir)
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
    typer.echo(_json_model(manifest))


@app.command("build")
def build_command(
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
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
    resolved_edition = _resolve_edition(edition)
    resolved_cache_dir = _resolve_cache_dir(cache_dir)
    resolved_db = _resolve_db_path(db)
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
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="SQLite path. Defaults under cache db/."),
    ] = None,
) -> None:
    """Verify cached source artifacts and an optional SQLite KB."""
    resolved_edition = _resolve_edition(edition)
    resolved_cache_dir = _resolve_cache_dir(cache_dir)
    resolved_db = _resolve_db_path(db)
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


def _resolve_edition(cli_value: str | None, *, default: str | None = None) -> str:
    resolved = value_with_precedence(
        cli_value=cli_value,
        env_value=str_env(os.environ, "DICOM_KB_EDITION"),
        config_value=_ACTIVE_CONFIG.edition,
        default=default,
    )
    if resolved is None:
        raise typer.BadParameter(
            "--edition is required when not supplied by environment or config"
        )
    return resolved


def _resolve_cache_dir(cli_value: Path | None) -> Path:
    return value_with_precedence(
        cli_value=cli_value,
        env_value=path_env(os.environ, "DICOM_KB_CACHE_DIR"),
        config_value=_ACTIVE_CONFIG.artifact_dir,
        default=DEFAULT_CACHE_DIR,
    )


def _resolve_db_path(cli_value: Path | None) -> Path | None:
    if cli_value is not None:
        return cli_value
    env_database_url = str_env(os.environ, "DICOM_KB_DATABASE_URL")
    if env_database_url is not None:
        return sqlite_url_path(env_database_url)
    if _ACTIVE_CONFIG.database_url is not None:
        return sqlite_url_path(_ACTIVE_CONFIG.database_url)
    return None


def _resolve_max_text_chars(cli_value: int | None, *, default: int) -> int:
    return value_with_precedence(
        cli_value=cli_value,
        env_value=int_env(os.environ, "DICOM_KB_MAX_TEXT_EXCERPT_CHARS"),
        config_value=_ACTIVE_CONFIG.max_text_excerpt_chars,
        default=default,
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


@mcp_app.command("serve")
def mcp_serve_command(
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
) -> None:
    """Serve v1 query tools over MCP stdio."""
    config = MCPServerConfig(
        edition=_resolve_edition(edition),
        db_path=_resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
    )
    try:
        serve_mcp_stdio(config)
    except MissingMCPDependencyError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc


@eval_app.command("score")
def eval_score_command(
    transcript: Annotated[
        Path,
        typer.Argument(
            help=(
                "JSON AgentRun transcript, list of transcripts, or object with "
                "a top-level runs list."
            ),
        ),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write the JSON scorecard report to a file."),
    ] = None,
    fail_on_issues: Annotated[
        bool,
        typer.Option(
            "--fail-on-issues/--no-fail-on-issues",
            help="Exit nonzero when any transcript fails scoring.",
        ),
    ] = True,
) -> None:
    """Score recorded agent runs against committed regression cases."""
    if not transcript.exists():
        raise typer.BadParameter(f"agent transcript does not exist: {transcript}")
    report = score_agent_run_file(transcript)
    payload = json.dumps(report_as_jsonable(report), indent=2, sort_keys=True)
    if output is None:
        typer.echo(payload)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    if fail_on_issues and report.failed_runs:
        raise typer.Exit(code=1)


@eval_app.command("run")
def eval_run_command(
    out: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Write compact agent transcripts to this JSON file.",
        ),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
    cases: Annotated[
        list[str] | None,
        typer.Option(
            "--case",
            "--cases",
            help=(
                "Agent regression case id to run; repeatable. "
                "Defaults to every committed case."
            ),
        ),
    ] = None,
    agent: Annotated[
        str,
        typer.Option(
            "--agent",
            help="Agent runner to use: reference or external.",
        ),
    ] = "reference",
    external_command: Annotated[
        str | None,
        typer.Option(
            "--external-command",
            help=(
                "Command for --agent external. Receives JSON on stdin and must "
                "emit AgentRun JSON on stdout."
            ),
        ),
    ] = None,
    external_provider: Annotated[
        str | None,
        typer.Option(
            "--external-provider",
            help="Optional provider label passed to the external agent payload.",
        ),
    ] = None,
    external_model: Annotated[
        str | None,
        typer.Option(
            "--external-model",
            help="Optional model label passed to the external agent payload.",
        ),
    ] = None,
    external_timeout: Annotated[
        float,
        typer.Option(
            "--external-timeout",
            help="Maximum seconds to wait for the external agent command.",
        ),
    ] = 300.0,
) -> None:
    """Run reference or opt-in external agent transcripts for prompt cases."""
    selected_cases = select_agent_regression_cases(tuple(cases or ()))
    resolved_edition = _resolve_edition(edition)
    resolved_cache_dir = _resolve_cache_dir(cache_dir)
    resolved_db = _resolve_db_path(db)
    if agent == "reference":
        with _connect_query_db(
            resolved_db,
            cache_dir=resolved_cache_dir,
            edition=resolved_edition,
        ) as connection:
            runs = run_reference_agent_cases(
                connection,
                edition=resolved_edition,
                cases=selected_cases,
            )
    elif agent == "external":
        db_path = (
            resolved_db
            if resolved_db is not None
            else default_db_path(resolved_cache_dir, resolved_edition)
        )
        if not db_path.exists():
            raise typer.BadParameter(f"SQLite KB does not exist: {db_path}")
        try:
            config = external_agent_config(
                command=external_command,
                provider=external_provider,
                model=external_model,
                timeout_seconds=external_timeout,
            )
            runs = run_external_agent_cases(
                config=config,
                edition=resolved_edition,
                cases=selected_cases,
                db_path=db_path,
                cache_dir=resolved_cache_dir,
            )
        except ExternalAgentError as exc:
            raise typer.BadParameter(str(exc)) from exc
    else:
        raise typer.BadParameter("agent must be 'reference' or 'external'")
    write_agent_runs(out, runs)
    payload = {
        "agent": agent,
        "edition": resolved_edition,
        "runs": len(runs),
        "output": str(out),
    }
    if agent == "external":
        payload.update(
            {
                "external_provider": external_provider,
                "external_model": external_model,
            }
        )
    typer.echo(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
    )


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
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
    max_chars: Annotated[
        int | None,
        typer.Option("--max-chars", help="Maximum excerpt characters to return."),
    ] = None,
) -> None:
    """Retrieve a capped excerpt from persisted standard text."""
    resolved_edition = _resolve_edition(edition)
    resolved_max_chars = _resolve_max_text_chars(max_chars, default=800)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
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
    query: Annotated[
        str,
        typer.Argument(help="Full-text query over persisted DocBook text."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
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
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
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
    topic: Annotated[
        str,
        typer.Argument(help="PS3.5 encoding topic, VR, or transfer syntax name."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
) -> None:
    """Explain a PS3.5 encoding rule with citations."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            explain_encoding_rule(
                connection,
                topic=topic,
                edition=resolved_edition,
            )
        )


@lookup_app.command("tag")
def lookup_tag(
    tag_or_keyword: Annotated[
        str,
        typer.Argument(help="DICOM tag like (0008,0060), range tag, or keyword."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
) -> None:
    """Look up a PS3.6 data element by tag or keyword."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            lookup_data_element(
                connection,
                tag_or_keyword=tag_or_keyword,
                edition=resolved_edition,
            )
        )


@lookup_app.command("uid")
def lookup_uid_command(
    uid_or_keyword: Annotated[
        str,
        typer.Argument(help="DICOM UID value or UID keyword."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
) -> None:
    """Look up a PS3.6 UID registry entry by UID value or keyword."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            lookup_uid(
                connection,
                uid_or_keyword=uid_or_keyword,
                edition=resolved_edition,
            )
        )


@lookup_app.command("vr")
def lookup_vr_command(
    vr: Annotated[
        str,
        typer.Argument(help="Two-letter DICOM Value Representation code."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
) -> None:
    """Look up a PS3.5 Value Representation definition."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            lookup_vr(
                connection,
                vr=vr,
                edition=resolved_edition,
            )
        )


@lookup_app.command("transfer-syntax")
def lookup_transfer_syntax_command(
    uid_or_keyword: Annotated[
        str,
        typer.Argument(help="DICOM Transfer Syntax UID value, name, or keyword."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
) -> None:
    """Look up transfer syntax UID metadata and encoding details."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            lookup_transfer_syntax(
                connection,
                uid_or_keyword=uid_or_keyword,
                edition=resolved_edition,
            )
        )


@lookup_app.command("media-type")
def lookup_media_type_command(
    media_type_or_context: Annotated[
        str,
        typer.Argument(help="DICOM media type or service context."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
) -> None:
    """Look up DICOM media type constraints by media type or context."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            lookup_media_type(
                connection,
                media_type_or_context=media_type_or_context,
                edition=resolved_edition,
            )
        )


@lookup_app.command("dicomweb")
def lookup_dicomweb_command(
    name_or_route: Annotated[
        str,
        typer.Argument(help="DICOMweb transaction name or route template."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
) -> None:
    """Look up a PS3.18 DICOMweb transaction by name or route."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            lookup_dicomweb_transaction(
                connection,
                name_or_route=name_or_route,
                edition=resolved_edition,
            )
        )


@lookup_app.command("sr-template")
def lookup_sr_template_command(
    tid_or_name: Annotated[
        str,
        typer.Argument(help="PS3.16 SR template TID or exact template name."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
) -> None:
    """Look up a PS3.16 SR template by TID or exact name."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            lookup_sr_template(
                connection,
                tid_or_name=tid_or_name,
                edition=resolved_edition,
            )
        )


@lookup_app.command("context-group")
def lookup_context_group_command(
    cid_or_name: Annotated[
        str,
        typer.Argument(help="PS3.16 context group CID or exact context group name."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
) -> None:
    """Look up a PS3.16 context group by CID or exact name."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            lookup_context_group(
                connection,
                cid_or_name=cid_or_name,
                edition=resolved_edition,
            )
        )


@lookup_app.command("iod")
def lookup_iod_command(
    iod_name: Annotated[
        str,
        typer.Argument(help="DICOM IOD name or keyword, for example 'CT Image'."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
) -> None:
    """Look up a PS3.3 IOD by name or keyword."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            lookup_iod(
                connection,
                iod_name=iod_name,
                edition=resolved_edition,
            )
        )


@lookup_app.command("sop-class")
def lookup_sop_class_command(
    uid_or_name_or_keyword: Annotated[
        str,
        typer.Argument(help="DICOM SOP Class UID, name, or UID keyword."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
) -> None:
    """Look up a PS3.4 SOP Class and linked IODs."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            lookup_sop_class(
                connection,
                uid_or_name_or_keyword=uid_or_name_or_keyword,
                edition=resolved_edition,
            )
        )


@lookup_app.command("enumerated-values")
def lookup_enumerated_values_command(
    attribute: Annotated[
        str,
        typer.Argument(help="DICOM attribute tag, keyword, or name."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
    context: Annotated[
        str | None,
        typer.Option("--context", help="Optional module, macro, or context label."),
    ] = None,
) -> None:
    """Look up parsed enumerated values for a DICOM attribute."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            lookup_enumerated_values(
                connection,
                attribute=attribute,
                edition=resolved_edition,
                context=context,
            )
        )


@lookup_app.command("defined-terms")
def lookup_defined_terms_command(
    attribute: Annotated[
        str,
        typer.Argument(help="DICOM attribute tag, keyword, or name."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
    context: Annotated[
        str | None,
        typer.Option("--context", help="Optional module, macro, or context label."),
    ] = None,
) -> None:
    """Look up parsed defined terms for a DICOM attribute."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            lookup_defined_terms(
                connection,
                attribute=attribute,
                edition=resolved_edition,
                context=context,
            )
        )


@iod_app.command("modules")
def iod_modules(
    iod_name: Annotated[
        str,
        typer.Argument(help="DICOM IOD name or keyword, for example 'CT Image'."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
) -> None:
    """List PS3.3 modules used by an IOD."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            list_modules_for_iod(
                connection,
                iod_name=iod_name,
                edition=resolved_edition,
            )
        )


@module_app.command("attributes")
def module_attributes(
    module_name: Annotated[
        str,
        typer.Argument(help="DICOM module name, for example 'Patient'."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
    expand_macros: Annotated[
        bool,
        typer.Option(
            "--expand-macros/--no-expand-macros",
            help="Inline attributes from included macros after each include row.",
        ),
    ] = False,
) -> None:
    """List PS3.3 attributes used by a module."""
    resolved_edition = _resolve_edition(edition)
    with _connect_query_db(
        _resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        edition=resolved_edition,
    ) as connection:
        _echo_response(
            list_attributes_for_module(
                connection,
                module_name=module_name,
                edition=resolved_edition,
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
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
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
    resolved_edition = _resolve_edition(edition)
    _echo_attribute_context_response(
        attribute=attribute,
        edition=resolved_edition,
        db=_resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
        iod_name=iod_name,
        sop_class=sop_class,
    )


@context_app.command("attribute")
def context_attribute_command(
    attribute: Annotated[
        str,
        typer.Argument(help="DICOM attribute tag, keyword, or name."),
    ],
    edition: Annotated[
        str | None,
        typer.Option("--edition", help="Concrete DICOM edition label."),
    ] = None,
    db: Annotated[
        Path | None,
        typer.Option("--db", help="Path to a locally built dicom-kb SQLite file."),
    ] = None,
    cache_dir: Annotated[
        Path | None,
        typer.Option("--cache-dir", help="Local dicom-kb cache directory."),
    ] = None,
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
    resolved_edition = _resolve_edition(edition)
    _echo_attribute_context_response(
        attribute=attribute,
        edition=resolved_edition,
        db=_resolve_db_path(db),
        cache_dir=_resolve_cache_dir(cache_dir),
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
