"""Edition-pinned prompt cases for agent regression tests."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AgentRegressionCase(BaseModel):
    """A prompt and deterministic expectations for an agent answer."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition: str
    prompt: str
    expected_tools: tuple[str, ...]
    must_include: tuple[str, ...] = ()
    must_not_include: tuple[str, ...] = ()


AGENT_REGRESSION_CASES: tuple[AgentRegressionCase, ...] = (
    AgentRegressionCase(
        id="agent.ct.required_modules",
        edition="2026b",
        prompt="List the required modules for CT Image IOD and cite the standard.",
        expected_tools=("lookup_iod", "list_modules_for_iod"),
        must_include=("edition", "module usage", "source references"),
        must_not_include=(
            "uncited normative claims",
            "official conformance certification",
        ),
    ),
    AgentRegressionCase(
        id="agent.ct.modality_context",
        edition="2026b",
        prompt=(
            "For CT Image Storage, explain the Modality attribute usage "
            "and cite the standard."
        ),
        expected_tools=(
            "lookup_uid",
            "lookup_sop_class",
            "resolve_attribute_context",
        ),
        must_include=("edition", "Modality", "source references"),
        must_not_include=(
            "uncited normative claims",
            "official conformance certification",
        ),
    ),
    AgentRegressionCase(
        id="agent.ps36.transfer_syntax",
        edition="2026b",
        prompt=(
            "Look up Explicit VR Big Endian and say whether it is retired, "
            "with a citation."
        ),
        expected_tools=("lookup_uid",),
        must_include=("edition", "retired", "source references"),
        must_not_include=("uncited normative claims",),
    ),
)


def get_agent_regression_case(case_id: str) -> AgentRegressionCase:
    """Return a committed agent regression case by id."""
    for case in AGENT_REGRESSION_CASES:
        if case.id == case_id:
            return case
    raise KeyError(f"unknown agent regression case: {case_id}")
