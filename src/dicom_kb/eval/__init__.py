"""Agent regression harness primitives."""

from dicom_kb.eval.prompt_cases import AGENT_REGRESSION_CASES, AgentRegressionCase
from dicom_kb.eval.reporting import (
    AgentRegressionReport,
    load_agent_runs,
    score_agent_run_file,
    score_agent_runs,
)
from dicom_kb.eval.scoring import AgentRun, ObservedToolCall, Scorecard, score_agent_run

__all__ = [
    "AGENT_REGRESSION_CASES",
    "AgentRegressionCase",
    "AgentRegressionReport",
    "AgentRun",
    "ObservedToolCall",
    "Scorecard",
    "load_agent_runs",
    "score_agent_run",
    "score_agent_run_file",
    "score_agent_runs",
]
