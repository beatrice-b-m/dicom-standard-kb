from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from typer.testing import CliRunner

from dicom_kb.build import default_db_path
from dicom_kb.cli.main import app
from dicom_kb.eval.reporting import score_agent_runs
from dicom_kb.eval.runner import (
    run_reference_agent_cases,
    select_agent_regression_cases,
)


def test_reference_agent_scores_synthetic_subset(tmp_path: Path) -> None:
    cache_dir = _build_fixture_cache(tmp_path)
    selected_cases = select_agent_regression_cases(
        (
            "agent.ct.required_modules",
            "agent.ct.modality_context",
            "agent.ps36.transfer_syntax",
        )
    )

    with _connect_fixture_db(cache_dir) as connection:
        runs = run_reference_agent_cases(
            connection,
            edition="2026b",
            cases=selected_cases,
        )

    report = score_agent_runs(runs)

    assert report.total_runs == 3
    assert report.failed_runs == 0
    assert [run.case_id for run in runs] == [case.id for case in selected_cases]


def test_cli_eval_run_writes_scoreable_reference_transcripts(tmp_path: Path) -> None:
    cache_dir = _build_fixture_cache(tmp_path)
    transcript = tmp_path / "reference-runs.json"
    runner = CliRunner()

    run_result = runner.invoke(
        app,
        [
            "eval",
            "run",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cache_dir),
            "--out",
            str(transcript),
            "--cases",
            "agent.ps36.transfer_syntax",
        ],
    )

    assert run_result.exit_code == 0, run_result.output
    assert json.loads(run_result.output) == {
        "agent": "reference",
        "edition": "2026b",
        "output": str(transcript),
        "runs": 1,
    }

    score_result = runner.invoke(app, ["eval", "score", str(transcript)])

    assert score_result.exit_code == 0, score_result.output
    score_payload = json.loads(score_result.output)
    assert score_payload["total_runs"] == 1
    assert score_payload["passed_runs"] == 1


def _build_fixture_cache(tmp_path: Path) -> Path:
    cache_dir = tmp_path / "cache"
    result = CliRunner().invoke(
        app,
        [
            "build-fixture",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cache_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    return cache_dir


@contextmanager
def _connect_fixture_db(cache_dir: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(
        f"file:{default_db_path(cache_dir, '2026b')}?mode=ro",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()
