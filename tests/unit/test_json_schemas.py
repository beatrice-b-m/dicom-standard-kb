from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import BaseModel, ValidationError

from dicom_kb.query.answer_contracts import (
    CodeMeaningResult,
    ContextGroupResult,
    ContextGroupRowResult,
    DicomMediaTypeResult,
    DicomwebTransactionResult,
    EncodingRuleExplanationResult,
    ResponseStatus,
    SRTemplateResult,
    SRTemplateRowResult,
    StandardRef,
    ToolResponse,
    TransferSyntaxDetailResult,
    VRDefinitionResult,
    code_meaning_result,
    context_group_result,
    dicom_media_type_result,
    dicomweb_transaction_result,
    encoding_rule_explanation_result,
    sr_template_result,
    tool_response,
    transfer_syntax_detail_result,
    vr_definition_result,
)
from dicom_kb.sources.manifest import SourceArtifact, SourceManifest

SCHEMA_DIR = Path(__file__).parents[2] / "schemas"
SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _schema(name: str) -> dict[str, object]:
    path = SCHEMA_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_schema_def_matches_model(
    schema_def: dict[str, object], model: type[BaseModel]
) -> None:
    assert schema_def["additionalProperties"] is False
    assert set(schema_def["properties"]) == set(model.model_fields)
    assert schema_def["required"] == list(model.model_fields)


def test_required_schema_files_are_valid_json_objects() -> None:
    for name in {
        "condition.schema.json",
        "source_manifest.schema.json",
        "standard_ref.schema.json",
        "tool_response.schema.json",
    }:
        schema = _schema(name)

        assert schema["$schema"] == SCHEMA_DRAFT
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False


def test_standard_ref_schema_matches_public_contract_fields() -> None:
    schema = _schema("standard_ref.schema.json")

    assert set(schema["properties"]) == set(StandardRef.model_fields)
    assert schema["required"] == ["part", "edition"]


def test_tool_response_schema_matches_public_envelope_contract() -> None:
    schema = _schema("tool_response.schema.json")
    properties = schema["properties"]
    expected_required = [name for name in ToolResponse.model_fields if name != "notice"]

    assert set(properties) == set(ToolResponse.model_fields)
    assert properties["status"]["enum"] == list(get_args(ResponseStatus))
    assert properties["notice"]["type"] == ["string", "null"]
    assert schema["required"] == expected_required


def test_v2_payload_schema_matches_public_result_contracts() -> None:
    schema = _schema("v2_payloads.schema.json")
    defs = schema["$defs"]

    assert schema["$schema"] == SCHEMA_DRAFT
    assert schema["type"] == "object"
    assert schema["oneOf"] == [
        {"$ref": "#/$defs/vrDefinitionResult"},
        {"$ref": "#/$defs/transferSyntaxDetailResult"},
        {"$ref": "#/$defs/encodingRuleExplanationResult"},
        {"$ref": "#/$defs/dicomwebTransactionResult"},
        {"$ref": "#/$defs/dicomMediaTypeResult"},
        {"$ref": "#/$defs/srTemplateResult"},
        {"$ref": "#/$defs/contextGroupResult"},
        {"$ref": "#/$defs/codeMeaningResult"},
    ]

    expected_defs = {
        "vrDefinitionResult": VRDefinitionResult,
        "transferSyntaxDetailResult": TransferSyntaxDetailResult,
        "encodingRuleExplanationResult": EncodingRuleExplanationResult,
        "dicomwebTransactionResult": DicomwebTransactionResult,
        "dicomMediaTypeResult": DicomMediaTypeResult,
        "srTemplateResult": SRTemplateResult,
        "srTemplateRowResult": SRTemplateRowResult,
        "contextGroupResult": ContextGroupResult,
        "contextGroupRowResult": ContextGroupRowResult,
        "codeMeaningResult": CodeMeaningResult,
    }
    assert set(defs) == set(expected_defs)
    for name, model in expected_defs.items():
        _assert_schema_def_matches_model(defs[name], model)


def test_representative_v2_payloads_match_schema_required_fields() -> None:
    defs = _schema("v2_payloads.schema.json")["$defs"]
    representative_payloads = {
        "vrDefinitionResult": vr_definition_result(vr="PN", name="Person Name"),
        "transferSyntaxDetailResult": transfer_syntax_detail_result(
            uid_value="1.2.840.10008.1.2.1",
            uid_name="Explicit VR Little Endian",
            retired=False,
        ),
        "encodingRuleExplanationResult": encoding_rule_explanation_result(
            topic="padding",
            summary="Padding rules require cited text.",
        ),
        "dicomwebTransactionResult": dicomweb_transaction_result(
            transaction_name="RetrieveStudy",
            resource_category="study",
            http_method="GET",
            route_template="/studies/{studyInstanceUID}",
        ),
        "dicomMediaTypeResult": dicom_media_type_result(
            media_type="application/dicom",
        ),
        "srTemplateResult": sr_template_result(
            tid="TID 1500",
            name="Measurement Report",
            rows=[SRTemplateRowResult(order=1)],
        ),
        "contextGroupResult": context_group_result(
            cid="CID 29",
            name="Acquisition Modality",
            rows=[ContextGroupRowResult(order=1)],
        ),
        "codeMeaningResult": code_meaning_result(
            code_value="CT",
            coding_scheme_designator="DCM",
            code_meaning="Computed Tomography",
        ),
    }

    for schema_name, payload in representative_payloads.items():
        schema_def = defs[schema_name]
        assert set(payload) == set(schema_def["properties"])
        assert set(payload) == set(schema_def["required"])

    sr_rows = representative_payloads["srTemplateResult"]["rows"]
    assert set(sr_rows[0]) == set(defs["srTemplateRowResult"]["required"])
    context_group_rows = representative_payloads["contextGroupResult"]["rows"]
    assert set(context_group_rows[0]) == set(defs["contextGroupRowResult"]["required"])


def test_tool_response_requires_classification_metadata() -> None:
    with pytest.raises(ValidationError):
        ToolResponse(
            edition="2026b",
            tool="lookup_data_element",
            input={"tag_or_keyword": "Modality"},
            status="ok",
            result={"tag": "(0008,0060)"},
        )


def test_tool_response_factory_adds_deterministic_metadata() -> None:
    response = tool_response(
        edition="2026b",
        tool="lookup_data_element",
        input={"tag_or_keyword": "Modality"},
        status="ok",
        result={"tag": "(0008,0060)"},
    )

    assert response.classification.model_dump() == {
        "normativity": "normative",
        "evidence_level": "parsed_registry",
        "machine_decidability": "decidable",
    }
    assert response.parse_confidence.model_dump(exclude_none=True) == {
        "level": "high",
        "source": "parsed_registry",
    }
    assert response.notice is None


def test_v2_tool_response_classification_metadata() -> None:
    responses = [
        tool_response(
            edition="2026b",
            tool="lookup_vr",
            input={"vr": "PN"},
            status="ok",
            result=vr_definition_result(vr="PN", name="Person Name"),
        ),
        tool_response(
            edition="2026b",
            tool="lookup_transfer_syntax",
            input={"uid_or_keyword": "ExplicitVRLittleEndian"},
            status="ok",
            result=transfer_syntax_detail_result(
                uid_value="1.2.840.10008.1.2.1",
                uid_name="Explicit VR Little Endian",
                retired=False,
            ),
        ),
        tool_response(
            edition="2026b",
            tool="explain_encoding_rule",
            input={"topic": "padding"},
            status="ok",
            result=encoding_rule_explanation_result(
                topic="padding",
                summary="Padding is returned as cited explanatory text.",
            ),
        ),
    ]

    expected = {
        "lookup_vr": ("normative", "parsed_table", "decidable", "high"),
        "lookup_transfer_syntax": (
            "normative",
            "parsed_cross_reference",
            "decidable",
            "high",
        ),
        "explain_encoding_rule": (
            "explanatory",
            "retrieved_text",
            "not_applicable",
            "low",
        ),
    }
    for response in responses:
        normativity, evidence_level, machine_decidability, confidence = expected[
            response.tool
        ]
        assert response.classification.normativity == normativity
        assert response.classification.evidence_level == evidence_level
        assert response.classification.machine_decidability == machine_decidability
        assert response.parse_confidence.level == confidence
        assert response.parse_confidence.source == evidence_level


def test_v2_result_builders_return_concrete_payload_contracts() -> None:
    assert vr_definition_result(
        vr="PN",
        name="Person Name",
        value_representation_class="text",
        length_notes=["64 chars maximum per component group"],
        padding_behavior="space padded",
        character_repertoire_notes=["affected by Specific Character Set"],
        binary_or_text="text",
    ) == {
        "vr": "PN",
        "name": "Person Name",
        "value_representation_class": "text",
        "length_notes": ["64 chars maximum per component group"],
        "padding_behavior": "space padded",
        "character_repertoire_notes": ["affected by Specific Character Set"],
        "binary_or_text": "text",
    }
    assert transfer_syntax_detail_result(
        uid_value="1.2.840.10008.1.2.1",
        uid_name="Explicit VR Little Endian",
        uid_keyword="ExplicitVRLittleEndian",
        explicit_vr=True,
        endian="little",
        encapsulated=False,
        compression_family=None,
        retired=False,
        encoding_notes=["native pixel encoding"],
    ) == {
        "uid_value": "1.2.840.10008.1.2.1",
        "uid_name": "Explicit VR Little Endian",
        "uid_keyword": "ExplicitVRLittleEndian",
        "explicit_vr": True,
        "endian": "little",
        "encapsulated": False,
        "compression_family": None,
        "retired": False,
        "encoding_notes": ["native pixel encoding"],
    }
    assert encoding_rule_explanation_result(
        topic="undefined length sequence",
        summary="Sequences may use delimiter items when encoded with undefined length.",
        structured_facts=["SQ supports undefined length"],
        text_excerpt="Bounded cited excerpt.",
    ) == {
        "topic": "undefined length sequence",
        "summary": (
            "Sequences may use delimiter items when encoded with undefined length."
        ),
        "structured_facts": ["SQ supports undefined length"],
        "text_excerpt": "Bounded cited excerpt.",
    }
    assert dicomweb_transaction_result(
        transaction_name="RetrieveStudy",
        resource_category="study",
        http_method="GET",
        route_template="/studies/{studyInstanceUID}",
        request_constraints=["studyInstanceUID is required"],
        response_constraints=["returns matching instances"],
        status_codes=["200", "404"],
        media_type_refs=["multipart/related; type=application/dicom"],
    ) == {
        "transaction_name": "RetrieveStudy",
        "resource_category": "study",
        "http_method": "GET",
        "route_template": "/studies/{studyInstanceUID}",
        "request_constraints": ["studyInstanceUID is required"],
        "response_constraints": ["returns matching instances"],
        "status_codes": ["200", "404"],
        "media_type_refs": ["multipart/related; type=application/dicom"],
    }
    assert dicom_media_type_result(
        media_type="application/dicom",
        service_context="PS3.10 file",
        transfer_syntax_constraints=["single transfer syntax parameter"],
        directions=["request", "response"],
    ) == {
        "media_type": "application/dicom",
        "service_context": "PS3.10 file",
        "transfer_syntax_constraints": ["single transfer syntax parameter"],
        "directions": ["request", "response"],
    }
    assert sr_template_result(
        tid="TID 1500",
        name="Measurement Report",
        extensibility="EXTENSIBLE",
        rows=[
            SRTemplateRowResult(
                order=1,
                relationship_type="CONTAINS",
                value_type="CONTAINER",
                concept_name="Imaging Measurement Report",
                cardinality="1",
                condition=None,
                include_tid=None,
            )
        ],
    ) == {
        "tid": "TID 1500",
        "name": "Measurement Report",
        "extensibility": "EXTENSIBLE",
        "rows": [
            {
                "order": 1,
                "relationship_type": "CONTAINS",
                "value_type": "CONTAINER",
                "concept_name": "Imaging Measurement Report",
                "cardinality": "1",
                "condition": None,
                "include_tid": None,
            }
        ],
    }
    assert context_group_result(
        cid="CID 29",
        name="Acquisition Modality",
        extensibility="EXTENSIBLE",
        version="20260614",
        rows=[
            ContextGroupRowResult(
                order=1,
                coding_scheme_designator="DCM",
                coding_scheme_version=None,
                code_value="CT",
                code_meaning="Computed Tomography",
                include_cid=None,
            )
        ],
    ) == {
        "cid": "CID 29",
        "name": "Acquisition Modality",
        "extensibility": "EXTENSIBLE",
        "version": "20260614",
        "rows": [
            {
                "order": 1,
                "coding_scheme_designator": "DCM",
                "coding_scheme_version": None,
                "code_value": "CT",
                "code_meaning": "Computed Tomography",
                "include_cid": None,
            }
        ],
    }
    assert code_meaning_result(
        code_value="CT",
        coding_scheme_designator="DCM",
        coding_scheme_version=None,
        code_meaning="Computed Tomography",
        context_groups=["CID 29"],
    ) == {
        "code_value": "CT",
        "coding_scheme_designator": "DCM",
        "coding_scheme_version": None,
        "code_meaning": "Computed Tomography",
        "context_groups": ["CID 29"],
    }


def test_source_manifest_schema_matches_persisted_manifest_contract() -> None:
    schema = _schema("source_manifest.schema.json")
    artifact_schema = schema["$defs"]["sourceArtifact"]

    assert set(schema["properties"]) == set(SourceManifest.model_fields)
    assert schema["required"] == list(SourceManifest.model_fields)
    assert set(artifact_schema["properties"]) == set(SourceArtifact.model_fields)
    assert artifact_schema["required"] == list(SourceArtifact.model_fields)


def test_condition_schema_preserves_raw_text_until_machine_parsed() -> None:
    schema = _schema("condition.schema.json")
    properties = schema["properties"]

    assert properties["machine_status"]["enum"] == [
        "parsed",
        "partially_parsed",
        "raw_text",
        "not_machine_decidable",
    ]
    assert "source_text" in schema["required"]
    assert "evaluator" in schema["required"]
