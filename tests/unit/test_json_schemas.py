from __future__ import annotations

import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from dicom_kb.query.answer_contracts import (
    NOTICE,
    ResponseStatus,
    StandardRef,
    ToolResponse,
    tool_response,
)
from dicom_kb.sources.manifest import SourceArtifact, SourceManifest

SCHEMA_DIR = Path(__file__).parents[2] / "schemas"
SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _schema(name: str) -> dict[str, object]:
    path = SCHEMA_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


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

    assert set(properties) == set(ToolResponse.model_fields)
    assert properties["status"]["enum"] == list(get_args(ResponseStatus))
    assert properties["notice"]["const"] == NOTICE
    assert schema["required"] == list(ToolResponse.model_fields)


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
