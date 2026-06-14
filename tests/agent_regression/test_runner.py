from __future__ import annotations

import json
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from click.utils import strip_ansi
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


def test_reference_agent_scores_phase7_prose_retrieval_cases(tmp_path: Path) -> None:
    cache_dir = _build_fixture_cache(tmp_path)
    selected_cases = select_agent_regression_cases(
        (
            "agent.text.dimse_service_behavior",
            "agent.text.association_pdu_behavior",
        )
    )

    with _connect_fixture_db(cache_dir) as connection:
        runs = run_reference_agent_cases(
            connection,
            edition="2026b",
            cases=selected_cases,
        )

    report = score_agent_runs(runs)

    assert report.total_runs == 2
    assert report.failed_runs == 0
    assert [run.case_id for run in runs] == [case.id for case in selected_cases]


def test_reference_agent_scores_v2_public_tool_batch(tmp_path: Path) -> None:
    cache_dir = _build_fixture_cache(tmp_path)
    selected_cases = select_agent_regression_cases(
        (
            "agent.v2.vr.person_name",
            "agent.v2.transfer_syntax.explicit_little",
            "agent.v2.encoding_rule.sequence",
            "agent.v2.media_type.dicom_file",
            "agent.v2.dicomweb.retrieve_study",
            "agent.v2.sr_template.measurement_report",
            "agent.v2.context_group.acquisition_modality",
            "agent.v2.code_meaning.ct",
        )
    )

    with _connect_fixture_db(cache_dir) as connection:
        runs = run_reference_agent_cases(
            connection,
            edition="2026b",
            cases=selected_cases,
        )

    report = score_agent_runs(runs)

    assert report.total_runs == 8
    assert report.failed_runs == 0
    assert [run.case_id for run in runs] == [case.id for case in selected_cases]


def test_reference_agent_scores_v2_unsupported_claim_batch(tmp_path: Path) -> None:
    cache_dir = _build_fixture_cache(tmp_path)
    selected_cases = select_agent_regression_cases(
        (
            "agent.v2.unsupported.transfer_syntax.unknown_uid",
            "agent.v2.unsupported.transfer_syntax.malformed_uid",
            "agent.v2.unsupported.dicomweb.unknown_transaction",
            "agent.v2.unsupported.dicomweb.empty_route",
            "agent.v2.unsupported.media_type.unknown_context",
            "agent.v2.unsupported.media_type.empty_context",
            "agent.v2.unsupported.sr_template.unknown_tid",
            "agent.v2.unsupported.sr_template.empty_tid",
            "agent.v2.unsupported.context_group.unknown_cid",
            "agent.v2.unsupported.context_group.empty_cid",
            "agent.v2.unsupported.code_meaning.unknown_code",
            "agent.v2.unsupported.code_meaning.empty_scheme",
        )
    )

    with _connect_fixture_db(cache_dir) as connection:
        runs = run_reference_agent_cases(
            connection,
            edition="2026b",
            cases=selected_cases,
        )

    report = score_agent_runs(runs)

    assert report.total_runs == 12
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


def test_cli_eval_run_invokes_external_agent_command(tmp_path: Path) -> None:
    cache_dir = _build_fixture_cache(tmp_path)
    transcript = tmp_path / "external-runs.json"
    harness = tmp_path / "external_agent.py"
    harness.write_text(
        """\
import json
import sys

payload = json.load(sys.stdin)
case = payload["cases"][0]
json.dump(
    {
        "runs": [
            {
                "case_id": case["id"],
                "edition": payload["edition"],
                "answer": (
                    "For edition 2026b, external model used source references "
                    "for Explicit VR Big Endian and confirmed retired status."
                ),
                "tool_calls": [
                    {
                        "tool": "lookup_uid",
                        "arguments": {"uid_or_keyword": "ExplicitVRBigEndian"},
                        "response_status": "ok",
                        "response_edition": payload["edition"],
                        "response_ref_count": 1,
                    }
                ],
                "unsupported_normative_claims": [],
            }
        ]
    },
    sys.stdout,
)
""",
        encoding="utf-8",
    )
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
            "--agent",
            "external",
            "--external-command",
            f"{sys.executable} {harness}",
            "--external-provider",
            "test-provider",
            "--external-model",
            "test-model",
        ],
    )

    assert run_result.exit_code == 0, run_result.output
    assert json.loads(run_result.output) == {
        "agent": "external",
        "edition": "2026b",
        "external_model": "test-model",
        "external_provider": "test-provider",
        "output": str(transcript),
        "runs": 1,
    }

    score_result = runner.invoke(app, ["eval", "score", str(transcript)])
    assert score_result.exit_code == 0, score_result.output


def test_cli_eval_run_requires_external_command(tmp_path: Path) -> None:
    cache_dir = _build_fixture_cache(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "eval",
            "run",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cache_dir),
            "--out",
            str(tmp_path / "external-runs.json"),
            "--cases",
            "agent.ps36.transfer_syntax",
            "--agent",
            "external",
        ],
    )

    assert result.exit_code != 0
    output = " ".join(strip_ansi(result.output).split())
    assert "external agent runs require --external-command" in output


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
