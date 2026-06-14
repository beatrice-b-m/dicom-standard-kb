from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("make") is None, reason="make is unavailable")
def test_makefile_dicom_integration_aliases_are_wired() -> None:
    integration = _make_dry_run("test-dicom-integration")
    current = _make_dry_run("test-dicom-current")
    release = _make_dry_run("test-dicom-release")
    default = _make_dry_run("test")

    assert "pytest tests/integration_requires_dicom_download" in integration.stdout
    assert "-m dicom_current" in current.stdout
    assert "DICOM_KB_RUN_CURRENT=1" in current.stdout
    assert "-m dicom_release" in release.stdout
    assert "DICOM_KB_RUN_RELEASE=1" in release.stdout
    assert "test_release_gate.py" in release.stdout
    assert "test_release_goldens.py" in release.stdout
    assert "dicom_current" not in default.stdout
    assert "dicom_release" not in default.stdout


def _make_dry_run(target: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["make", "-n", target],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result
