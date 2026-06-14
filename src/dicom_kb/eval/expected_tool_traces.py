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
}
