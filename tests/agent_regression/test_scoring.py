from __future__ import annotations

import json
from pathlib import Path

from dicom_kb.eval import AgentRun, ObservedToolCall, score_agent_run
from dicom_kb.eval.prompt_cases import get_agent_regression_case
from dicom_kb.eval.reporting import load_agent_runs, score_agent_run_file


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


def test_agent_score_rejects_v2_unsupported_normative_claims() -> None:
    case = get_agent_regression_case(
        "agent.v2.unsupported.dicomweb.unknown_transaction"
    )
    run = AgentRun(
        case_id=case.id,
        edition="2026b",
        answer=(
            "For edition 2026b, BulkDeleteInstances is a supported DICOMweb "
            "DELETE route with PS3.18 source references."
        ),
        tool_calls=(
            ObservedToolCall(
                tool="lookup_dicomweb_transaction",
                arguments={"name_or_route": "BulkDeleteInstances"},
                response_status="not_found",
                response_edition="2026b",
                response_ref_count=0,
            ),
            ObservedToolCall(
                tool="lookup_data_element",
                arguments={"tag_or_keyword": "Modality"},
                response_status="ok",
                response_edition="2026b",
                response_ref_count=1,
            ),
        ),
        unsupported_normative_claims=(
            "BulkDeleteInstances is a supported DICOMweb DELETE route.",
        ),
    )

    scorecard = score_agent_run(case, run)

    assert scorecard.passed is False
    assert any(
        issue.code == "unsupported_normative_claim" for issue in scorecard.issues
    )


def test_agent_score_requires_positive_v2_tool_status() -> None:
    case = get_agent_regression_case("agent.v2.vr.person_name")
    run = AgentRun(
        case_id=case.id,
        edition="2026b",
        answer=(
            "For edition 2026b, PN means Person Name with PS3.5 source "
            "references and citations."
        ),
        tool_calls=(
            ObservedToolCall(
                tool="lookup_vr",
                arguments={"vr": "PN"},
                response_status="not_found",
                response_edition="2026b",
                response_ref_count=0,
            ),
            ObservedToolCall(
                tool="lookup_data_element",
                arguments={"tag_or_keyword": "Modality"},
                response_status="ok",
                response_edition="2026b",
                response_ref_count=1,
                response_parts=("PS3.3",),
            ),
        ),
    )

    scorecard = score_agent_run(case, run)
    issue_codes = {issue.code for issue in scorecard.issues}

    assert scorecard.passed is False
    assert "tool_status_mismatch" in issue_codes
    assert "citation_part_mismatch" in issue_codes


def test_agent_score_requires_positive_v2_tool_part_citation() -> None:
    case = get_agent_regression_case("agent.v2.dicomweb.retrieve_study")
    run = AgentRun(
        case_id=case.id,
        edition="2026b",
        answer=(
            "For edition 2026b, RetrieveStudy uses GET with PS3.18 source "
            "references and citations."
        ),
        tool_calls=(
            ObservedToolCall(
                tool="lookup_dicomweb_transaction",
                arguments={"name_or_route": "RetrieveStudy"},
                response_status="ok",
                response_edition="2026b",
                response_ref_count=1,
                response_parts=("PS3.3",),
            ),
        ),
    )

    scorecard = score_agent_run(case, run)

    assert scorecard.passed is False
    assert [issue.code for issue in scorecard.issues] == ["citation_part_mismatch"]


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


def test_agent_report_scores_transcript_file(tmp_path: Path) -> None:
    transcript = tmp_path / "agent-runs.json"
    transcript.write_text(
        json.dumps(
            {
                "runs": [
                    {
                        "case_id": "agent.ct.required_modules",
                        "edition": "2026b",
                        "answer": (
                            "For edition 2026b, CT Image IOD module usage "
                            "is cited from PS3.3 source references."
                        ),
                        "tool_calls": [
                            {
                                "tool": "dicom_lookup_iod",
                                "arguments": {"iod_name": "CT Image"},
                                "response_status": "ok",
                                "response_edition": "2026b",
                                "response_ref_count": 1,
                            },
                            {
                                "tool": "dicom_list_modules_for_iod",
                                "arguments": {"iod_name": "CT Image"},
                                "response_status": "ok",
                                "response_edition": "2026b",
                                "response_ref_count": 3,
                            },
                        ],
                    },
                    {
                        "case_id": "agent.unknown",
                        "edition": "2026b",
                        "answer": "No committed prompt case exists.",
                        "tool_calls": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    report = score_agent_run_file(transcript)

    assert report.total_runs == 2
    assert report.passed_runs == 1
    assert report.failed_runs == 1
    assert report.scorecards[0].passed is True
    assert report.scorecards[1].issues[0].code == "unknown_case"


def test_agent_run_loader_accepts_single_run_object(tmp_path: Path) -> None:
    transcript = tmp_path / "agent-run.json"
    transcript.write_text(
        json.dumps(
            {
                "case_id": "agent.ps36.transfer_syntax",
                "edition": "2026b",
                "answer": "For edition 2026b, PS3.6 source references exist.",
                "tool_calls": [
                    {
                        "tool": "lookup_uid",
                        "arguments": {"uid_or_keyword": "ExplicitVRBigEndian"},
                        "response_status": "ok",
                        "response_edition": "2026b",
                        "response_ref_count": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    runs = load_agent_runs(transcript)

    assert len(runs) == 1
    assert runs[0].case_id == "agent.ps36.transfer_syntax"
