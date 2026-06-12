from __future__ import annotations

from dicom_kb.eval import AgentRun, ObservedToolCall, score_agent_run
from dicom_kb.eval.prompt_cases import get_agent_regression_case


def test_agent_score_passes_when_required_tools_and_citations_are_present() -> None:
    case = get_agent_regression_case("agent.ct.required_modules")
    run = AgentRun(
        case_id=case.id,
        edition="2026b",
        answer=(
            "For edition 2026b, CT Image IOD module usage is cited from "
            "PS3.3 table A.3-1 source references."
        ),
        tool_calls=(
            ObservedToolCall(
                tool="dicom_lookup_iod",
                arguments={"iod_name": "CT Image"},
                response_status="ok",
                response_edition="2026b",
                response_ref_count=1,
            ),
            ObservedToolCall(
                tool="dicom_list_modules_for_iod",
                arguments={"iod_name": "CT Image"},
                response_status="ok",
                response_edition="2026b",
                response_ref_count=3,
            ),
        ),
    )

    scorecard = score_agent_run(case, run)

    assert scorecard.passed is True
    assert scorecard.issues == ()
    assert scorecard.observed_tools == ("lookup_iod", "list_modules_for_iod")


def test_agent_score_reports_missing_tools_and_uncited_claims() -> None:
    case = get_agent_regression_case("agent.ct.modality_context")
    run = AgentRun(
        case_id=case.id,
        edition="2026b",
        answer="The CT Modality value is required.",
        tool_calls=(
            ObservedToolCall(
                tool="lookup_uid",
                arguments={"uid_or_keyword": "CTImageStorage"},
                response_status="ok",
                response_edition="2026b",
                response_ref_count=0,
            ),
        ),
        unsupported_normative_claims=("The CT Modality value is required.",),
    )

    scorecard = score_agent_run(case, run)
    issue_codes = {issue.code for issue in scorecard.issues}

    assert scorecard.passed is False
    assert "missing_tool" in issue_codes
    assert "trace_mismatch" in issue_codes
    assert "missing_answer_content" in issue_codes
    assert "unsupported_normative_claim" in issue_codes


def test_agent_score_reports_expected_argument_mismatch() -> None:
    case = get_agent_regression_case("agent.ps36.transfer_syntax")
    run = AgentRun(
        case_id=case.id,
        edition="2026b",
        answer=(
            "For edition 2026b, Explicit VR Big Endian is retired; citation "
            "PS3.6 is present."
        ),
        tool_calls=(
            ObservedToolCall(
                tool="lookup_uid",
                arguments={"uid_or_keyword": "ExplicitVRLittleEndian"},
                response_status="ok",
                response_edition="2026b",
                response_ref_count=1,
            ),
        ),
    )

    scorecard = score_agent_run(case, run)

    assert scorecard.passed is False
    assert [issue.code for issue in scorecard.issues] == ["argument_mismatch"]
