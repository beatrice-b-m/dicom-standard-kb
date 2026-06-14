from __future__ import annotations

import sqlite3

from dicom_kb.eval.prompt_cases import AGENT_REGRESSION_CASES
from dicom_kb.eval.reporting import score_agent_runs
from dicom_kb.eval.runner import run_reference_agent_cases


def test_reference_agent_scores_all_cases_against_real_kb(
    connection: sqlite3.Connection,
    edition: str,
) -> None:
    runs = run_reference_agent_cases(
        connection,
        edition=edition,
        cases=AGENT_REGRESSION_CASES,
    )

    report = score_agent_runs(runs)

    assert report.total_runs == len(AGENT_REGRESSION_CASES)
    assert report.failed_runs == 0
