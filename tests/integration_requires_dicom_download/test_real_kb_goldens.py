from __future__ import annotations

import json
import sqlite3
from typing import Any

import pytest

from dicom_kb.query.answer_contracts import StandardRef, ToolResponse
from dicom_kb.query.resolver import (
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
)

# Expected values below were derived from the locally built official KB and
# are guarded by source refs in the response envelopes, e.g. PS3.6 table_6-1,
# PS3.6 table_A-1, and the relevant PS3.3 IOD/module table anchors.
DATA_ELEMENT_GOLDENS = {
    "(0008,0060)": ("Modality", "Modality", "CS", "1", "table_6-1"),
    "(0008,0016)": ("SOP Class UID", "SOPClassUID", "UI", "1", "table_6-1"),
    "(0008,0018)": ("SOP Instance UID", "SOPInstanceUID", "UI", "1", "table_6-1"),
    "(7FE0,0010)": ("Pixel Data", "PixelData", "OB or OW", "1", "table_6-1"),
    "(0002,0010)": (
        "Transfer Syntax UID",
        "TransferSyntaxUID",
        "UI",
        "1",
        "table_7-1",
    ),
    "(0010,0010)": ("Patient's Name", "PatientName", "PN", "1", "table_6-1"),
    "(0020,000D)": (
        "Study Instance UID",
        "StudyInstanceUID",
        "UI",
        "1",
        "table_6-1",
    ),
    "(0020,000E)": (
        "Series Instance UID",
        "SeriesInstanceUID",
        "UI",
        "1",
        "table_6-1",
    ),
}

UID_GOLDENS = {
    "1.2.840.10008.1.1": (
        "Verification SOP Class",
        "Verification",
        "SOP Class",
        False,
    ),
    "1.2.840.10008.5.1.4.1.1.2": (
        "CT Image Storage",
        "CTImageStorage",
        "SOP Class",
        False,
    ),
    "1.2.840.10008.5.1.4.1.1.4": (
        "MR Image Storage",
        "MRImageStorage",
        "SOP Class",
        False,
    ),
    "1.2.840.10008.5.1.4.1.1.66.4": (
        "Segmentation Storage",
        "SegmentationStorage",
        "SOP Class",
        False,
    ),
    "1.2.840.10008.1.2": (
        "Implicit VR Little Endian: Default Transfer Syntax for DICOM",
        "ImplicitVRLittleEndian",
        "Transfer Syntax",
        False,
    ),
    "1.2.840.10008.1.2.1": (
        "Explicit VR Little Endian",
        "ExplicitVRLittleEndian",
        "Transfer Syntax",
        False,
    ),
    "1.2.840.10008.1.2.1.99": (
        "Deflated Explicit VR Little Endian",
        "DeflatedExplicitVRLittleEndian",
        "Transfer Syntax",
        False,
    ),
    "1.2.840.10008.1.2.2": (
        "Explicit VR Big Endian",
        "ExplicitVRBigEndian",
        "Transfer Syntax",
        True,
    ),
}

TRANSFER_SYNTAX_GOLDENS = {
    "1.2.840.10008.1.2": {
        "uid_name": "Implicit VR Little Endian: Default Transfer Syntax for DICOM",
        "uid_keyword": "ImplicitVRLittleEndian",
        "explicit_vr": False,
        "endian": "little",
        "encapsulated": False,
        "compression_family": None,
        "retired": False,
        "encoding_notes": [],
    },
    "1.2.840.10008.1.2.1": {
        "uid_name": "Explicit VR Little Endian",
        "uid_keyword": "ExplicitVRLittleEndian",
        "explicit_vr": True,
        "endian": "little",
        "encapsulated": False,
        "compression_family": None,
        "retired": False,
        "encoding_notes": [],
    },
    "1.2.840.10008.1.2.1.99": {
        "uid_name": "Deflated Explicit VR Little Endian",
        "uid_keyword": "DeflatedExplicitVRLittleEndian",
        "explicit_vr": True,
        "endian": "little",
        "encapsulated": False,
        "compression_family": "deflated",
        "retired": False,
        "encoding_notes": ["deflated dataset encoding"],
    },
    "1.2.840.10008.1.2.4.50": {
        "uid_name": (
            "JPEG Baseline (Process 1): Default Transfer Syntax for Lossy JPEG "
            "8 Bit Image Compression"
        ),
        "uid_keyword": "JPEGBaseline8Bit",
        "explicit_vr": None,
        "endian": None,
        "encapsulated": True,
        "compression_family": "jpeg",
        "retired": False,
        "encoding_notes": [
            "jpeg compressed transfer syntax",
            "encapsulated pixel data",
        ],
    },
}

IOD_GOLDENS = [
    "CT Image",
    "MR Image",
    "Enhanced CT Image",
    "Segmentation",
    "Comprehensive SR",
    "Encapsulated PDF",
]

MODULE_GOLDENS = [
    "Patient",
    "General Study",
    "General Series",
    "Image Pixel",
    "SOP Common",
    "CT Image",
    "Contrast/Bolus",
]


@pytest.mark.parametrize(
    ("tag", "expected"),
    DATA_ELEMENT_GOLDENS.items(),
    ids=DATA_ELEMENT_GOLDENS.keys(),
)
def test_real_kb_data_element_goldens(
    connection: sqlite3.Connection,
    edition: str,
    tag: str,
    expected: tuple[str, str, str, str, str],
) -> None:
    response = lookup_data_element(connection, tag_or_keyword=tag, edition=edition)
    result = _ok_result(response)

    name, keyword, vr, vm, anchor = expected
    assert result["tag"] == tag
    assert result["name"] == name
    assert result["keyword"] == keyword
    assert result["vr"] == vr
    assert result["vm"] == vm
    assert result["retired"] is False
    _assert_ref(response.refs, part="PS3.6", anchor=anchor)


@pytest.mark.parametrize(
    ("uid", "expected"),
    UID_GOLDENS.items(),
    ids=UID_GOLDENS.keys(),
)
def test_real_kb_uid_goldens(
    connection: sqlite3.Connection,
    edition: str,
    uid: str,
    expected: tuple[str, str, str, bool],
) -> None:
    response = lookup_uid(connection, uid_or_keyword=uid, edition=edition)
    result = _ok_result(response)

    name, keyword, uid_type, retired = expected
    assert result["uid_value"] == uid
    assert result["uid_name"] == name
    assert result["uid_keyword"] == keyword
    assert result["uid_type"] == uid_type
    assert result["retired"] is retired
    _assert_ref(response.refs, part="PS3.6", anchor="table_A-1")


@pytest.mark.parametrize(
    ("uid", "expected"),
    TRANSFER_SYNTAX_GOLDENS.items(),
    ids=TRANSFER_SYNTAX_GOLDENS.keys(),
)
def test_real_kb_transfer_syntax_encoding_goldens(
    connection: sqlite3.Connection,
    edition: str,
    uid: str,
    expected: dict[str, object],
) -> None:
    _require_phase2_encoding_rows(connection, edition)

    response = lookup_transfer_syntax(connection, uid_or_keyword=uid, edition=edition)
    result = _ok_result(response)

    assert result == {"uid_value": uid, **expected}
    _assert_ref(response.refs, part="PS3.6", anchor="table_A-1")


def test_real_kb_vr_definition_golden(
    connection: sqlite3.Connection, edition: str
) -> None:
    expected = _require_vr_definition(connection, edition, vr="PN")

    response = lookup_vr(connection, vr="PN", edition=edition)
    result = _ok_result(response)

    assert result["vr"] == "PN"
    assert result["name"] == expected["name"]
    assert result["binary_or_text"] == expected["binary_or_text"]
    _assert_ref(response.refs, part="PS3.5")


def test_real_kb_ps310_media_type_golden(
    connection: sqlite3.Connection, edition: str
) -> None:
    expected = _require_unique_media_type(connection, edition, source_part="PS3.10")

    response = lookup_media_type(
        connection,
        media_type_or_context=str(expected["service_context"]),
        edition=edition,
    )
    result = _ok_result(response)

    assert result == {
        "media_type": expected["media_type"],
        "service_context": expected["service_context"],
        "transfer_syntax_constraints": json.loads(
            expected["transfer_syntax_constraints_json"]
        ),
        "directions": json.loads(expected["directions_json"]),
    }
    _assert_ref(response.refs, part="PS3.10")


def test_real_kb_ps318_transaction_golden(
    connection: sqlite3.Connection, edition: str
) -> None:
    expected = _require_unique_dicomweb_transaction(connection, edition)

    response = lookup_dicomweb_transaction(
        connection,
        name_or_route=str(expected["transaction_name"]),
        edition=edition,
    )
    result = _ok_result(response)

    assert result == {
        "transaction_name": expected["transaction_name"],
        "resource_category": expected["resource_category"],
        "http_method": expected["http_method"],
        "route_template": expected["route_template"],
        "request_constraints": json.loads(expected["request_constraints_json"]),
        "response_constraints": json.loads(expected["response_constraints_json"]),
        "status_codes": json.loads(expected["status_codes_json"]),
        "media_type_refs": json.loads(expected["media_type_refs_json"]),
    }
    _assert_ref(response.refs, part="PS3.18")


def test_real_kb_ps316_sr_template_golden(
    connection: sqlite3.Connection, edition: str
) -> None:
    expected = _require_sr_template(connection, edition)

    response = lookup_sr_template(
        connection, tid_or_name=str(expected["tid"]), edition=edition
    )
    result = _ok_result(response)

    assert result["tid"] == expected["tid"]
    assert result["name"] == expected["name"]
    assert result["extensibility"] == expected["extensibility"]
    assert result["rows"]
    _assert_ref(response.refs, part="PS3.16")


def test_real_kb_ps316_context_group_golden(
    connection: sqlite3.Connection, edition: str
) -> None:
    expected = _require_context_group(connection, edition)

    response = lookup_context_group(
        connection, cid_or_name=str(expected["cid"]), edition=edition
    )
    result = _ok_result(response)

    assert result["cid"] == expected["cid"]
    assert result["name"] == expected["name"]
    assert result["extensibility"] == expected["extensibility"]
    assert result["version"] == expected["version"]
    assert result["rows"]
    _assert_ref(response.refs, part="PS3.16")


def test_real_kb_ps316_code_meaning_golden(
    connection: sqlite3.Connection, edition: str
) -> None:
    expected = _require_unique_code_meaning(connection, edition)

    response = lookup_code_meaning(
        connection,
        code_value=str(expected["code_value"]),
        scheme=str(expected["coding_scheme_designator"]),
        edition=edition,
    )
    result = _ok_result(response)

    assert result["code_value"] == expected["code_value"]
    assert result["coding_scheme_designator"] == expected["coding_scheme_designator"]
    assert result["coding_scheme_version"] == (
        expected["coding_scheme_version"] or None
    )
    assert result["code_meaning"] == expected["code_meaning"]
    assert result["context_groups"]
    _assert_ref(response.refs, part="PS3.16")


def test_real_kb_contextual_value_term_golden(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = lookup_enumerated_values(
        connection,
        attribute="Modality",
        context="CT Image",
        edition=edition,
    )
    result = _ok_result(response)

    assert result["attribute"]["tag"] == "(0008,0060)"
    assert result["attribute"]["keyword"] == "Modality"
    assert result["terms"]
    assert {term["attribute_use_id"] for term in result["terms"]} == {
        f"{edition}.module.general_series.attribute_use.0"
    }
    assert {term["context_label"] for term in result["terms"]} == {
        "General Series Module - Enumerated Values:"
    }
    assert {ref.part for ref in response.refs} >= {"PS3.3", "PS3.6"}


def test_real_kb_contextual_defined_term_golden(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = lookup_defined_terms(
        connection,
        attribute="PatientName",
        context="CT Image Storage",
        edition=edition,
    )
    result = _ok_result(response)

    assert result["attribute"]["tag"] == "(0010,0010)"
    assert result["attribute"]["keyword"] == "PatientName"
    assert result["terms"]
    assert {term["attribute_use_id"] for term in result["terms"]} == {
        f"{edition}.module.patient.attribute_use.0"
    }
    assert {term["context_label"] for term in result["terms"]} == {
        "Patient Module - Defined Terms:"
    }
    assert {ref.part for ref in response.refs} >= {"PS3.3", "PS3.4", "PS3.6"}


@pytest.mark.parametrize("iod_name", IOD_GOLDENS)
def test_real_kb_iod_goldens_resolve_with_anchor_modules(
    connection: sqlite3.Connection, edition: str, iod_name: str
) -> None:
    iod_response = lookup_iod(connection, iod_name=iod_name, edition=edition)
    iod = _ok_result(iod_response)
    assert iod["name"] == iod_name
    _assert_ref(iod_response.refs, part="PS3.3")

    modules_response = list_modules_for_iod(
        connection, iod_name=iod_name, edition=edition
    )
    modules_result = _ok_result(modules_response)
    modules = {module["module_name"]: module for module in modules_result["modules"]}
    assert modules["Patient"]["usage"] == "M"
    assert modules["SOP Common"]["usage"] == "M"
    _assert_ref(modules_response.refs, part="PS3.3")


@pytest.mark.parametrize("module_name", MODULE_GOLDENS)
def test_real_kb_module_goldens_return_attributes(
    connection: sqlite3.Connection, edition: str, module_name: str
) -> None:
    response = list_attributes_for_module(
        connection, module_name=module_name, edition=edition
    )
    result = _ok_result(response)

    assert result["module"]["name"] == module_name
    assert result["attributes"]
    _assert_ref(response.refs, part="PS3.3")


def test_real_kb_general_series_contains_modality_type_one(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = list_attributes_for_module(
        connection, module_name="General Series", edition=edition
    )
    result = _ok_result(response)
    modality = _attribute_by_tag(result["attributes"], "(0008,0060)")

    assert modality["attribute_name"] == "Modality"
    assert modality["type_designation"] == "1"
    _assert_ref(response.refs, part="PS3.3", anchor="table_C.7-5a")


@pytest.mark.parametrize(
    ("sop_class", "expected_iod"),
    [
        ("1.2.840.10008.5.1.4.1.1.2", "CT Image"),
        ("1.2.840.10008.5.1.4.1.1.66.4", "Segmentation"),
    ],
)
def test_real_kb_sop_class_to_iod_goldens(
    connection: sqlite3.Connection,
    edition: str,
    sop_class: str,
    expected_iod: str,
) -> None:
    response = lookup_sop_class(
        connection, uid_or_name_or_keyword=sop_class, edition=edition
    )
    result = _ok_result(response)

    assert {iod["iod_name"] for iod in result["iods"]} == {expected_iod}
    _assert_ref(response.refs, part="PS3.4")
    _assert_ref(response.refs, part="PS3.3")


def test_real_kb_module_macro_include_expands_with_dual_provenance(
    connection: sqlite3.Connection, edition: str
) -> None:
    row = connection.execute(
        """
        SELECT owner.name AS module_name
        FROM attribute_use include_row
        JOIN module owner ON owner.id = include_row.owner_id
        WHERE include_row.edition_id = ?
          AND include_row.owner_type = 'module'
          AND include_row.row_kind = 'include'
          AND include_row.included_macro_id IS NOT NULL
        LIMIT 1
        """,
        (edition,),
    ).fetchone()
    assert row is not None

    response = list_attributes_for_module(
        connection,
        module_name=str(row["module_name"]),
        edition=edition,
        expand_macros=True,
    )
    result = _ok_result(response)
    assert any(
        attribute.get("expanded_from_include_id") for attribute in result["attributes"]
    )
    assert len({ref.anchor for ref in response.refs if ref.part == "PS3.3"}) >= 2


def test_real_kb_enhanced_ct_functional_group_context_traversal(
    connection: sqlite3.Connection, edition: str
) -> None:
    row = connection.execute(
        """
        SELECT macro_attr.attribute_tag AS attribute_tag
        FROM iod_functional_group_use fg
        JOIN iod ON iod.id = fg.iod_id
        JOIN attribute_use macro_attr
          ON macro_attr.owner_type = 'macro'
         AND macro_attr.owner_id = fg.macro_id
         AND macro_attr.edition_id = fg.edition_id
        WHERE fg.edition_id = ?
          AND iod.name = 'Enhanced CT Image'
          AND macro_attr.attribute_tag IS NOT NULL
        ORDER BY macro_attr.row_order
        LIMIT 1
        """,
        (edition,),
    ).fetchone()
    assert row is not None

    response = resolve_attribute_context(
        connection,
        attribute=str(row["attribute_tag"]),
        iod_name="Enhanced CT Image",
        edition=edition,
    )
    result = _ok_result(response)
    assert any(use["via_macro"] for use in result["uses"])


def _ok_result(response: ToolResponse) -> dict[str, Any]:
    assert response.status == "ok"
    assert response.result is not None
    assert response.refs
    return response.result


def _assert_ref(
    refs: list[StandardRef], *, part: str, anchor: str | None = None
) -> None:
    matches = [
        ref
        for ref in refs
        if ref.part == part and (anchor is None or ref.anchor == anchor)
    ]
    assert matches
    assert all(ref.official_url for ref in matches if ref.anchor is not None)


def _require_phase2_encoding_rows(connection: sqlite3.Connection, edition: str) -> None:
    try:
        row = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM transfer_syntax_detail
            WHERE edition_id = ?
            """,
            (edition,),
        ).fetchone()
    except sqlite3.OperationalError as exc:
        pytest.skip(f"real KB must be rebuilt with Phase 2 schema: {exc}")
    if row is None or int(row["count"]) == 0:
        pytest.skip("real KB must be rebuilt with Phase 2 transfer syntax rows")


def _require_v2_rows(
    connection: sqlite3.Connection, edition: str, table: str, *, part: str | None = None
) -> None:
    try:
        if part is None:
            row = connection.execute(
                f"SELECT COUNT(*) AS count FROM {table} WHERE edition_id = ?",
                (edition,),
            ).fetchone()
        else:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS count
                FROM {table}
                JOIN source_ref ON source_ref.id = {table}.source_ref_id
                WHERE {table}.edition_id = ?
                  AND source_ref.part = ?
                """,
                (edition, part),
            ).fetchone()
    except sqlite3.OperationalError as exc:
        pytest.skip(f"real KB must be rebuilt with v2 schema: {exc}")
    if row is None or int(row["count"]) == 0:
        part_suffix = f" for {part}" if part else ""
        pytest.skip(f"real KB must be rebuilt with {table} rows{part_suffix}")


def _require_vr_definition(
    connection: sqlite3.Connection, edition: str, *, vr: str
) -> sqlite3.Row:
    _require_v2_rows(connection, edition, "vr_definition")
    row = connection.execute(
        """
        SELECT vr, name, binary_or_text
        FROM vr_definition
        WHERE edition_id = ? AND vr = ?
        """,
        (edition, vr),
    ).fetchone()
    if row is None:
        pytest.skip(f"real KB must include PS3.5 VR definition row for {vr}")
    return row


def _require_unique_media_type(
    connection: sqlite3.Connection, edition: str, *, source_part: str
) -> sqlite3.Row:
    _require_v2_rows(connection, edition, "dicom_media_type", part=source_part)
    row = connection.execute(
        """
        SELECT media.*
        FROM dicom_media_type media
        JOIN source_ref sr ON sr.id = media.source_ref_id
        WHERE media.edition_id = ?
          AND sr.part = ?
          AND media.service_context IS NOT NULL
          AND (
            SELECT COUNT(*)
            FROM dicom_media_type candidate
            WHERE candidate.edition_id = media.edition_id
              AND lower(candidate.service_context) = lower(media.service_context)
          ) = 1
        ORDER BY media.id
        LIMIT 1
        """,
        (edition, source_part),
    ).fetchone()
    if row is None:
        pytest.skip(f"real KB must include a unique {source_part} media context")
    return row


def _require_unique_dicomweb_transaction(
    connection: sqlite3.Connection, edition: str
) -> sqlite3.Row:
    _require_v2_rows(connection, edition, "dicomweb_transaction", part="PS3.18")
    row = connection.execute(
        """
        SELECT txn.*
        FROM dicomweb_transaction txn
        JOIN source_ref sr ON sr.id = txn.source_ref_id
        WHERE txn.edition_id = ?
          AND sr.part = 'PS3.18'
          AND (
            SELECT COUNT(*)
            FROM dicomweb_transaction candidate
            WHERE candidate.edition_id = txn.edition_id
              AND lower(candidate.transaction_name) = lower(txn.transaction_name)
          ) = 1
        ORDER BY
          CASE WHEN lower(txn.transaction_name) LIKE '%retrieve%' THEN 0 ELSE 1 END,
          txn.id
        LIMIT 1
        """,
        (edition,),
    ).fetchone()
    if row is None:
        pytest.skip("real KB must include a unique PS3.18 transaction name")
    return row


def _require_sr_template(connection: sqlite3.Connection, edition: str) -> sqlite3.Row:
    _require_v2_rows(connection, edition, "sr_template", part="PS3.16")
    row = connection.execute(
        """
        SELECT template.*
        FROM sr_template template
        JOIN source_ref sr ON sr.id = template.source_ref_id
        WHERE template.edition_id = ?
          AND sr.part = 'PS3.16'
          AND EXISTS (
            SELECT 1
            FROM sr_template_row template_row
            WHERE template_row.sr_template_id = template.id
          )
        ORDER BY CASE WHEN template.tid = 'TID 1500' THEN 0 ELSE 1 END, template.id
        LIMIT 1
        """,
        (edition,),
    ).fetchone()
    if row is None:
        pytest.skip("real KB must include a PS3.16 SR template with rows")
    return row


def _require_context_group(connection: sqlite3.Connection, edition: str) -> sqlite3.Row:
    _require_v2_rows(connection, edition, "context_group", part="PS3.16")
    row = connection.execute(
        """
        SELECT context_group.*
        FROM context_group
        JOIN source_ref sr ON sr.id = context_group.source_ref_id
        WHERE context_group.edition_id = ?
          AND sr.part = 'PS3.16'
          AND EXISTS (
            SELECT 1
            FROM context_group_row context_row
            WHERE context_row.context_group_id = context_group.id
          )
        ORDER BY CASE WHEN context_group.cid = 'CID 29' THEN 0 ELSE 1 END,
                 context_group.id
        LIMIT 1
        """,
        (edition,),
    ).fetchone()
    if row is None:
        pytest.skip("real KB must include a PS3.16 context group with rows")
    return row


def _require_unique_code_meaning(
    connection: sqlite3.Connection, edition: str
) -> sqlite3.Row:
    _require_v2_rows(connection, edition, "coded_concept", part="PS3.16")
    row = connection.execute(
        """
        SELECT concept.*
        FROM coded_concept concept
        JOIN source_ref sr ON sr.id = concept.source_ref_id
        WHERE concept.edition_id = ?
          AND sr.part = 'PS3.16'
          AND EXISTS (
            SELECT 1
            FROM context_group_row context_row
            WHERE context_row.code_value = concept.code_value
              AND context_row.coding_scheme_designator =
                  concept.coding_scheme_designator
          )
          AND (
            SELECT COUNT(*)
            FROM coded_concept candidate
            WHERE candidate.edition_id = concept.edition_id
              AND candidate.code_value = concept.code_value
              AND candidate.coding_scheme_designator =
                  concept.coding_scheme_designator
          ) = 1
        ORDER BY
          CASE
            WHEN concept.code_value = 'CT'
             AND concept.coding_scheme_designator = 'DCM'
            THEN 0 ELSE 1
          END,
          concept.id
        LIMIT 1
        """,
        (edition,),
    ).fetchone()
    if row is None:
        pytest.skip("real KB must include a unique PS3.16 coded concept")
    return row


def _attribute_by_tag(attributes: list[dict[str, Any]], tag: str) -> dict[str, Any]:
    for attribute in attributes:
        if attribute.get("attribute_tag") == tag:
            return attribute
    raise AssertionError(f"attribute {tag} not found")
