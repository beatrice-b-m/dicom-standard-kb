"""Scorecard loading and reporting for agent regression transcripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from dicom_kb.eval.prompt_cases import get_agent_regression_case
from dicom_kb.eval.scoring import AgentRun, Scorecard, ScoreIssue, score_agent_run


class AgentRegressionReport(BaseModel):
    """Aggregate scorecard report for one transcript file."""

    model_config = ConfigDict(frozen=True)

    total_runs: int
    passed_runs: int
    failed_runs: int
    scorecards: tuple[Scorecard, ...]


def load_agent_runs(path: Path) -> tuple[AgentRun, ...]:
    """Load agent run transcripts from a JSON file.

    The file may contain a single ``AgentRun`` object, a list of run objects,
    or an object with a top-level ``runs`` list.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return tuple(AgentRun.model_validate(item) for item in payload)
    if isinstance(payload, dict) and "runs" in payload:
        runs = payload["runs"]
        if not isinstance(runs, list):
            raise ValueError("agent transcript 'runs' field must be a list")
        return tuple(AgentRun.model_validate(item) for item in runs)
    if isinstance(payload, dict):
        return (AgentRun.model_validate(payload),)
    raise ValueError("agent transcript must be a JSON object or list")


def score_agent_runs(runs: tuple[AgentRun, ...]) -> AgentRegressionReport:
    """Score multiple recorded agent runs against committed prompt cases."""
    scorecards = tuple(_score_known_or_unknown_case(run) for run in runs)
    passed = sum(1 for scorecard in scorecards if scorecard.passed)
    return AgentRegressionReport(
        total_runs=len(scorecards),
        passed_runs=passed,
        failed_runs=len(scorecards) - passed,
        scorecards=scorecards,
    )


def score_agent_run_file(path: Path) -> AgentRegressionReport:
    """Load and score an agent transcript file."""
    return score_agent_runs(load_agent_runs(path))


def _score_known_or_unknown_case(run: AgentRun) -> Scorecard:
    try:
        case = get_agent_regression_case(run.case_id)
    except KeyError:
        return Scorecard(
            case_id=run.case_id,
            passed=False,
            observed_tools=tuple(
                call.tool.removeprefix("dicom_") for call in run.tool_calls
            ),
            issues=(
                ScoreIssue(
                    code="unknown_case",
                    message=f"no committed agent regression case exists: {run.case_id}",
                ),
            ),
        )
    return score_agent_run(case, run)


def report_as_jsonable(report: AgentRegressionReport) -> dict[str, Any]:
    """Return a stable JSON-ready report payload."""
    return report.model_dump(mode="json")
