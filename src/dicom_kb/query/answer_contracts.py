"""Public response contracts shared by CLI and future agent tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from dicom_kb.ir.models import (
    DocNode,
    SourceRef,
    UIDRegistryEntry,
)

ResponseStatus = Literal["ok", "not_found", "validation_error"]


class StandardRef(BaseModel):
    """Where in the standard a fact comes from."""

    model_config = ConfigDict(frozen=True)

    part: str
    section: str | None = None
    table: str | None = None
    anchor: str | None = None
    edition: str
    # How the source line names it, when the id alone would read badly.
    label: str | None = None


class ToolResponse(BaseModel):
    """A resolver's answer: the result, its sources, and real gaps only."""

    model_config = ConfigDict(frozen=True)

    status: ResponseStatus
    result: dict[str, Any] | None
    refs: list[StandardRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class VRDefinitionResult(BaseModel):
    """V2 payload for a parsed PS3.5 value representation definition."""

    model_config = ConfigDict(frozen=True)

    vr: str
    name: str
    value_representation_class: str | None = None
    length_notes: list[str] = Field(default_factory=list)
    padding_behavior: str | None = None
    character_repertoire_notes: list[str] = Field(default_factory=list)
    binary_or_text: str | None = None


class TransferSyntaxDetailResult(BaseModel):
    """V2 payload combining PS3.6 UID metadata with PS3.5 encoding facts."""

    model_config = ConfigDict(frozen=True)

    uid_value: str
    uid_name: str
    uid_keyword: str | None = None
    explicit_vr: bool | None = None
    endian: str | None = None
    encapsulated: bool | None = None
    compression_family: str | None = None
    retired: bool
    encoding_notes: list[str] = Field(default_factory=list)


class EncodingRuleExplanationResult(BaseModel):
    """V2 payload for a bounded, cited encoding-rule explanation."""

    model_config = ConfigDict(frozen=True)

    topic: str
    summary: str
    structured_facts: list[str] = Field(default_factory=list)
    text_excerpt: str | None = None


class DicomwebTransactionResult(BaseModel):
    """V2 payload for a parsed PS3.18 DICOMweb transaction."""

    model_config = ConfigDict(frozen=True)

    transaction_name: str
    resource_category: str
    http_method: str
    route_template: str
    request_constraints: list[str] = Field(default_factory=list)
    response_constraints: list[str] = Field(default_factory=list)
    status_codes: list[str] = Field(default_factory=list)
    media_type_refs: list[str] = Field(default_factory=list)


class DicomMediaTypeResult(BaseModel):
    """V2 payload for PS3.10/PS3.18 media-type semantics."""

    model_config = ConfigDict(frozen=True)

    media_type: str
    service_context: str | None = None
    transfer_syntax_constraints: list[str] = Field(default_factory=list)
    directions: list[str] = Field(default_factory=list)


def tool_response(
    *,
    status: ResponseStatus,
    result: dict[str, Any] | None,
    refs: list[StandardRef] | None = None,
    warnings: list[str] | None = None,
) -> ToolResponse:
    """Build a resolver response."""
    return ToolResponse(
        status=status,
        result=result,
        refs=refs or [],
        warnings=warnings or [],
    )


def uid_result(uid: UIDRegistryEntry) -> dict[str, Any]:
    """Return the public result payload for a UID registry entry."""
    return {
        "uid_value": uid.uid_value,
        "uid_name": uid.uid_name,
        "uid_keyword": uid.uid_keyword,
        "uid_type": uid.uid_type,
        "part": uid.part,
        "retired": uid.retired,
    }


def vr_definition_result(
    *,
    vr: str,
    name: str,
    value_representation_class: str | None = None,
    length_notes: list[str] | None = None,
    padding_behavior: str | None = None,
    character_repertoire_notes: list[str] | None = None,
    binary_or_text: str | None = None,
) -> dict[str, Any]:
    """Return the public v2 result payload for a PS3.5 VR definition."""
    return VRDefinitionResult(
        vr=vr,
        name=name,
        value_representation_class=value_representation_class,
        length_notes=length_notes or [],
        padding_behavior=padding_behavior,
        character_repertoire_notes=character_repertoire_notes or [],
        binary_or_text=binary_or_text,
    ).model_dump(mode="json")


def transfer_syntax_detail_result(
    *,
    uid_value: str,
    uid_name: str,
    retired: bool,
    uid_keyword: str | None = None,
    explicit_vr: bool | None = None,
    endian: str | None = None,
    encapsulated: bool | None = None,
    compression_family: str | None = None,
    encoding_notes: list[str] | None = None,
) -> dict[str, Any]:
    """Return the public v2 result payload for transfer-syntax details."""
    return TransferSyntaxDetailResult(
        uid_value=uid_value,
        uid_name=uid_name,
        uid_keyword=uid_keyword,
        explicit_vr=explicit_vr,
        endian=endian,
        encapsulated=encapsulated,
        compression_family=compression_family,
        retired=retired,
        encoding_notes=encoding_notes or [],
    ).model_dump(mode="json")


def encoding_rule_explanation_result(
    *,
    topic: str,
    summary: str,
    structured_facts: list[str] | None = None,
    text_excerpt: str | None = None,
) -> dict[str, Any]:
    """Return the public v2 result payload for an encoding-rule explanation."""
    return EncodingRuleExplanationResult(
        topic=topic,
        summary=summary,
        structured_facts=structured_facts or [],
        text_excerpt=text_excerpt,
    ).model_dump(mode="json")


def dicomweb_transaction_result(
    *,
    transaction_name: str,
    resource_category: str,
    http_method: str,
    route_template: str,
    request_constraints: list[str] | None = None,
    response_constraints: list[str] | None = None,
    status_codes: list[str] | None = None,
    media_type_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Return the public v2 result payload for a DICOMweb transaction."""
    return DicomwebTransactionResult(
        transaction_name=transaction_name,
        resource_category=resource_category,
        http_method=http_method,
        route_template=route_template,
        request_constraints=request_constraints or [],
        response_constraints=response_constraints or [],
        status_codes=status_codes or [],
        media_type_refs=media_type_refs or [],
    ).model_dump(mode="json")


def dicom_media_type_result(
    *,
    media_type: str,
    service_context: str | None = None,
    transfer_syntax_constraints: list[str] | None = None,
    directions: list[str] | None = None,
) -> dict[str, Any]:
    """Return the public v2 result payload for DICOM media-type semantics."""
    return DicomMediaTypeResult(
        media_type=media_type,
        service_context=service_context,
        transfer_syntax_constraints=transfer_syntax_constraints or [],
        directions=directions or [],
    ).model_dump(mode="json")


def standard_text_result(
    node: DocNode,
    tables: list[DocNode],
    *,
    text_excerpt: str,
) -> dict[str, Any]:
    """Return the public result payload for a short standard text excerpt."""
    return {
        "part": node.part,
        "section": node.xml_id or node.number,
        "title": node.title,
        "text_excerpt": text_excerpt,
        "tables": [
            {
                "table_id": table.xml_id,
                "title": table.title,
            }
            for table in tables
        ],
    }


def standard_ref(source_ref: SourceRef) -> StandardRef:
    """Convert an internal source ref to the public citation shape."""
    return StandardRef(
        part=source_ref.part,
        section=source_ref.section,
        table=source_ref.title or source_ref.table_id,
        anchor=source_ref.xml_id,
        edition=source_ref.edition_id,
    )
