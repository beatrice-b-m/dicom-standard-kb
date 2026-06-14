from __future__ import annotations

from dicom_kb.eval.prompt_cases import AGENT_REGRESSION_CASES

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


def test_agent_prompt_case_floor_ids_and_edition_pins() -> None:
    case_ids = [case.id for case in AGENT_REGRESSION_CASES]

    assert len(AGENT_REGRESSION_CASES) >= 50
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
