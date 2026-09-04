"""Explicit release checks must fail instead of silently skipping missing inputs."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("edition", [None, "2026b"])
def test_strict_release_rejects_missing_local_database(
    tmp_path: Path, edition: str | None
) -> None:
    environ = {
        **os.environ,
        "DICOM_KB_RUN_RELEASE": "1",
        "DICOM_KB_CACHE_DIR": str(tmp_path / "empty-cache"),
    }
    environ.pop("DICOM_KB_TEST_EDITION", None)
    if edition is not None:
        environ["DICOM_KB_TEST_EDITION"] = edition
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/integration_requires_dicom_download/test_release_gate.py",
        ],
        cwd=ROOT,
        env=environ,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "strict release prerequisite missing" in result.stdout
    assert "skipped" not in result.stdout
