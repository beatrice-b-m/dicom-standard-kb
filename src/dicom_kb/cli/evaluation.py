"""Agent regression execution and scoring commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from dicom_kb.build import (
    default_db_path,
)
from dicom_kb.cli.context import (
    connect_query_db,
    resolve_cache_dir,
    resolve_db_path,
    resolve_edition,
)
from dicom_kb.cli.options import CacheDirectoryOption, DatabaseOption, EditionOption
from dicom_kb.eval.reporting import report_as_jsonable, score_agent_run_file
from dicom_kb.eval.runner import (
    ExternalAgentError,
    external_agent_config,
    run_external_agent_cases,
    run_reference_agent_cases,
    select_agent_regression_cases,
    write_agent_runs,
)

eval_app = typer.Typer(help="Run agent regression scoring utilities.")


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
    ctx: typer.Context,
    out: Annotated[
        Path,
        typer.Option(
            "--out",
            help="Write compact agent transcripts to this JSON file.",
        ),
    ],
    edition: EditionOption = None,
    db: DatabaseOption = None,
    cache_dir: CacheDirectoryOption = None,
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
    resolved_edition = resolve_edition(ctx, edition)
    resolved_cache_dir = resolve_cache_dir(ctx, cache_dir)
    resolved_db = resolve_db_path(ctx, db)
    if agent == "reference":
        with connect_query_db(
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
