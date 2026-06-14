from __future__ import annotations

import os
import sqlite3

import pytest

from dicom_kb.sources.manifest import SourceManifest

try:
    from tests.integration_requires_dicom_download.release_requirements import (
        require_official_kb_release_ready,
    )
except ModuleNotFoundError:  # pragma: no cover - single-file pytest invocation
    from release_requirements import require_official_kb_release_ready

pytestmark = [
    pytest.mark.dicom_release,
    pytest.mark.skipif(
        os.environ.get("DICOM_KB_RUN_RELEASE") != "1",
        reason="strict official release gate is opt-in via make test-dicom-release",
    ),
]


def test_official_kb_satisfies_strict_release_requirements(
    connection: sqlite3.Connection,
    edition: str,
    manifest: SourceManifest,
) -> None:
    require_official_kb_release_ready(
        connection,
        edition=edition,
        manifest=manifest,
    )
