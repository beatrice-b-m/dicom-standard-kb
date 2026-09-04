from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from dicom_kb.cli.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_python_lookup_example_runs_against_fixture_db(tmp_path: Path) -> None:
    db_path = _build_fixture_db(tmp_path)

    result = _run_python_example(
        "examples/python/lookup_modality.py",
        "--db",
        str(db_path),
        "--edition",
        "2026b",
    )

    payload = json.loads(result.stdout)
    assert payload["tool"] == "lookup_data_element"
    assert payload["status"] == "ok"
    assert payload["result"]["keyword"] == "Modality"


def test_coding_agent_harness_example_writes_scoreable_run(tmp_path: Path) -> None:
    db_path = _build_fixture_db(tmp_path)
    transcript = tmp_path / "reference-run.json"

    result = _run_python_example(
        "examples/coding_agent_harness/run_reference_case.py",
        "--db",
        str(db_path),
        "--edition",
        "2026b",
        "--case",
        "agent.ct.required_modules",
        "--out",
        str(transcript),
    )

    assert json.loads(result.stdout) == {"output": str(transcript), "runs": 1}
    score_result = CliRunner().invoke(app, ["eval", "score", str(transcript)])
    assert score_result.exit_code == 0, score_result.output


def test_validator_example_normalizes_tag() -> None:
    result = _run_python_example(
        "examples/validators/validate_identifier.py",
        "--tag",
        "(0008,0060)",
    )

    assert json.loads(result.stdout) == {
        "kind": "tag",
        "normalized": "(0008,0060)",
    }


def _build_fixture_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "fixture.sqlite"
    result = CliRunner().invoke(
        app,
        [
            "build-fixture",
            "--edition",
            "2026b",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--db",
            str(db_path),
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output
    return db_path


def _run_python_example(
    relative_script: str, *args: str
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / relative_script), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result
