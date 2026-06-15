"""Deterministic reference runner for agent regression prompt cases."""

from __future__ import annotations

import json
import os
import shlex
import sqlite3
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from dicom_kb.eval.expected_tool_traces import EXPECTED_TOOL_TRACES
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
    explain_encoding_rule,
    list_attributes_for_module,
    list_modules_for_iod,
    lookup_code_meaning,
    lookup_context_group,
    lookup_data_element,
    lookup_defined_terms,
    lookup_dicomweb_transaction,
    lookup_enumerated_values,
    lookup_iod,
    lookup_media_type,
    lookup_sop_class,
    lookup_sr_template,
    lookup_transfer_syntax,
    lookup_uid,
    lookup_vr,
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


@dataclass(frozen=True)
class ExternalAgentConfig:
    """Configuration for an opt-in external agent harness."""

    command: tuple[str, ...]
    provider: str | None = None
    model: str | None = None
    timeout_seconds: float = 300.0


class ExternalAgentError(RuntimeError):
    """Raised when an external agent run cannot be completed."""


def external_agent_config(
    *,
    command: str | None,
    provider: str | None = None,
    model: str | None = None,
    timeout_seconds: float = 300.0,
) -> ExternalAgentConfig:
    """Build external-agent config from CLI input or environment."""
    command_text = command or os.environ.get("DICOM_KB_EVAL_EXTERNAL_COMMAND")
    if not command_text:
        raise ExternalAgentError(
            "external agent runs require --external-command or "
            "DICOM_KB_EVAL_EXTERNAL_COMMAND"
        )
    argv = tuple(shlex.split(command_text))
    if not argv:
        raise ExternalAgentError("external agent command must not be empty")
    if timeout_seconds <= 0:
        raise ExternalAgentError("external agent timeout must be positive")
    return ExternalAgentConfig(
        command=argv,
        provider=provider,
        model=model,
        timeout_seconds=timeout_seconds,
    )


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


def run_external_agent_cases(
    *,
    config: ExternalAgentConfig,
    edition: str,
    cases: tuple[AgentRegressionCase, ...],
    db_path: Path,
    cache_dir: Path,
) -> tuple[AgentRun, ...]:
    """Run committed prompt cases through an opt-in external agent harness."""
    payload = {
        "edition": edition,
        "provider": config.provider,
        "model": config.model,
        "db_path": str(db_path),
        "cache_dir": str(cache_dir),
        "cases": [case.model_dump(mode="json") for case in cases],
    }
    try:
        completed = subprocess.run(
            config.command,
            input=json.dumps(payload, sort_keys=True),
            text=True,
            capture_output=True,
            timeout=config.timeout_seconds,
            check=False,
        )
    except OSError as exc:
        raise ExternalAgentError(f"failed to start external agent: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ExternalAgentError(
            f"external agent timed out after {config.timeout_seconds:g} seconds"
        ) from exc
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        detail = f": {stderr}" if stderr else ""
        raise ExternalAgentError(
            f"external agent exited with code {completed.returncode}{detail}"
        )
    runs = _parse_external_agent_runs(completed.stdout)
    _validate_external_agent_runs(runs, cases=cases, edition=edition)
    return runs


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
    _ensure_source_reference(case, observed, invoke)
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


def _parse_external_agent_runs(stdout: str) -> tuple[AgentRun, ...]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ExternalAgentError("external agent stdout was not valid JSON") from exc
    if isinstance(payload, dict) and "runs" in payload:
        runs_payload = payload["runs"]
    elif isinstance(payload, list):
        runs_payload = payload
    elif isinstance(payload, dict):
        runs_payload = [payload]
    else:
        raise ExternalAgentError(
            "external agent JSON must be an AgentRun object, list, or runs object"
        )
    if not isinstance(runs_payload, list):
        raise ExternalAgentError("external agent 'runs' field must be a list")
    try:
        return tuple(AgentRun.model_validate(run) for run in runs_payload)
    except ValueError as exc:
        raise ExternalAgentError(
            "external agent returned invalid AgentRun JSON"
        ) from exc


def _validate_external_agent_runs(
    runs: tuple[AgentRun, ...],
    *,
    cases: tuple[AgentRegressionCase, ...],
    edition: str,
) -> None:
    expected_case_ids = {case.id for case in cases}
    observed_case_ids = {run.case_id for run in runs}
    if observed_case_ids != expected_case_ids:
        raise ExternalAgentError(
            "external agent returned case ids "
            f"{sorted(observed_case_ids)!r}; expected {sorted(expected_case_ids)!r}"
        )
    mismatched_editions = sorted(
        {run.edition for run in runs if run.edition != edition}
    )
    if mismatched_editions:
        raise ExternalAgentError(
            "external agent returned unexpected editions: "
            f"{', '.join(mismatched_editions)}"
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
    elif case_id.startswith("agent.v2."):
        _run_v2_tool_case(case_id, invoke)
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


def _run_v2_tool_case(case_id: str, invoke: ToolInvoker) -> None:
    case_key = case_id.removeprefix("agent.v2.")
    if case_key == "vr.person_name":
        invoke("lookup_vr", {"vr": "PN"})
    elif case_key == "transfer_syntax.explicit_little":
        invoke(
            "lookup_transfer_syntax",
            {"uid_or_keyword": _uid_value("explicit_vr_little_endian")},
        )
    elif case_key == "encoding_rule.sequence":
        invoke("explain_encoding_rule", {"topic": "SQ"})
    elif case_key == "media_type.dicom_file":
        invoke("lookup_media_type", {"media_type_or_context": "application/dicom"})
    elif case_key == "dicomweb.retrieve_study":
        invoke("lookup_dicomweb_transaction", {"name_or_route": "RetrieveStudy"})
    elif case_key == "sr_template.measurement_report":
        invoke("lookup_sr_template", {"tid_or_name": "1500"})
    elif case_key == "context_group.acquisition_modality":
        invoke("lookup_context_group", {"cid_or_name": "29"})
    elif case_key == "code_meaning.ct":
        invoke("lookup_code_meaning", {"code_value": "CT", "scheme": "DCM"})
    elif case_key == "unsupported.transfer_syntax.unknown_uid":
        invoke(
            "lookup_transfer_syntax",
            {"uid_or_keyword": "1.2.840.10008.999999"},
        )
    elif case_key == "unsupported.transfer_syntax.malformed_uid":
        invoke("lookup_transfer_syntax", {"uid_or_keyword": "1.2.840..10008"})
    elif case_key == "unsupported.dicomweb.unknown_transaction":
        invoke(
            "lookup_dicomweb_transaction",
            {"name_or_route": "BulkDeleteInstances"},
        )
    elif case_key == "unsupported.dicomweb.empty_route":
        invoke("lookup_dicomweb_transaction", {"name_or_route": ""})
    elif case_key == "unsupported.media_type.unknown_context":
        invoke(
            "lookup_media_type",
            {"media_type_or_context": "application/x-dicom-private"},
        )
    elif case_key == "unsupported.media_type.empty_context":
        invoke("lookup_media_type", {"media_type_or_context": ""})
    elif case_key == "unsupported.sr_template.unknown_tid":
        invoke("lookup_sr_template", {"tid_or_name": "999999"})
    elif case_key == "unsupported.sr_template.empty_tid":
        invoke("lookup_sr_template", {"tid_or_name": ""})
    elif case_key == "unsupported.context_group.unknown_cid":
        invoke("lookup_context_group", {"cid_or_name": "999999"})
    elif case_key == "unsupported.context_group.empty_cid":
        invoke("lookup_context_group", {"cid_or_name": ""})
    elif case_key == "unsupported.code_meaning.unknown_code":
        invoke("lookup_code_meaning", {"code_value": "ZZZ", "scheme": "DCM"})
    elif case_key == "unsupported.code_meaning.empty_scheme":
        invoke("lookup_code_meaning", {"code_value": "CT", "scheme": ""})
    elif case_key == "workflow.person_name_vr_defined_terms":
        invoke("lookup_vr", {"vr": "PN"})
        invoke("lookup_data_element", {"tag_or_keyword": "Patient's Name"})
        invoke("lookup_defined_terms", {"attribute": "Patient's Name"})
    elif case_key == "workflow.sequence_vr_encoding":
        invoke("lookup_vr", {"vr": "SQ"})
        invoke("explain_encoding_rule", {"topic": "SQ"})
    elif case_key == "workflow.ob_pixel_data_encoding":
        invoke("lookup_vr", {"vr": "OB"})
        invoke("lookup_data_element", {"tag_or_keyword": "(7FE0,0010)"})
    elif case_key == "workflow.un_vr_encoding":
        invoke("lookup_vr", {"vr": "UN"})
        invoke("explain_encoding_rule", {"topic": "UN"})
    elif case_key == "workflow.implicit_transfer_syntax_uid":
        uid = _uid_value("implicit_vr_little_endian")
        invoke("lookup_uid", {"uid_or_keyword": uid})
        invoke("lookup_transfer_syntax", {"uid_or_keyword": uid})
    elif case_key == "workflow.deflated_transfer_syntax_encoding":
        uid = _uid_value("deflated_explicit_vr_little_endian")
        invoke("lookup_uid", {"uid_or_keyword": uid})
        invoke("lookup_transfer_syntax", {"uid_or_keyword": uid})
    elif case_key == "workflow.big_endian_transfer_syntax_retired":
        uid = _uid_value("explicit_vr_big_endian")
        invoke("lookup_uid", {"uid_or_keyword": uid})
        invoke("lookup_transfer_syntax", {"uid_or_keyword": uid})
    elif case_key == "workflow.dicomweb_retrieve_media_type":
        invoke("lookup_dicomweb_transaction", {"name_or_route": "RetrieveStudy"})
        invoke("lookup_media_type", {"media_type_or_context": "WADO-RS response"})
    elif case_key == "workflow.dicomweb_store_media_type":
        invoke("lookup_dicomweb_transaction", {"name_or_route": "StoreInstances"})
        invoke("lookup_media_type", {"media_type_or_context": "STOW-RS request"})
    elif case_key == "workflow.dicomweb_ambiguous_route_candidates":
        invoke(
            "lookup_dicomweb_transaction",
            {"name_or_route": "/studies/{study}"},
        )
    elif case_key == "workflow.sr_template_context_group_code":
        invoke("lookup_sr_template", {"tid_or_name": "1500"})
        invoke("lookup_context_group", {"cid_or_name": "29"})
        invoke("lookup_code_meaning", {"code_value": "CT", "scheme": "DCM"})
    elif case_key == "workflow.media_file_preamble_fallback":
        invoke("lookup_media_type", {"media_type_or_context": "File Preamble"})
    else:
        raise ValueError(f"no reference v2 route for case: {case_id}")


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
    if tool == "lookup_vr":
        return lookup_vr(connection, vr=arguments["vr"], edition=edition)
    if tool == "lookup_transfer_syntax":
        return lookup_transfer_syntax(
            connection,
            uid_or_keyword=arguments["uid_or_keyword"],
            edition=edition,
        )
    if tool == "explain_encoding_rule":
        return explain_encoding_rule(
            connection,
            topic=arguments["topic"],
            edition=edition,
        )
    if tool == "lookup_media_type":
        return lookup_media_type(
            connection,
            media_type_or_context=arguments["media_type_or_context"],
            edition=edition,
        )
    if tool == "lookup_dicomweb_transaction":
        return lookup_dicomweb_transaction(
            connection,
            name_or_route=arguments["name_or_route"],
            edition=edition,
        )
    if tool == "lookup_sr_template":
        return lookup_sr_template(
            connection,
            tid_or_name=arguments["tid_or_name"],
            edition=edition,
        )
    if tool == "lookup_context_group":
        return lookup_context_group(
            connection,
            cid_or_name=arguments["cid_or_name"],
            edition=edition,
        )
    if tool == "lookup_code_meaning":
        return lookup_code_meaning(
            connection,
            code_value=arguments["code_value"],
            edition=edition,
            scheme=arguments.get("scheme"),
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
        response_parts=tuple(sorted({ref.part for ref in response.refs})),
        response_terms=_response_evidence_terms(response),
    )


def _ensure_source_reference(
    case: AgentRegressionCase,
    observed: list[ObservedToolCall],
    invoke: ToolInvoker,
) -> None:
    if _requires_own_cited_tool_evidence(case.id):
        return
    if any(
        call.response_status == "ok"
        and call.response_edition is not None
        and call.response_ref_count > 0
        for call in observed
    ):
        return
    invoke("lookup_data_element", {"tag_or_keyword": "Modality"})


def _requires_own_cited_tool_evidence(case_id: str) -> bool:
    return any(
        expected.required_status == "ok" and expected.required_parts
        for expected in EXPECTED_TOOL_TRACES.get(case_id, ())
    )


def _reference_answer(
    case: AgentRegressionCase,
    *,
    edition: str,
    tool_calls: tuple[ObservedToolCall, ...],
) -> str:
    statuses = ", ".join(
        sorted(
            {
                status.replace("_", " ")
                for call in tool_calls
                if (status := call.response_status) is not None
            }
        )
    )
    source_reference_text = (
        "source references and citations"
        if _run_has_source_references(tool_calls, edition=edition)
        else "recorded tool output"
    )
    warnings = (
        " warning" if any(call.response_status == "ok" for call in tool_calls) else ""
    )
    answer_terms = list(_answer_evidence_terms(tool_calls))
    if case.id == "agent.error.malformed_tag":
        answer_terms.append("validation")
    if case.id == "agent.v2.workflow.media_file_preamble_fallback":
        answer_terms.extend(("File Preamble", "fallback"))
    evidence_terms = " ".join(answer_terms)
    return (
        f"For edition {edition}, the reference agent used {source_reference_text}. "
        f"Tool statuses: {statuses}.{warnings} {evidence_terms}"
    )


def _run_has_source_references(
    tool_calls: tuple[ObservedToolCall, ...],
    *,
    edition: str,
) -> bool:
    return any(
        call.response_status == "ok"
        and call.response_edition == edition
        and call.response_ref_count > 0
        for call in tool_calls
    )


def _answer_evidence_terms(
    tool_calls: tuple[ObservedToolCall, ...],
) -> tuple[str, ...]:
    terms: list[str] = []
    for call in tool_calls:
        terms.extend(_tool_label_terms(call.tool))
        if call.tool in {"search_standard_text", "retrieve_standard_text"}:
            terms.extend(call.arguments.values())
        terms.extend(call.response_terms)
    return tuple(_dedupe_terms(terms))


def _response_evidence_terms(response: ToolResponse) -> tuple[str, ...]:
    terms: list[str] = []
    status = response.status.replace("_", " ")
    terms.append(status)
    if response.status != "ok":
        terms.append("unsupported")
        if response.status == "validation_error":
            terms.append("validation")
    terms.extend(ref.part for ref in response.refs)
    if response.result is not None:
        terms.extend(_payload_terms(response.result))
    return tuple(_dedupe_terms(terms))


def _payload_terms(payload: object) -> tuple[str, ...]:
    terms: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            label = key.replace("_", " ")
            terms.append(label)
            terms.extend(_combined_identifier_terms(key, value))
            terms.extend(_payload_terms(value))
    elif isinstance(payload, list | tuple):
        for value in payload:
            terms.extend(_payload_terms(value))
    elif isinstance(payload, str):
        text = " ".join(payload.split())
        if text:
            terms.append(text[:800])
    elif isinstance(payload, bool):
        terms.append("retired" if payload else "not retired")
    elif payload is not None:
        terms.append(str(payload))
    return tuple(terms)


def _combined_identifier_terms(key: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, str) or not value:
        return ()
    if key == "tid":
        return (f"TID {value}",)
    if key == "cid":
        return (f"CID {value}",)
    return ()


def _tool_label_terms(tool: str) -> tuple[str, ...]:
    normalized = tool.removeprefix("dicom_").replace("_", " ")
    terms = [normalized]
    if "dicomweb" in normalized:
        terms.append("DICOMweb")
    if "code" in normalized:
        terms.append("code")
    if "sr template" in normalized:
        terms.append("TID")
    if "context group" in normalized:
        terms.append("CID")
    return tuple(terms)


def _dedupe_terms(terms: list[str]) -> tuple[str, ...]:
    deduped: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = " ".join(term.split())
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return tuple(deduped)


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
