"""Expected tool-call traces for committed agent regression cases."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExpectedToolCall(BaseModel):
    """A required tool call and any exact arguments the harness can verify."""

    model_config = ConfigDict(frozen=True)

    tool: str
    arguments: dict[str, str] = Field(default_factory=dict)


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
                "section_or_anchor": "sect_7_1",
                "max_chars": "800",
            },
        ),
    ),
    "agent.text.association_pdu_behavior": (
        ExpectedToolCall(
            tool="retrieve_standard_text",
            arguments={
                "part": "PS3.8",
                "section_or_anchor": "sect_8_1",
                "max_chars": "800",
            },
        ),
    ),
    "agent.v2.vr.person_name": (
        ExpectedToolCall(tool="lookup_vr", arguments={"vr": "PN"}),
    ),
    "agent.v2.transfer_syntax.explicit_little": (
        ExpectedToolCall(
            tool="lookup_transfer_syntax",
            arguments={"uid_or_keyword": "1.2.840.10008.1.2.1"},
        ),
    ),
    "agent.v2.encoding_rule.sequence": (
        ExpectedToolCall(
            tool="explain_encoding_rule",
            arguments={"topic": "SQ"},
        ),
    ),
    "agent.v2.media_type.dicom_file": (
        ExpectedToolCall(
            tool="lookup_media_type",
            arguments={"media_type_or_context": "application/dicom"},
        ),
    ),
    "agent.v2.dicomweb.retrieve_study": (
        ExpectedToolCall(
            tool="lookup_dicomweb_transaction",
            arguments={"name_or_route": "RetrieveStudy"},
        ),
    ),
    "agent.v2.sr_template.measurement_report": (
        ExpectedToolCall(
            tool="lookup_sr_template",
            arguments={"tid_or_name": "1500"},
        ),
    ),
    "agent.v2.context_group.acquisition_modality": (
        ExpectedToolCall(
            tool="lookup_context_group",
            arguments={"cid_or_name": "29"},
        ),
    ),
    "agent.v2.code_meaning.ct": (
        ExpectedToolCall(
            tool="lookup_code_meaning",
            arguments={"code_value": "CT", "scheme": "DCM"},
        ),
    ),
}
