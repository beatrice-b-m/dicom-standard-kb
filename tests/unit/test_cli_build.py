from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from dicom_kb.cli.main import app


def test_cli_build_fixture_fails_configured_quality_gate(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "build-fixture",
            "--edition",
            "2026b",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--db",
            str(tmp_path / "fixture.sqlite"),
            "--max-parse-warnings",
            "0",
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    parse_warnings = payload["metrics"]["parse_warnings"]
    assert parse_warnings > 0
    assert payload["gate_failures"] == [
        f"parse warning count {parse_warnings} exceeds configured maximum 0"
    ]


def test_cli_build_fixture_allows_quality_gate_failures(
    tmp_path: Path,
) -> None:
    result = CliRunner().invoke(
        app,
        [
            "build-fixture",
            "--edition",
            "2026b",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--db",
            str(tmp_path / "fixture.sqlite"),
            "--max-parse-warnings",
            "0",
            "--allow-gate-failures",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    parse_warnings = payload["metrics"]["parse_warnings"]
    assert payload["gate_failures"] == [
        f"parse warning count {parse_warnings} exceeds configured maximum 0"
    ]
    assert payload["warnings"][-1] == payload["gate_failures"][0]
