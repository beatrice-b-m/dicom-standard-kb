"""Deterministic reference runner for agent regression prompt cases."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path

from dicom_kb.eval.prompt_cases import (
    AGENT_REGRESSION_CASES,
    DATA_ELEMENTS,
    IODS,
    MODULES,
    SEARCH_QUERIES,
    SOP_CLASS_TO_IOD,
    TEXT_RETRIEVAL_TARGETS,
    UIDS,
    AgentRegressionCase,
    get_agent_regression_case,
)
from dicom_kb.eval.scoring import AgentRun, ObservedToolCall
from dicom_kb.query.answer_contracts import ToolResponse
from dicom_kb.query.resolver import (
    list_attributes_for_module,
    list_modules_for_iod,
    lookup_data_element,
    lookup_defined_terms,
    lookup_enumerated_values,
    lookup_iod,
    lookup_sop_class,
    lookup_uid,
    resolve_attribute_context,
    retrieve_standard_text,
    search_standard_text,
)

ToolInvoker = Callable[[str, dict[str, str]], ToolResponse]

ATTRIBUTE_CONTEXTS = {
    "ct_modality": ("Modality", "CT Image"),
    "mr_modality": ("Modality", "MR Image"),
    "ct_sop_class_uid": ("SOP Class UID", "CT Image"),
    "mr_sop_instance_uid": ("SOP Instance UID", "MR Image"),
    "ct_pixel_data": ("Pixel Data", "CT Image"),
    "general_series_modality": ("(0008,0060)", "MR Image"),
}


def run_reference_agent_cases(
    connection: sqlite3.Connection,
    *,
    edition: str,
    cases: tuple[AgentRegressionCase, ...] = AGENT_REGRESSION_CASES,
) -> tuple[AgentRun, ...]:
    """Run the deterministic reference agent over committed prompt cases."""
    return tuple(
        run_reference_agent_case(connection, case=case, edition=edition)
        for case in cases
    )


def run_reference_agent_case(
    connection: sqlite3.Connection,
    *,
    case: AgentRegressionCase,
    edition: str,
) -> AgentRun:
    """Run one prompt case through deterministic resolver routing."""
    observed: list[ObservedToolCall] = []

    def invoke(tool: str, arguments: dict[str, str]) -> ToolResponse:
        response = _invoke_tool(
            connection,
            tool=tool,
            arguments=arguments,
            edition=edition,
        )
        observed.append(_observed_call(response, arguments))
        return response

    _run_case_route(case, invoke)
    _ensure_source_reference(observed, invoke)
    return AgentRun(
        case_id=case.id,
        edition=edition,
        answer=_reference_answer(case, edition=edition, tool_calls=tuple(observed)),
        tool_calls=tuple(observed),
    )


def select_agent_regression_cases(
    case_ids: tuple[str, ...],
) -> tuple[AgentRegressionCase, ...]:
    """Return selected cases or all committed cases when no ids are supplied."""
    if not case_ids:
        return AGENT_REGRESSION_CASES
    return tuple(get_agent_regression_case(case_id) for case_id in case_ids)


def write_agent_runs(path: Path, runs: tuple[AgentRun, ...]) -> None:
    """Write compact agent run transcripts in the scorecard input shape."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"runs": [run.model_dump(mode="json") for run in runs]}
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run_case_route(case: AgentRegressionCase, invoke: ToolInvoker) -> None:
    case_id = case.id
    if case_id == "agent.ct.required_modules":
        _lookup_iod_modules(invoke, "CT Image")
    elif case_id == "agent.ct.modality_context":
        invoke("lookup_uid", {"uid_or_keyword": "CTImageStorage"})
        invoke(
            "lookup_sop_class",
            {"uid_or_name_or_keyword": "CT Image Storage"},
        )
        invoke(
            "resolve_attribute_context",
            {"attribute": "Modality", "sop_class": "CT Image Storage"},
        )
    elif case_id == "agent.ps36.transfer_syntax":
        invoke("lookup_uid", {"uid_or_keyword": "ExplicitVRBigEndian"})
    elif case_id.startswith("agent.iod."):
        iod = _entity_from_slug(case_id, IODS, prefix="agent.iod.", suffix=".modules")
        _lookup_iod_modules(invoke, iod)
    elif case_id.startswith("agent.module."):
        module = _entity_from_slug(
            case_id,
            MODULES,
            prefix="agent.module.",
            suffix=".attributes",
        )
        invoke("list_attributes_for_module", {"module_name": module})
    elif case_id.startswith("agent.data_element."):
        case_key = case_id.removeprefix("agent.data_element.")
        tag = _data_element_tag(case_key)
        invoke("lookup_data_element", {"tag_or_keyword": tag})
    elif case_id.startswith("agent.uid."):
        case_key = case_id.removeprefix("agent.uid.")
        uid = _uid_value(case_key)
        invoke("lookup_uid", {"uid_or_keyword": uid})
    elif case_id.startswith("agent.sop_class."):
        case_key = case_id.removeprefix("agent.sop_class.").removesuffix(".iod")
        sop_class, _iod = _sop_class_pair(case_key)
        _lookup_sop_class_and_uid(invoke, sop_class)
    elif case_id.startswith("agent.context."):
        case_key = case_id.removeprefix("agent.context.")
        attribute, iod = ATTRIBUTE_CONTEXTS[case_key]
        invoke("lookup_data_element", {"tag_or_keyword": attribute})
        invoke("lookup_iod", {"iod_name": iod})
        invoke(
            "resolve_attribute_context",
            {"attribute": attribute, "iod_name": iod},
        )
    elif case_id == "agent.values.modality.enumerated":
        invoke("lookup_data_element", {"tag_or_keyword": "Modality"})
        invoke("lookup_enumerated_values", {"attribute": "Modality"})
    elif case_id == "agent.values.patient_name.defined":
        invoke("lookup_data_element", {"tag_or_keyword": "Patient's Name"})
        invoke("lookup_defined_terms", {"attribute": "Patient's Name"})
    elif case_id.startswith("agent.text."):
        case_key = case_id.removeprefix("agent.text.")
        part, anchor = _text_target(case_key)
        invoke(
            "retrieve_standard_text",
            {"part": part, "section_or_anchor": anchor, "max_chars": "800"},
        )
    elif case_id.startswith("agent.search."):
        case_key = case_id.removeprefix("agent.search.")
        query, part = _search_target(case_key)
        invoke(
            "search_standard_text",
            {"query": query, "part_filter": part, "limit": "10"},
        )
    elif case_id.startswith("agent.workflow."):
        _run_workflow(case_id, invoke)
    elif case_id.startswith("agent.error."):
        _run_error_case(case_id, invoke)
    else:
        raise ValueError(f"no reference route for case: {case_id}")


def _lookup_iod_modules(invoke: ToolInvoker, iod: str) -> None:
    invoke("lookup_iod", {"iod_name": iod})
    invoke("list_modules_for_iod", {"iod_name": iod})


def _lookup_sop_class_and_uid(invoke: ToolInvoker, sop_class: str) -> None:
    response = invoke("lookup_sop_class", {"uid_or_name_or_keyword": sop_class})
    if response.status == "ok" and response.result is not None:
        sop_result = response.result["sop_class"]
        invoke("lookup_uid", {"uid_or_keyword": str(sop_result["uid_value"])})
        return
    invoke("lookup_uid", {"uid_or_keyword": sop_class.replace(" ", "")})


def _run_workflow(case_id: str, invoke: ToolInvoker) -> None:
    if case_id == "agent.workflow.ct_storage_to_pixel_data":
        invoke("lookup_uid", {"uid_or_keyword": _uid_value("ct_storage")})
        invoke("lookup_sop_class", {"uid_or_name_or_keyword": "CT Image Storage"})
        invoke("list_modules_for_iod", {"iod_name": "CT Image"})
        invoke(
            "resolve_attribute_context",
            {"attribute": "Pixel Data", "iod_name": "CT Image"},
        )
    elif case_id == "agent.workflow.segmentation_storage_to_modules":
        invoke("lookup_uid", {"uid_or_keyword": _uid_value("segmentation_storage")})
        invoke("lookup_sop_class", {"uid_or_name_or_keyword": "Segmentation Storage"})
        invoke("list_modules_for_iod", {"iod_name": "Segmentation"})
    elif case_id == "agent.workflow.mr_modality_dictionary_context":
        invoke("lookup_uid", {"uid_or_keyword": _uid_value("mr_storage")})
        invoke("lookup_sop_class", {"uid_or_name_or_keyword": "MR Image Storage"})
        invoke("lookup_data_element", {"tag_or_keyword": "Modality"})
        invoke(
            "resolve_attribute_context",
            {"attribute": "Modality", "iod_name": "MR Image"},
        )
    elif case_id == "agent.workflow.encapsulated_pdf_modules_text":
        _lookup_sop_class_and_uid(invoke, "Encapsulated PDF Storage")
        invoke("list_modules_for_iod", {"iod_name": "Encapsulated PDF"})
        invoke(
            "retrieve_standard_text",
            {
                "part": "PS3.3",
                "section_or_anchor": "table_A.45.1-1",
                "max_chars": "800",
            },
        )
    elif case_id == "agent.workflow.transfer_syntax_search":
        invoke(
            "lookup_uid",
            {"uid_or_keyword": _uid_value("explicit_vr_little_endian")},
        )
        invoke(
            "search_standard_text",
            {"query": "Transfer Syntax UID", "part_filter": "PS3.6", "limit": "10"},
        )
    else:
        raise ValueError(f"no reference workflow route for case: {case_id}")


def _run_error_case(case_id: str, invoke: ToolInvoker) -> None:
    case_key = case_id.removeprefix("agent.error.")
    if case_key == "malformed_tag":
        invoke("lookup_data_element", {"tag_or_keyword": "0008-0060"})
    elif case_key == "unknown_tag":
        invoke("lookup_data_element", {"tag_or_keyword": "(9999,9999)"})
    elif case_key == "range_overlay_tag":
        invoke("lookup_data_element", {"tag_or_keyword": "(6002,3000)"})
    elif case_key == "malformed_uid":
        invoke("lookup_uid", {"uid_or_keyword": "1.2.840..10008"})
    elif case_key == "unknown_uid":
        invoke("lookup_uid", {"uid_or_keyword": "1.2.840.10008.999999"})
    elif case_key == "unknown_iod":
        invoke("lookup_iod", {"iod_name": "Made Up Image"})
    elif case_key == "unknown_module":
        invoke("list_attributes_for_module", {"module_name": "Made Up Module"})
    elif case_key == "invalid_context":
        invoke("resolve_attribute_context", {"attribute": "Modality"})
    elif case_key == "invalid_retrieve_part":
        invoke(
            "retrieve_standard_text",
            {"part": "DICOM-3", "section_or_anchor": "table_6-1", "max_chars": "800"},
        )
    elif case_key == "empty_search":
        invoke("search_standard_text", {"query": "", "limit": "10"})
    else:
        raise ValueError(f"no reference error route for case: {case_id}")


def _invoke_tool(
    connection: sqlite3.Connection,
    *,
    tool: str,
    arguments: dict[str, str],
    edition: str,
) -> ToolResponse:
    if tool == "lookup_data_element":
        return lookup_data_element(
            connection,
            tag_or_keyword=arguments["tag_or_keyword"],
            edition=edition,
        )
    if tool == "lookup_uid":
        return lookup_uid(
            connection,
            uid_or_keyword=arguments["uid_or_keyword"],
            edition=edition,
        )
    if tool == "lookup_iod":
        return lookup_iod(connection, iod_name=arguments["iod_name"], edition=edition)
    if tool == "lookup_enumerated_values":
        return lookup_enumerated_values(
            connection,
            attribute=arguments["attribute"],
            edition=edition,
            context=arguments.get("context"),
        )
    if tool == "lookup_defined_terms":
        return lookup_defined_terms(
            connection,
            attribute=arguments["attribute"],
            edition=edition,
            context=arguments.get("context"),
        )
    if tool == "lookup_sop_class":
        return lookup_sop_class(
            connection,
            uid_or_name_or_keyword=arguments["uid_or_name_or_keyword"],
            edition=edition,
        )
    if tool == "list_modules_for_iod":
        return list_modules_for_iod(
            connection,
            iod_name=arguments["iod_name"],
            edition=edition,
        )
    if tool == "list_attributes_for_module":
        return list_attributes_for_module(
            connection,
            module_name=arguments["module_name"],
            edition=edition,
            expand_macros=arguments.get("expand_macros") == "true",
        )
    if tool == "resolve_attribute_context":
        return resolve_attribute_context(
            connection,
            attribute=arguments["attribute"],
            edition=edition,
            iod_name=arguments.get("iod_name"),
            sop_class=arguments.get("sop_class"),
        )
    if tool == "retrieve_standard_text":
        return retrieve_standard_text(
            connection,
            part=arguments["part"],
            section_or_anchor=arguments["section_or_anchor"],
            edition=edition,
            max_chars=int(arguments.get("max_chars", "800")),
        )
    if tool == "search_standard_text":
        return search_standard_text(
            connection,
            query=arguments["query"],
            edition=edition,
            part_filter=arguments.get("part_filter"),
            limit=int(arguments.get("limit", "10")),
        )
    raise ValueError(f"unknown tool: {tool}")


def _observed_call(
    response: ToolResponse,
    arguments: dict[str, str],
) -> ObservedToolCall:
    return ObservedToolCall(
        tool=response.tool,
        arguments=arguments,
        response_status=response.status,
        response_edition=response.edition,
        response_ref_count=len(response.refs),
    )


def _ensure_source_reference(
    observed: list[ObservedToolCall],
    invoke: ToolInvoker,
) -> None:
    if any(
        call.response_status == "ok"
        and call.response_edition is not None
        and call.response_ref_count > 0
        for call in observed
    ):
        return
    invoke("lookup_data_element", {"tag_or_keyword": "Modality"})


def _reference_answer(
    case: AgentRegressionCase,
    *,
    edition: str,
    tool_calls: tuple[ObservedToolCall, ...],
) -> str:
    statuses = ", ".join(
        sorted(
            {
                status
                for call in tool_calls
                if (status := call.response_status) is not None
            }
        )
    )
    warnings = (
        " warning" if any(call.response_status == "ok" for call in tool_calls) else ""
    )
    required_terms = " ".join(
        term
        for term in case.must_include
        if term not in {"edition", "source references"}
    )
    return (
        f"For edition {edition}, the reference agent used source references "
        f"and citations from the recorded tool output. Tool statuses: {statuses}."
        f"{warnings} {required_terms}"
    )


def _entity_from_slug(
    case_id: str,
    values: tuple[str, ...],
    *,
    prefix: str,
    suffix: str,
) -> str:
    slug = case_id.removeprefix(prefix).removesuffix(suffix)
    for value in values:
        if _slug(value) == slug:
            return value
    raise ValueError(f"no entity matches case id: {case_id}")


def _data_element_tag(case_key: str) -> str:
    for candidate_key, tag, _name, _vr, _vm in DATA_ELEMENTS:
        if candidate_key == case_key:
            return tag
    raise ValueError(f"no data element case key: {case_key}")


def _uid_value(case_key: str) -> str:
    for candidate_key, uid, _name in UIDS:
        if candidate_key == case_key:
            return uid
    raise ValueError(f"no UID case key: {case_key}")


def _sop_class_pair(case_key: str) -> tuple[str, str]:
    for candidate_key, sop_class, iod in SOP_CLASS_TO_IOD:
        if candidate_key == case_key:
            return sop_class, iod
    raise ValueError(f"no SOP Class case key: {case_key}")


def _text_target(case_key: str) -> tuple[str, str]:
    for candidate_key, part, anchor, _label in TEXT_RETRIEVAL_TARGETS:
        if candidate_key == case_key:
            return part, anchor
    raise ValueError(f"no text target case key: {case_key}")


def _search_target(case_key: str) -> tuple[str, str]:
    for candidate_key, query, part in SEARCH_QUERIES:
        if candidate_key == case_key:
            return query, part
    raise ValueError(f"no search target case key: {case_key}")


def _slug(value: str) -> str:
    return (
        value.casefold()
        .replace("/", "_")
        .replace("-", "_")
        .replace(" ", "_")
        .replace("'", "")
    )
