"""Agent regression harness primitives."""

from dicom_kb.eval.prompt_cases import AGENT_REGRESSION_CASES, AgentRegressionCase
from dicom_kb.eval.scoring import AgentRun, ObservedToolCall, Scorecard, score_agent_run

__all__ = [
    "AGENT_REGRESSION_CASES",
    "AgentRegressionCase",
    "AgentRun",
    "ObservedToolCall",
    "Scorecard",
    "score_agent_run",
]
