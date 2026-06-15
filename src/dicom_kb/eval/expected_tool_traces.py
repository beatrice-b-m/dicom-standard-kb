"""Expected tool-call traces for committed agent regression cases."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExpectedToolCall(BaseModel):
    """A required tool call and any exact arguments the harness can verify."""

    model_config = ConfigDict(frozen=True)

    tool: str
    arguments: dict[str, str] = Field(default_factory=dict)
    required_status: str | None = None
    required_parts: tuple[str, ...] = ()


def cited_ok(
    tool: str,
    *,
    arguments: dict[str, str],
    required_parts: tuple[str, ...],
) -> ExpectedToolCall:
    """Declare a positive expected call that must return cited evidence."""
    return ExpectedToolCall(
        tool=tool,
        arguments=arguments,
        required_status="ok",
        required_parts=required_parts,
    )


EXPECTED_TOOL_TRACES: dict[str, tuple[ExpectedToolCall, ...]] = {
    "agent.ct.required_modules": (
        ExpectedToolCall(tool="lookup_iod", arguments={"iod_name": "CT Image"}),
        ExpectedToolCall(
            tool="list_modules_for_iod",
            arguments={"iod_name": "CT Image"},
        ),
    ),
    "agent.ct.modality_context": (
        ExpectedToolCall(
            tool="lookup_uid",
            arguments={"uid_or_keyword": "CTImageStorage"},
        ),
        ExpectedToolCall(
            tool="lookup_sop_class",
            arguments={"uid_or_name_or_keyword": "CT Image Storage"},
        ),
        ExpectedToolCall(
            tool="resolve_attribute_context",
            arguments={
                "attribute": "Modality",
                "sop_class": "CT Image Storage",
            },
        ),
    ),
    "agent.ps36.transfer_syntax": (
        ExpectedToolCall(
            tool="lookup_uid",
            arguments={"uid_or_keyword": "ExplicitVRBigEndian"},
        ),
    ),
    "agent.text.dimse_service_behavior": (
        ExpectedToolCall(
            tool="retrieve_standard_text",
            arguments={
                "part": "PS3.7",
                "section_or_anchor": "sect_7.1",
                "max_chars": "800",
            },
        ),
    ),
    "agent.text.association_pdu_behavior": (
        ExpectedToolCall(
            tool="retrieve_standard_text",
            arguments={
                "part": "PS3.8",
                "section_or_anchor": "sect_9.3",
                "max_chars": "800",
            },
        ),
    ),
    "agent.v2.vr.person_name": (
        cited_ok(
            "lookup_vr",
            arguments={"vr": "PN"},
            required_parts=("PS3.5",),
        ),
    ),
    "agent.v2.transfer_syntax.explicit_little": (
        cited_ok(
            "lookup_transfer_syntax",
            arguments={"uid_or_keyword": "1.2.840.10008.1.2.1"},
            required_parts=("PS3.6",),
        ),
    ),
    "agent.v2.encoding_rule.sequence": (
        cited_ok(
            "explain_encoding_rule",
            arguments={"topic": "SQ"},
            required_parts=("PS3.5",),
        ),
    ),
    "agent.v2.media_type.dicom_file": (
        cited_ok(
            "lookup_media_type",
            arguments={"media_type_or_context": "application/dicom"},
            required_parts=("PS3.10", "PS3.18"),
        ),
    ),
    "agent.v2.dicomweb.retrieve_study": (
        cited_ok(
            "lookup_dicomweb_transaction",
            arguments={"name_or_route": "RetrieveStudy"},
            required_parts=("PS3.18",),
        ),
    ),
    "agent.v2.sr_template.measurement_report": (
        cited_ok(
            "lookup_sr_template",
            arguments={"tid_or_name": "1500"},
            required_parts=("PS3.16",),
        ),
    ),
    "agent.v2.context_group.acquisition_modality": (
        cited_ok(
            "lookup_context_group",
            arguments={"cid_or_name": "29"},
            required_parts=("PS3.16",),
        ),
    ),
    "agent.v2.code_meaning.ct": (
        cited_ok(
            "lookup_code_meaning",
            arguments={"code_value": "CT", "scheme": "DCM"},
            required_parts=("PS3.16",),
        ),
    ),
    "agent.v2.unsupported.transfer_syntax.unknown_uid": (
        ExpectedToolCall(
            tool="lookup_transfer_syntax",
            arguments={"uid_or_keyword": "1.2.840.10008.999999"},
        ),
    ),
    "agent.v2.unsupported.transfer_syntax.malformed_uid": (
        ExpectedToolCall(
            tool="lookup_transfer_syntax",
            arguments={"uid_or_keyword": "1.2.840..10008"},
        ),
    ),
    "agent.v2.unsupported.dicomweb.unknown_transaction": (
        ExpectedToolCall(
            tool="lookup_dicomweb_transaction",
            arguments={"name_or_route": "BulkDeleteInstances"},
        ),
    ),
    "agent.v2.unsupported.dicomweb.empty_route": (
        ExpectedToolCall(
            tool="lookup_dicomweb_transaction",
            arguments={"name_or_route": ""},
        ),
    ),
    "agent.v2.unsupported.media_type.unknown_context": (
        ExpectedToolCall(
            tool="lookup_media_type",
            arguments={"media_type_or_context": "application/x-dicom-private"},
        ),
    ),
    "agent.v2.unsupported.media_type.empty_context": (
        ExpectedToolCall(
            tool="lookup_media_type",
            arguments={"media_type_or_context": ""},
        ),
    ),
    "agent.v2.unsupported.sr_template.unknown_tid": (
        ExpectedToolCall(
            tool="lookup_sr_template",
            arguments={"tid_or_name": "999999"},
        ),
    ),
    "agent.v2.unsupported.sr_template.empty_tid": (
        ExpectedToolCall(
            tool="lookup_sr_template",
            arguments={"tid_or_name": ""},
        ),
    ),
    "agent.v2.unsupported.context_group.unknown_cid": (
        ExpectedToolCall(
            tool="lookup_context_group",
            arguments={"cid_or_name": "999999"},
        ),
    ),
    "agent.v2.unsupported.context_group.empty_cid": (
        ExpectedToolCall(
            tool="lookup_context_group",
            arguments={"cid_or_name": ""},
        ),
    ),
    "agent.v2.unsupported.code_meaning.unknown_code": (
        ExpectedToolCall(
            tool="lookup_code_meaning",
            arguments={"code_value": "ZZZ", "scheme": "DCM"},
        ),
    ),
    "agent.v2.unsupported.code_meaning.empty_scheme": (
        ExpectedToolCall(
            tool="lookup_code_meaning",
            arguments={"code_value": "CT", "scheme": ""},
        ),
    ),
    "agent.v2.workflow.person_name_vr_defined_terms": (
        cited_ok(
            "lookup_vr",
            arguments={"vr": "PN"},
            required_parts=("PS3.5",),
        ),
        ExpectedToolCall(
            tool="lookup_data_element",
            arguments={"tag_or_keyword": "Patient's Name"},
        ),
        ExpectedToolCall(
            tool="lookup_defined_terms",
            arguments={"attribute": "Patient's Name"},
        ),
    ),
    "agent.v2.workflow.sequence_vr_encoding": (
        cited_ok(
            "lookup_vr",
            arguments={"vr": "SQ"},
            required_parts=("PS3.5",),
        ),
        cited_ok(
            "explain_encoding_rule",
            arguments={"topic": "SQ"},
            required_parts=("PS3.5",),
        ),
    ),
    "agent.v2.workflow.ob_pixel_data_encoding": (
        cited_ok(
            "lookup_vr",
            arguments={"vr": "OB"},
            required_parts=("PS3.5",),
        ),
        ExpectedToolCall(
            tool="lookup_data_element",
            arguments={"tag_or_keyword": "(7FE0,0010)"},
        ),
    ),
    "agent.v2.workflow.un_vr_encoding": (
        cited_ok(
            "lookup_vr",
            arguments={"vr": "UN"},
            required_parts=("PS3.5",),
        ),
        cited_ok(
            "explain_encoding_rule",
            arguments={"topic": "UN"},
            required_parts=("PS3.5",),
        ),
    ),
    "agent.v2.workflow.implicit_transfer_syntax_uid": (
        ExpectedToolCall(
            tool="lookup_uid",
            arguments={"uid_or_keyword": "1.2.840.10008.1.2"},
        ),
        cited_ok(
            "lookup_transfer_syntax",
            arguments={"uid_or_keyword": "1.2.840.10008.1.2"},
            required_parts=("PS3.6",),
        ),
    ),
    "agent.v2.workflow.deflated_transfer_syntax_encoding": (
        ExpectedToolCall(
            tool="lookup_uid",
            arguments={"uid_or_keyword": "1.2.840.10008.1.2.1.99"},
        ),
        cited_ok(
            "lookup_transfer_syntax",
            arguments={"uid_or_keyword": "1.2.840.10008.1.2.1.99"},
            required_parts=("PS3.6",),
        ),
    ),
    "agent.v2.workflow.big_endian_transfer_syntax_retired": (
        ExpectedToolCall(
            tool="lookup_uid",
            arguments={"uid_or_keyword": "1.2.840.10008.1.2.2"},
        ),
        cited_ok(
            "lookup_transfer_syntax",
            arguments={"uid_or_keyword": "1.2.840.10008.1.2.2"},
            required_parts=("PS3.6",),
        ),
    ),
    "agent.v2.workflow.dicomweb_retrieve_media_type": (
        cited_ok(
            "lookup_dicomweb_transaction",
            arguments={"name_or_route": "RetrieveStudy"},
            required_parts=("PS3.18",),
        ),
        cited_ok(
            "lookup_media_type",
            arguments={"media_type_or_context": "WADO-RS response"},
            required_parts=("PS3.18",),
        ),
    ),
    "agent.v2.workflow.dicomweb_store_media_type": (
        cited_ok(
            "lookup_dicomweb_transaction",
            arguments={"name_or_route": "StoreInstances"},
            required_parts=("PS3.18",),
        ),
        cited_ok(
            "lookup_media_type",
            arguments={"media_type_or_context": "STOW-RS request"},
            required_parts=("PS3.18",),
        ),
    ),
    "agent.v2.workflow.dicomweb_ambiguous_route_candidates": (
        ExpectedToolCall(
            tool="lookup_dicomweb_transaction",
            arguments={"name_or_route": "/studies/{study}"},
        ),
    ),
    "agent.v2.workflow.sr_template_context_group_code": (
        cited_ok(
            "lookup_sr_template",
            arguments={"tid_or_name": "1500"},
            required_parts=("PS3.16",),
        ),
        cited_ok(
            "lookup_context_group",
            arguments={"cid_or_name": "29"},
            required_parts=("PS3.16",),
        ),
        cited_ok(
            "lookup_code_meaning",
            arguments={"code_value": "CT", "scheme": "DCM"},
            required_parts=("PS3.16",),
        ),
    ),
    "agent.v2.workflow.media_file_preamble_fallback": (
        ExpectedToolCall(
            tool="lookup_media_type",
            arguments={"media_type_or_context": "File Preamble"},
        ),
    ),
}
