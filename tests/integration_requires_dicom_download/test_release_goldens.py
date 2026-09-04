from __future__ import annotations

import os
import sqlite3
from typing import Any

import pytest

from dicom_kb.query.answer_contracts import StandardRef, ToolResponse
from dicom_kb.query.resolver import (
    lookup_code_meaning,
    lookup_context_group,
    lookup_dicomweb_transaction,
    lookup_media_type,
    lookup_sr_template,
    lookup_vr,
)

pytestmark = [
    pytest.mark.dicom_release,
    pytest.mark.skipif(
        os.environ.get("DICOM_KB_RUN_RELEASE") != "1",
        reason="strict official release gate is opt-in via make test-dicom-release",
    ),
]


def test_release_golden_pn_vr(connection: sqlite3.Connection, edition: str) -> None:
    response = lookup_vr(connection, vr="PN", edition=edition)
    result = _strict_ok_result(response)

    assert result["vr"] == "PN"
    assert result["name"] == "Person Name"
    assert result["binary_or_text"]
    _assert_ref(response.refs, part="PS3.5")


def test_release_golden_application_dicom_media_type(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = lookup_media_type(
        connection,
        media_type_or_context="application/dicom",
        edition=edition,
    )
    result = _strict_ok_result(response)

    assert result["media_type"] == "application/dicom"
    assert result["transfer_syntax_constraints"]
    assert result["directions"]
    _assert_any_ref(response.refs, parts={"PS3.10", "PS3.18"})


def test_release_golden_retrieve_study_transaction(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = lookup_dicomweb_transaction(
        connection,
        name_or_route="RetrieveStudy",
        edition=edition,
    )
    result = _strict_ok_result(response)

    assert result["transaction_name"] == "RetrieveStudy"
    assert result["http_method"] == "GET"
    assert result["route_template"]
    assert result["resource_category"]
    assert result["request_constraints"]
    assert result["response_constraints"]
    _assert_ref(response.refs, part="PS3.18")


def test_release_golden_store_instances_transaction(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = lookup_dicomweb_transaction(
        connection,
        name_or_route="StoreInstances",
        edition=edition,
    )
    result = _strict_ok_result(response)

    assert result["transaction_name"] == "StoreInstances"
    assert result["http_method"] == "POST"
    assert result["route_template"]
    assert result["resource_category"]
    assert result["request_constraints"]
    assert result["response_constraints"]
    assert "multipart/related" in result["media_type_refs"]
    _assert_ref(response.refs, part="PS3.18")


def test_release_golden_wado_rs_response_media_type(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = lookup_media_type(
        connection,
        media_type_or_context="WADO-RS response",
        edition=edition,
    )
    result = _strict_ok_result(response)

    assert result["media_type"] == "multipart/related"
    assert result["service_context"] == "WADO-RS response"
    assert result["transfer_syntax_constraints"]
    assert result["directions"] == ["response"]
    _assert_ref(response.refs, part="PS3.18")


def test_release_golden_stow_rs_request_media_type(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = lookup_media_type(
        connection,
        media_type_or_context="STOW-RS request",
        edition=edition,
    )
    result = _strict_ok_result(response)

    assert result["media_type"] == "multipart/related"
    assert result["service_context"] == "STOW-RS request"
    assert result["transfer_syntax_constraints"]
    assert result["directions"] == ["request"]
    _assert_ref(response.refs, part="PS3.18")


def test_release_golden_tid_1500_template(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = lookup_sr_template(
        connection,
        tid_or_name="1500",
        edition=edition,
    )
    result = _strict_ok_result(response)

    assert result["tid"] == "TID 1500"
    assert result["name"] == "Measurement Report"
    assert result["extensibility"]
    assert result["rows"]
    _assert_ref(response.refs, part="PS3.16")


def test_release_golden_cid_29_context_group(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = lookup_context_group(
        connection,
        cid_or_name="29",
        edition=edition,
    )
    result = _strict_ok_result(response)

    assert result["cid"] == "CID 29"
    assert result["name"] == "Acquisition Modality"
    assert result["extensibility"]
    assert result["rows"]
    _assert_ref(response.refs, part="PS3.16")


def test_release_golden_ct_dcm_code_meaning(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = lookup_code_meaning(
        connection,
        code_value="CT",
        scheme="DCM",
        edition=edition,
    )
    result = _strict_ok_result(response)

    assert result["code_value"] == "CT"
    assert result["coding_scheme_designator"] == "DCM"
    assert result["code_meaning"] == "Computed Tomography"
    assert result["context_groups"]
    _assert_ref(response.refs, part="PS3.16")


def _strict_ok_result(response: ToolResponse) -> dict[str, Any]:
    assert response.status == "ok", response.model_dump(mode="json")
    assert response.result is not None
    assert response.refs
    return response.result


def _assert_ref(refs: list[StandardRef], *, part: str) -> None:
    assert any(ref.part == part for ref in refs), [
        ref.model_dump(mode="json") for ref in refs
    ]


def _assert_any_ref(refs: list[StandardRef], *, parts: set[str]) -> None:
    assert any(ref.part in parts for ref in refs), [
        ref.model_dump(mode="json") for ref in refs
    ]
