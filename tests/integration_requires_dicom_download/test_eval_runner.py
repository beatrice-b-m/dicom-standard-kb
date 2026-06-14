from __future__ import annotations

import sqlite3

import pytest

from dicom_kb.eval.prompt_cases import AGENT_REGRESSION_CASES
from dicom_kb.eval.reporting import score_agent_runs
from dicom_kb.eval.runner import run_reference_agent_cases
from dicom_kb.sources.manifest import SourceManifest

try:
    from tests.integration_requires_dicom_download.release_requirements import (
        evaluate_official_kb_release_requirements,
    )
except ModuleNotFoundError:  # pragma: no cover - single-file pytest invocation
    from release_requirements import evaluate_official_kb_release_requirements


def test_reference_agent_scores_all_cases_against_real_kb(
    connection: sqlite3.Connection,
    edition: str,
    manifest: SourceManifest,
) -> None:
    requirements = evaluate_official_kb_release_requirements(
        connection,
        edition=edition,
        manifest=manifest,
    )
    if not requirements.ok:
        pytest.skip(requirements.failure_message())

    runs = run_reference_agent_cases(
        connection,
        edition=edition,
        cases=AGENT_REGRESSION_CASES,
    )

    report = score_agent_runs(runs)

    assert report.total_runs == len(AGENT_REGRESSION_CASES)
    assert report.failed_runs == 0
