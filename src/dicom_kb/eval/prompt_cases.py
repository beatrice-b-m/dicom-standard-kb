"""Edition-pinned prompt cases for agent regression tests."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

EDITION = "2026b"
BASE_MUST_INCLUDE = ("edition", "source references")
BASE_MUST_NOT_INCLUDE = (
    "uncited normative claims",
    "official conformance certification",
)


class AgentRegressionCase(BaseModel):
    """A prompt and deterministic expectations for an agent answer."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition: str
    prompt: str
    expected_tools: tuple[str, ...]
    must_include: tuple[str, ...] = ()
    must_not_include: tuple[str, ...] = ()


# Golden entities and prompt facts are sourced from the real 2026b KB validated
# by tests/integration_requires_dicom_download/test_real_kb_goldens.py.
IODS = (
    "CT Image",
    "MR Image",
    "Enhanced CT Image",
    "Segmentation",
    "Comprehensive SR",
    "Encapsulated PDF",
)
MODULES = (
    "Patient",
    "General Study",
    "General Series",
    "Image Pixel",
    "SOP Common",
    "CT Image",
    "Contrast/Bolus",
)
DATA_ELEMENTS = (
    ("modality", "(0008,0060)", "Modality", "CS", "1"),
    ("sop_class_uid", "(0008,0016)", "SOP Class UID", "UI", "1"),
    ("sop_instance_uid", "(0008,0018)", "SOP Instance UID", "UI", "1"),
    ("pixel_data", "(7FE0,0010)", "Pixel Data", "OB or OW", "1"),
    ("transfer_syntax_uid", "(0002,0010)", "Transfer Syntax UID", "UI", "1"),
    ("patient_name", "(0010,0010)", "Patient's Name", "PN", "1"),
    ("study_instance_uid", "(0020,000D)", "Study Instance UID", "UI", "1"),
    ("series_instance_uid", "(0020,000E)", "Series Instance UID", "UI", "1"),
)
UIDS = (
    ("verification", "1.2.840.10008.1.1", "Verification SOP Class"),
    ("ct_storage", "1.2.840.10008.5.1.4.1.1.2", "CT Image Storage"),
    ("mr_storage", "1.2.840.10008.5.1.4.1.1.4", "MR Image Storage"),
    (
        "segmentation_storage",
        "1.2.840.10008.5.1.4.1.1.66.4",
        "Segmentation Storage",
    ),
    (
        "implicit_vr_little_endian",
        "1.2.840.10008.1.2",
        "Implicit VR Little Endian",
    ),
    (
        "explicit_vr_little_endian",
        "1.2.840.10008.1.2.1",
        "Explicit VR Little Endian",
    ),
    (
        "deflated_explicit_vr_little_endian",
        "1.2.840.10008.1.2.1.99",
        "Deflated Explicit VR Little Endian",
    ),
    (
        "explicit_vr_big_endian",
        "1.2.840.10008.1.2.2",
        "Explicit VR Big Endian",
    ),
)
SOP_CLASS_TO_IOD = (
    ("ct", "CT Image Storage", "CT Image"),
    ("mr", "MR Image Storage", "MR Image"),
    ("segmentation", "Segmentation Storage", "Segmentation"),
    ("encapsulated_pdf", "Encapsulated PDF Storage", "Encapsulated PDF"),
)
TEXT_RETRIEVAL_TARGETS = (
    ("ct_iod_table", "PS3.3", "table_A.3-1", "CT Image IOD modules"),
    ("mr_iod_table", "PS3.3", "table_A.4-1", "MR Image IOD modules"),
    ("general_series", "PS3.3", "table_C.7-5a", "General Series attributes"),
    ("data_elements", "PS3.6", "table_6-1", "data element registry"),
    ("uids", "PS3.6", "table_A-1", "UID registry"),
    ("dimse_service_behavior", "PS3.7", "sect_7_1", "DIMSE service behavior"),
    ("association_pdu_behavior", "PS3.8", "sect_8_1", "association PDU behavior"),
)
SEARCH_QUERIES = (
    ("ct_image", "CT Image IOD", "PS3.3"),
    ("modality", "Modality attribute", "PS3.3"),
    ("transfer_syntax", "Transfer Syntax UID", "PS3.6"),
    ("segmentation", "Segmentation Storage", "PS3.4"),
    ("patient_module", "Patient Module", "PS3.3"),
)
ERROR_CASES = (
    (
        "malformed_tag",
        "Explain why tag 0008-0060 is malformed before making any claim.",
        ("lookup_data_element",),
        ("validation",),
    ),
    (
        "unknown_tag",
        "Look up DICOM tag (9999,9999) and report the not-found result.",
        ("lookup_data_element",),
        ("not found",),
    ),
    (
        "range_overlay_tag",
        "Resolve overlay data tag (6002,3000) and include any range warning.",
        ("lookup_data_element",),
        ("warning",),
    ),
    (
        "malformed_uid",
        "Look up UID 1.2.840..10008 and explain the validation result.",
        ("lookup_uid",),
        ("validation",),
    ),
    (
        "unknown_uid",
        "Look up UID 1.2.840.10008.999999 and report the not-found result.",
        ("lookup_uid",),
        ("not found",),
    ),
    (
        "unknown_iod",
        "Try to resolve a Made Up Image IOD and say what the tool returned.",
        ("lookup_iod",),
        ("not found",),
    ),
    (
        "unknown_module",
        "Try to list attributes for Made Up Module and cite the tool result.",
        ("list_attributes_for_module",),
        ("not found",),
    ),
    (
        "invalid_context",
        "Resolve Modality without selecting an IOD or SOP Class context.",
        ("resolve_attribute_context",),
        ("validation",),
    ),
    (
        "invalid_retrieve_part",
        "Retrieve text from part DICOM-3 and explain the validation result.",
        ("retrieve_standard_text",),
        ("validation",),
    ),
    (
        "empty_search",
        "Search standard text with an empty query and report the validation result.",
        ("search_standard_text",),
        ("validation",),
    ),
)
V2_TOOL_CASES = (
    (
        "vr.person_name",
        "Look up the PN Value Representation and cite PS3.5.",
        ("lookup_vr",),
        ("PN", "Person Name", "PS3.5"),
    ),
    (
        "transfer_syntax.explicit_little",
        (
            "Look up Explicit VR Little Endian with parsed encoding details "
            "and citations."
        ),
        ("lookup_transfer_syntax",),
        ("Explicit VR Little Endian", "encoding", "PS3.6"),
    ),
    (
        "encoding_rule.sequence",
        "Explain the SQ encoding rule with deterministic PS3.5 evidence.",
        ("explain_encoding_rule",),
        ("SQ", "Sequence of Items", "PS3.5"),
    ),
    (
        "media_type.dicom_file",
        "Look up application/dicom media type constraints and cite the source.",
        ("lookup_media_type",),
        ("application/dicom", "PS3.10"),
    ),
    (
        "dicomweb.retrieve_study",
        "Look up the RetrieveStudy DICOMweb transaction and cite PS3.18.",
        ("lookup_dicomweb_transaction",),
        ("RetrieveStudy", "GET", "PS3.18"),
    ),
    (
        "sr_template.measurement_report",
        "Look up TID 1500 and summarize its SR template rows with citations.",
        ("lookup_sr_template",),
        ("TID 1500", "Measurement Report", "PS3.16"),
    ),
    (
        "context_group.acquisition_modality",
        "Look up CID 29 and summarize its coded rows with citations.",
        ("lookup_context_group",),
        ("CID 29", "Acquisition Modality", "PS3.16"),
    ),
    (
        "code_meaning.ct",
        "Look up code value CT in scheme DCM and cite its code meaning.",
        ("lookup_code_meaning",),
        ("CT", "Computed Tomography", "PS3.16"),
    ),
)
V2_UNSUPPORTED_CASES = (
    (
        "unsupported.transfer_syntax.unknown_uid",
        "transfer_syntax",
        (
            "Try transfer syntax UID 1.2.840.10008.999999 and avoid any "
            "encoding claim not supported by the tool result."
        ),
        ("lookup_transfer_syntax",),
        ("transfer syntax", "not found", "unsupported"),
    ),
    (
        "unsupported.transfer_syntax.malformed_uid",
        "transfer_syntax",
        (
            "Check malformed transfer syntax UID 1.2.840..10008 and report "
            "the validation result before making encoding claims."
        ),
        ("lookup_transfer_syntax",),
        ("transfer syntax", "validation", "unsupported"),
    ),
    (
        "unsupported.dicomweb.unknown_transaction",
        "dicomweb",
        (
            "Try to look up a BulkDeleteInstances DICOMweb transaction and "
            "withhold route or method claims when the tool cannot support them."
        ),
        ("lookup_dicomweb_transaction",),
        ("DICOMweb", "not found", "unsupported"),
    ),
    (
        "unsupported.dicomweb.empty_route",
        "dicomweb",
        (
            "Validate an empty DICOMweb transaction query and do not invent a "
            "route template."
        ),
        ("lookup_dicomweb_transaction",),
        ("DICOMweb", "validation", "unsupported"),
    ),
    (
        "unsupported.media_type.unknown_context",
        "media_type",
        (
            "Try media type application/x-dicom-private and avoid unsupported "
            "request or response constraints."
        ),
        ("lookup_media_type",),
        ("media type", "not found", "unsupported"),
    ),
    (
        "unsupported.media_type.empty_context",
        "media_type",
        (
            "Validate an empty media-type lookup and report why no media "
            "constraints can be claimed."
        ),
        ("lookup_media_type",),
        ("media type", "validation", "unsupported"),
    ),
    (
        "unsupported.sr_template.unknown_tid",
        "tid",
        (
            "Try to look up TID 999999 and do not invent SR template rows."
        ),
        ("lookup_sr_template",),
        ("TID", "not found", "unsupported"),
    ),
    (
        "unsupported.sr_template.empty_tid",
        "tid",
        "Validate an empty TID lookup before making SR template claims.",
        ("lookup_sr_template",),
        ("TID", "validation", "unsupported"),
    ),
    (
        "unsupported.context_group.unknown_cid",
        "cid",
        (
            "Try to look up CID 999999 and do not invent context-group code "
            "rows."
        ),
        ("lookup_context_group",),
        ("CID", "not found", "unsupported"),
    ),
    (
        "unsupported.context_group.empty_cid",
        "cid",
        "Validate an empty CID lookup before making context-group claims.",
        ("lookup_context_group",),
        ("CID", "validation", "unsupported"),
    ),
    (
        "unsupported.code_meaning.unknown_code",
        "code_lookup",
        (
            "Try code value ZZZ in scheme DCM and avoid unsupported code "
            "meaning claims."
        ),
        ("lookup_code_meaning",),
        ("code", "not found", "unsupported"),
    ),
    (
        "unsupported.code_meaning.empty_scheme",
        "code_lookup",
        (
            "Validate code value CT with an empty scheme parameter and report "
            "the tool result before claiming a meaning."
        ),
        ("lookup_code_meaning",),
        ("code", "validation", "unsupported"),
    ),
)

def get_agent_regression_case(case_id: str) -> AgentRegressionCase:
    """Return a committed agent regression case by id."""
    for case in AGENT_REGRESSION_CASES:
        if case.id == case_id:
            return case
    raise KeyError(f"unknown agent regression case: {case_id}")


def _case(
    case_id: str,
    prompt: str,
    expected_tools: tuple[str, ...],
    must_include: tuple[str, ...] = (),
    must_not_include: tuple[str, ...] = BASE_MUST_NOT_INCLUDE,
) -> AgentRegressionCase:
    return AgentRegressionCase(
        id=case_id,
        edition=EDITION,
        prompt=prompt,
        expected_tools=expected_tools,
        must_include=BASE_MUST_INCLUDE + must_include,
        must_not_include=must_not_include,
    )


def _slug(value: str) -> str:
    return (
        value.casefold()
        .replace("/", "_")
        .replace("-", "_")
        .replace(" ", "_")
        .replace("'", "")
    )


def _iod_cases() -> tuple[AgentRegressionCase, ...]:
    return tuple(
        _case(
            f"agent.iod.{_slug(iod)}.modules",
            f"Resolve the {iod} IOD and summarize its Patient and SOP Common modules.",
            ("lookup_iod", "list_modules_for_iod"),
            ("module usage", iod),
        )
        for iod in IODS
        if iod != "CT Image"
    )


def _module_cases() -> tuple[AgentRegressionCase, ...]:
    return tuple(
        _case(
            f"agent.module.{_slug(module)}.attributes",
            f"List key attributes for the {module} module with citations.",
            ("list_attributes_for_module",),
            (module,),
        )
        for module in MODULES
    )


def _data_element_cases() -> tuple[AgentRegressionCase, ...]:
    return tuple(
        _case(
            f"agent.data_element.{case_id}",
            f"Look up {name} {tag}; include VR {vr}, VM {vm}, and a citation.",
            ("lookup_data_element",),
            (name, vr, vm),
        )
        for case_id, tag, name, vr, vm in DATA_ELEMENTS
    )


def _uid_cases() -> tuple[AgentRegressionCase, ...]:
    return tuple(
        _case(
            f"agent.uid.{case_id}",
            f"Look up {name} ({uid}) and cite the UID registry.",
            ("lookup_uid",),
            (name,),
        )
        for case_id, uid, name in UIDS
        if case_id != "explicit_vr_big_endian"
    )


def _sop_class_cases() -> tuple[AgentRegressionCase, ...]:
    return tuple(
        _case(
            f"agent.sop_class.{case_id}.iod",
            f"Resolve {sop_class} to its IOD and cite PS3.4 and PS3.3.",
            ("lookup_uid", "lookup_sop_class"),
            (sop_class, iod),
        )
        for case_id, sop_class, iod in SOP_CLASS_TO_IOD
    )


def _attribute_context_cases() -> tuple[AgentRegressionCase, ...]:
    contexts = (
        ("ct_modality", "Modality", "CT Image"),
        ("mr_modality", "Modality", "MR Image"),
        ("ct_sop_class_uid", "SOP Class UID", "CT Image"),
        ("mr_sop_instance_uid", "SOP Instance UID", "MR Image"),
        ("ct_pixel_data", "Pixel Data", "CT Image"),
        ("general_series_modality", "(0008,0060)", "MR Image"),
    )
    return tuple(
        _case(
            f"agent.context.{case_id}",
            f"Resolve {attribute} usage in the {iod} IOD with citations.",
            ("lookup_data_element", "lookup_iod", "resolve_attribute_context"),
            (attribute, iod),
        )
        for case_id, attribute, iod in contexts
    )


def _value_term_cases() -> tuple[AgentRegressionCase, ...]:
    return (
        _case(
            "agent.values.modality.enumerated",
            "Look up parsed enumerated values for Modality and cite the source.",
            ("lookup_data_element", "lookup_enumerated_values"),
            ("Modality", "enumerated values"),
        ),
        _case(
            "agent.values.patient_name.defined",
            "Look up parsed defined terms for Patient's Name and cite the source.",
            ("lookup_data_element", "lookup_defined_terms"),
            ("Patient's Name", "defined terms"),
        ),
    )


def _text_retrieval_cases() -> tuple[AgentRegressionCase, ...]:
    return tuple(
        _case(
            f"agent.text.{case_id}",
            f"Retrieve the standard text for {label} and cite the source ref.",
            ("retrieve_standard_text",),
            (part, label),
        )
        for case_id, part, _anchor, label in TEXT_RETRIEVAL_TARGETS
    )


def _search_cases() -> tuple[AgentRegressionCase, ...]:
    return tuple(
        _case(
            f"agent.search.{case_id}",
            f"Search {part} for {query} and summarize the cited matches.",
            ("search_standard_text",),
            (part, query),
        )
        for case_id, query, part in SEARCH_QUERIES
    )


def _workflow_cases() -> tuple[AgentRegressionCase, ...]:
    return (
        _case(
            "agent.workflow.ct_storage_to_pixel_data",
            (
                "Starting from CT Image Storage, identify the IOD, list modules, "
                "then resolve Pixel Data usage."
            ),
            (
                "lookup_uid",
                "lookup_sop_class",
                "list_modules_for_iod",
                "resolve_attribute_context",
            ),
            ("CT Image Storage", "Pixel Data", "module usage"),
        ),
        _case(
            "agent.workflow.segmentation_storage_to_modules",
            (
                "Starting from Segmentation Storage, identify the IOD and list "
                "Patient and SOP Common module usage."
            ),
            ("lookup_uid", "lookup_sop_class", "list_modules_for_iod"),
            ("Segmentation Storage", "module usage"),
        ),
        _case(
            "agent.workflow.mr_modality_dictionary_context",
            (
                "For MR Image Storage, look up Modality in PS3.6 and resolve "
                "its MR Image IOD context."
            ),
            (
                "lookup_uid",
                "lookup_sop_class",
                "lookup_data_element",
                "resolve_attribute_context",
            ),
            ("MR Image Storage", "Modality"),
        ),
        _case(
            "agent.workflow.encapsulated_pdf_modules_text",
            (
                "Resolve Encapsulated PDF Storage to an IOD, list its modules, "
                "and retrieve the Encapsulated PDF IOD table text."
            ),
            (
                "lookup_uid",
                "lookup_sop_class",
                "list_modules_for_iod",
                "retrieve_standard_text",
            ),
            ("Encapsulated PDF", "module usage"),
        ),
        _case(
            "agent.workflow.transfer_syntax_search",
            (
                "Look up Explicit VR Little Endian and search the standard text "
                "for Transfer Syntax UID references."
            ),
            ("lookup_uid", "search_standard_text"),
            ("Explicit VR Little Endian", "Transfer Syntax UID"),
        ),
    )


def _v2_tool_cases() -> tuple[AgentRegressionCase, ...]:
    return tuple(
        _case(
            f"agent.v2.{case_id}",
            prompt,
            tools,
            must_include,
        )
        for case_id, prompt, tools, must_include in V2_TOOL_CASES
    )


def _v2_unsupported_cases() -> tuple[AgentRegressionCase, ...]:
    return tuple(
        _case(
            f"agent.v2.{case_id}",
            prompt,
            tools,
            must_include,
        )
        for case_id, _domain, prompt, tools, must_include in V2_UNSUPPORTED_CASES
    )


def _error_cases() -> tuple[AgentRegressionCase, ...]:
    return tuple(
        _case(
            f"agent.error.{case_id}",
            prompt,
            tools,
            must_include,
        )
        for case_id, prompt, tools, must_include in ERROR_CASES
    )


def _agent_regression_cases() -> tuple[AgentRegressionCase, ...]:
    return (
        _case(
            "agent.ct.required_modules",
            "List the required modules for CT Image IOD and cite the standard.",
            ("lookup_iod", "list_modules_for_iod"),
            ("module usage",),
        ),
        _case(
            "agent.ct.modality_context",
            (
                "For CT Image Storage, explain the Modality attribute usage "
                "and cite the standard."
            ),
            ("lookup_uid", "lookup_sop_class", "resolve_attribute_context"),
            ("Modality",),
        ),
        _case(
            "agent.ps36.transfer_syntax",
            (
                "Look up Explicit VR Big Endian and say whether it is retired, "
                "with a citation."
            ),
            ("lookup_uid",),
            ("retired",),
        ),
        *_iod_cases(),
        *_module_cases(),
        *_data_element_cases(),
        *_uid_cases(),
        *_sop_class_cases(),
        *_attribute_context_cases(),
        *_value_term_cases(),
        *_text_retrieval_cases(),
        *_search_cases(),
        *_workflow_cases(),
        *_v2_tool_cases(),
        *_v2_unsupported_cases(),
        *_error_cases(),
    )


AGENT_REGRESSION_CASES: tuple[AgentRegressionCase, ...] = _agent_regression_cases()
