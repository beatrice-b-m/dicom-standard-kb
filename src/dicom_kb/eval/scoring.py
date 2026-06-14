"""Deterministic scoring for agent regression transcripts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from dicom_kb.eval.expected_tool_traces import EXPECTED_TOOL_TRACES, ExpectedToolCall
from dicom_kb.eval.prompt_cases import AgentRegressionCase


class ObservedToolCall(BaseModel):
    """A compact tool trace recorded from an agent run."""

    model_config = ConfigDict(frozen=True)

    tool: str
    arguments: dict[str, str] = Field(default_factory=dict)
    response_status: str | None = None
    response_edition: str | None = None
    response_ref_count: int = 0
    response_parts: tuple[str, ...] = ()
    response_terms: tuple[str, ...] = ()


class AgentRun(BaseModel):
    """An answer transcript to score against one regression case."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    edition: str
    answer: str
    tool_calls: tuple[ObservedToolCall, ...] = ()
    unsupported_normative_claims: tuple[str, ...] = ()


class ScoreIssue(BaseModel):
    """One deterministic scoring failure."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str


class Scorecard(BaseModel):
    """Scoring result for one agent regression run."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    passed: bool
    observed_tools: tuple[str, ...]
    issues: tuple[ScoreIssue, ...]


def score_agent_run(case: AgentRegressionCase, run: AgentRun) -> Scorecard:
    """Score one agent run against committed case and trace expectations."""
    issues: list[ScoreIssue] = []
    observed_tools = tuple(_normalize_tool_name(call.tool) for call in run.tool_calls)

    if run.case_id != case.id:
        issues.append(
            ScoreIssue(
                code="case_mismatch",
                message=f"run case {run.case_id!r} does not match {case.id!r}",
            )
        )
    if run.edition != case.edition:
        issues.append(
            ScoreIssue(
                code="edition_mismatch",
                message=f"run edition {run.edition!r} does not match {case.edition!r}",
            )
        )

    for tool in case.expected_tools:
        if _normalize_tool_name(tool) not in observed_tools:
            issues.append(
                ScoreIssue(
                    code="missing_tool",
                    message=f"required tool was not called: {tool}",
                )
            )

    if not run.tool_calls:
        issues.append(
            ScoreIssue(
                code="missing_tool_output",
                message="answer was not produced from recorded tool output",
            )
        )
    elif not any(call.response_status is not None for call in run.tool_calls):
        issues.append(
            ScoreIssue(
                code="missing_tool_output",
                message="recorded tool calls did not include response metadata",
            )
        )

    _score_expected_trace(case.id, run.tool_calls, issues)
    _score_required_answer_content(case, run, issues)
    _score_forbidden_answer_content(case, run, issues)

    return Scorecard(
        case_id=case.id,
        passed=not issues,
        observed_tools=observed_tools,
        issues=tuple(issues),
    )


def _score_expected_trace(
    case_id: str,
    tool_calls: tuple[ObservedToolCall, ...],
    issues: list[ScoreIssue],
) -> None:
    expected_trace = EXPECTED_TOOL_TRACES.get(case_id, ())
    if not expected_trace:
        return

    cursor = 0
    for expected in expected_trace:
        match_index = _find_matching_tool(expected, tool_calls, start=cursor)
        if match_index is None:
            issues.append(
                ScoreIssue(
                    code="trace_mismatch",
                    message=f"expected trace step was not observed: {expected.tool}",
                )
            )
            continue
        _score_expected_arguments(expected, tool_calls[match_index], issues)
        _score_expected_response(expected, tool_calls[match_index], issues)
        cursor = match_index + 1


def _find_matching_tool(
    expected: ExpectedToolCall,
    tool_calls: tuple[ObservedToolCall, ...],
    *,
    start: int,
) -> int | None:
    expected_tool = _normalize_tool_name(expected.tool)
    for index, call in enumerate(tool_calls[start:], start=start):
        if _normalize_tool_name(call.tool) == expected_tool:
            return index
    return None


def _score_expected_arguments(
    expected: ExpectedToolCall,
    observed: ObservedToolCall,
    issues: list[ScoreIssue],
) -> None:
    for key, expected_value in expected.arguments.items():
        if observed.arguments.get(key) != expected_value:
            issues.append(
                ScoreIssue(
                    code="argument_mismatch",
                    message=(
                        f"{expected.tool} expected argument {key}="
                        f"{expected_value!r}, observed "
                        f"{observed.arguments.get(key)!r}"
                    ),
                )
            )


def _score_expected_response(
    expected: ExpectedToolCall,
    observed: ObservedToolCall,
    issues: list[ScoreIssue],
) -> None:
    if (
        expected.required_status is not None
        and observed.response_status != expected.required_status
    ):
        issues.append(
            ScoreIssue(
                code="tool_status_mismatch",
                message=(
                    f"{expected.tool} expected status "
                    f"{expected.required_status!r}, observed "
                    f"{observed.response_status!r}"
                ),
            )
        )
    if expected.required_parts and not _has_required_part(
        observed,
        expected.required_parts,
    ):
        issues.append(
            ScoreIssue(
                code="citation_part_mismatch",
                message=(
                    f"{expected.tool} expected citation from one of "
                    f"{', '.join(expected.required_parts)}, observed "
                    f"{', '.join(observed.response_parts) or 'none'}"
                ),
            )
        )


def _has_required_part(
    observed: ObservedToolCall,
    required_parts: tuple[str, ...],
) -> bool:
    return bool(set(required_parts).intersection(observed.response_parts))


def _score_required_answer_content(
    case: AgentRegressionCase,
    run: AgentRun,
    issues: list[ScoreIssue],
) -> None:
    answer = run.answer.casefold()
    for required in case.must_include:
        if not _required_content_is_present(
            required,
            case=case,
            run=run,
            answer=answer,
        ):
            issues.append(
                ScoreIssue(
                    code="missing_answer_content",
                    message=f"answer did not include required content: {required}",
                )
            )


def _required_content_is_present(
    required: str,
    *,
    case: AgentRegressionCase,
    run: AgentRun,
    answer: str,
) -> bool:
    normalized = required.casefold()
    if normalized == "edition":
        return case.edition.casefold() in answer
    if normalized == "source references":
        return _has_source_references(run) and (
            "ps3." in answer or "source" in answer or "citation" in answer
        )
    if normalized == "module usage":
        return "module" in answer and "usage" in answer
    return normalized in answer


def _score_forbidden_answer_content(
    case: AgentRegressionCase,
    run: AgentRun,
    issues: list[ScoreIssue],
) -> None:
    answer = run.answer.casefold()
    for forbidden in case.must_not_include:
        normalized = forbidden.casefold()
        if normalized == "uncited normative claims":
            if run.unsupported_normative_claims:
                issues.append(
                    ScoreIssue(
                        code="unsupported_normative_claim",
                        message=(
                            "answer included unsupported normative claims: "
                            + "; ".join(run.unsupported_normative_claims)
                        ),
                    )
                )
            continue
        if normalized in answer:
            issues.append(
                ScoreIssue(
                    code="forbidden_answer_content",
                    message=f"answer included forbidden content: {forbidden}",
                )
            )


def _has_source_references(run: AgentRun) -> bool:
    return any(
        call.response_status == "ok"
        and call.response_edition == run.edition
        and call.response_ref_count > 0
        for call in run.tool_calls
    )


def _normalize_tool_name(tool: str) -> str:
    return tool.removeprefix("dicom_")
