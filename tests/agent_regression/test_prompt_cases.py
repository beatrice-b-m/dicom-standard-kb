from __future__ import annotations

from dicom_kb.eval.expected_tool_traces import EXPECTED_TOOL_TRACES
from dicom_kb.eval.prompt_cases import (
    AGENT_REGRESSION_CASES,
    V2_UNSUPPORTED_CASES,
    V2_WORKFLOW_CASES,
)

V1_AGENT_TOOL_NAMES = {
    "lookup_data_element",
    "lookup_uid",
    "lookup_sop_class",
    "lookup_iod",
    "lookup_enumerated_values",
    "lookup_defined_terms",
    "list_modules_for_iod",
    "list_attributes_for_module",
    "resolve_attribute_context",
    "retrieve_standard_text",
    "search_standard_text",
}
V2_AGENT_TOOL_NAMES = {
    "lookup_vr",
    "lookup_transfer_syntax",
    "explain_encoding_rule",
    "lookup_media_type",
    "lookup_dicomweb_transaction",
    "lookup_sr_template",
    "lookup_context_group",
    "lookup_code_meaning",
}


def test_agent_prompt_case_floor_ids_and_edition_pins() -> None:
    case_ids = [case.id for case in AGENT_REGRESSION_CASES]

    assert len(AGENT_REGRESSION_CASES) >= 100
    assert len(case_ids) == len(set(case_ids))
    assert all(case.edition == "2026b" for case in AGENT_REGRESSION_CASES)
    assert all(case.expected_tools for case in AGENT_REGRESSION_CASES)


def test_agent_prompt_cases_cover_all_v1_tools() -> None:
    covered_tool_names = {
        tool
        for case in AGENT_REGRESSION_CASES
        for tool in case.expected_tools
    }

    assert covered_tool_names >= V1_AGENT_TOOL_NAMES


def test_agent_prompt_cases_cover_v2_public_tools() -> None:
    covered_tool_names = {
        tool
        for case in AGENT_REGRESSION_CASES
        for tool in case.expected_tools
    }
    v2_case_ids = {
        case.id
        for case in AGENT_REGRESSION_CASES
        if case.id.startswith("agent.v2.")
    }

    assert covered_tool_names >= V2_AGENT_TOOL_NAMES
    assert len(v2_case_ids) >= len(V2_AGENT_TOOL_NAMES)
    assert all(case_id in EXPECTED_TOOL_TRACES for case_id in v2_case_ids)


def test_agent_prompt_cases_cover_v2_unsupported_claim_domains() -> None:
    unsupported_cases = [
        case
        for case in AGENT_REGRESSION_CASES
        if case.id.startswith("agent.v2.unsupported.")
    ]
    unsupported_case_ids = {case.id for case in unsupported_cases}

    assert len(unsupported_cases) >= 12
    assert {domain for _case_id, domain, *_rest in V2_UNSUPPORTED_CASES} >= {
        "transfer_syntax",
        "dicomweb",
        "media_type",
        "tid",
        "cid",
        "code_lookup",
    }
    assert all("unsupported" in case.must_include for case in unsupported_cases)
    assert all(
        "uncited normative claims" in case.must_not_include
        for case in unsupported_cases
    )
    assert unsupported_case_ids <= set(EXPECTED_TOOL_TRACES)


def test_agent_prompt_cases_include_v2_workflow_final_batch() -> None:
    workflow_cases = [
        case
        for case in AGENT_REGRESSION_CASES
        if case.id.startswith("agent.v2.workflow.")
    ]
    workflow_case_ids = {case.id for case in workflow_cases}

    assert len(workflow_cases) >= 12
    assert len(V2_WORKFLOW_CASES) >= 12
    assert all(case_id in EXPECTED_TOOL_TRACES for case_id in workflow_case_ids)
    assert all(
        len(EXPECTED_TOOL_TRACES[case.id]) == len(case.expected_tools)
        for case in workflow_cases
    )


def test_agent_prompt_cases_include_error_and_ambiguity_floor() -> None:
    error_cases = [
        case for case in AGENT_REGRESSION_CASES if case.id.startswith("agent.error.")
    ]

    assert len(error_cases) >= 8
    assert all(
        any(
            required in {"validation", "not found", "warning"}
            for required in case.must_include
        )
        for case in error_cases
    )


def test_agent_prompt_cases_include_phase7_prose_retrieval() -> None:
    cases_by_id = {case.id: case for case in AGENT_REGRESSION_CASES}

    ps37_case = cases_by_id["agent.text.dimse_service_behavior"]
    ps38_case = cases_by_id["agent.text.association_pdu_behavior"]

    assert ps37_case.expected_tools == ("retrieve_standard_text",)
    assert set(ps37_case.must_include) >= {
        "edition",
        "source references",
        "PS3.7",
        "DIMSE services",
    }
    assert ps38_case.expected_tools == ("retrieve_standard_text",)
    assert set(ps38_case.must_include) >= {
        "edition",
        "source references",
        "PS3.8",
        "PDU Fields",
    }
    assert "agent.text.dimse_service_behavior" in EXPECTED_TOOL_TRACES
    assert "agent.text.association_pdu_behavior" in EXPECTED_TOOL_TRACES
