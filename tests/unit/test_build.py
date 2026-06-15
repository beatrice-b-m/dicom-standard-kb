from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from dicom_kb.build import (
    BuildMetrics,
    DatabaseExistsError,
    QualityGateSettings,
    build_sqlite_database,
    default_db_path,
    evaluate_quality_gates,
)
from dicom_kb.db.importers import ImportSummary
from dicom_kb.query.resolver import (
    lookup_data_element,
    lookup_defined_terms,
    lookup_sop_class,
    lookup_vr,
)
from dicom_kb.sources.downloader import (
    DEFAULT_DOCBOOK_PARTS,
    DOCBOOK_XML_FORMAT,
    ArtifactRequest,
    official_artifact_destination,
    register_local_artifacts,
)
from tests.fixtures_synthetic import FIXTURE_DIR


def _register_synthetic_artifacts(cache_dir: Path) -> None:
    fixtures = {
        "PS3.3": "synthetic_ps3_3_ct_image_docbook.xml",
        "PS3.4": "synthetic_ps3_4_sop_classes_docbook.xml",
        "PS3.5": "synthetic_ps3_5_encoding_docbook.xml",
        "PS3.6": "synthetic_ps3_6_registry_docbook.xml",
        "PS3.7": "synthetic_ps3_7_messages_docbook.xml",
        "PS3.8": "synthetic_ps3_8_network_docbook.xml",
        "PS3.10": "synthetic_ps3_10_media_storage_docbook.xml",
        "PS3.16": "synthetic_ps3_16_content_mapping_docbook.xml",
        "PS3.18": "synthetic_ps3_18_web_services_docbook.xml",
    }
    register_local_artifacts(
        edition="2026b",
        cache_dir=cache_dir,
        artifacts=[
            ArtifactRequest(
                part=part,
                format=DOCBOOK_XML_FORMAT,
                source=FIXTURE_DIR / filename,
                destination=official_artifact_destination(
                    "2026b",
                    part=part,
                    artifact_format=DOCBOOK_XML_FORMAT,
                ),
            )
            for part, filename in fixtures.items()
        ],
    )


def _register_synthetic_parts(cache_dir: Path, fixtures: dict[str, str]) -> None:
    register_local_artifacts(
        edition="2026b",
        cache_dir=cache_dir,
        artifacts=[
            ArtifactRequest(
                part=part,
                format=DOCBOOK_XML_FORMAT,
                source=FIXTURE_DIR / filename,
                destination=official_artifact_destination(
                    "2026b",
                    part=part,
                    artifact_format=DOCBOOK_XML_FORMAT,
                ),
            )
            for part, filename in fixtures.items()
        ],
    )


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def test_build_sqlite_database_imports_manifest_docbook_and_metadata(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_artifacts(cache_dir)

    summary = build_sqlite_database(edition="2026b", cache_dir=cache_dir)

    assert summary.edition == "2026b"
    assert summary.db_path == default_db_path(cache_dir, "2026b")
    assert summary.db_path.exists()
    assert any("skipped malformed tag row" in warning for warning in summary.warnings)
    assert any("PS3.5 table_5-2" in warning for warning in summary.warnings)
    assert any("PS3.7 table_7-2" in warning for warning in summary.warnings)
    assert any("PS3.8 table_8-2" in warning for warning in summary.warnings)
    assert any("PS3.10 table_10-3" in warning for warning in summary.warnings)
    assert any("PS3.16 table_16-2" in warning for warning in summary.warnings)
    assert any("PS3.18 table_18-3" in warning for warning in summary.warnings)
    assert any(
        import_summary.file_meta_requirements == 7
        for import_summary in summary.import_summaries
    )
    assert any(
        import_summary.dicom_media_types == 1
        for import_summary in summary.import_summaries
    )
    assert any(
        import_summary.dicom_media_types == 3
        for import_summary in summary.import_summaries
    )
    assert any(
        import_summary.dicomweb_transactions == 2
        for import_summary in summary.import_summaries
    )
    assert any(
        import_summary.sr_templates == 1
        for import_summary in summary.import_summaries
    )
    assert any(
        import_summary.sr_template_rows == 2
        for import_summary in summary.import_summaries
    )
    assert any(
        import_summary.context_groups == 1
        for import_summary in summary.import_summaries
    )
    assert any(
        import_summary.context_group_rows == 2
        for import_summary in summary.import_summaries
    )
    assert any(
        import_summary.coded_concepts == 1
        for import_summary in summary.import_summaries
    )
    metrics = summary.metrics.as_jsonable()
    assert set(metrics) == {
        "edition",
        "parts_loaded",
        "data_elements",
        "uids",
        "iods",
        "modules",
        "macros",
        "iod_module_uses",
        "iod_functional_group_uses",
        "attribute_uses",
        "include_rows_resolved",
        "include_rows_unresolved",
        "sop_classes",
        "conditions",
        "xrefs_total",
        "xrefs_unresolved",
        "parse_warnings",
        "parse_warnings_by_part",
        "source_refs",
    }
    assert metrics["edition"] == "2026b"
    assert metrics["parts_loaded"] == sorted(DEFAULT_DOCBOOK_PARTS)
    assert metrics["parse_warnings"] == len(summary.warnings)
    assert metrics["parse_warnings_by_part"] == {
        "PS3.3": 0,
        "PS3.4": 1,
        "PS3.5": 1,
        "PS3.6": 2,
        "PS3.7": 1,
        "PS3.8": 1,
        "PS3.10": 1,
        "PS3.16": 1,
        "PS3.18": 1,
    }
    assert metrics["include_rows_resolved"] == 1
    assert metrics["include_rows_unresolved"] == 0
    assert metrics["xrefs_total"] >= metrics["xrefs_unresolved"]

    with _connect(summary.db_path) as connection:
        tag_response = lookup_data_element(
            connection, tag_or_keyword="Modality", edition="2026b"
        )
        sop_response = lookup_sop_class(
            connection,
            uid_or_name_or_keyword="CT Image Storage",
            edition="2026b",
        )
        terms_response = lookup_defined_terms(
            connection,
            attribute="PatientName",
            edition="2026b",
        )
        metadata = connection.execute(
            "SELECT metadata_json, schema_version FROM build_metadata "
            "WHERE edition_id = ?",
            ("2026b",),
        ).fetchone()
        v2_parts = connection.execute(
            "SELECT DISTINCT part FROM doc_node "
            "WHERE edition_id = ? AND part NOT IN ('PS3.3', 'PS3.4', 'PS3.6') "
            "ORDER BY part",
            ("2026b",),
        ).fetchall()
        v2_tables = connection.execute(
            "SELECT part, table_id FROM raw_table_ir "
            "WHERE edition_id = ? AND part NOT IN ('PS3.3', 'PS3.4', 'PS3.6') "
            "ORDER BY part, table_id",
            ("2026b",),
        ).fetchall()
        vr_rows = connection.execute(
            "SELECT vr, name, binary_or_text FROM vr_definition "
            "WHERE edition_id = ? ORDER BY vr",
            ("2026b",),
        ).fetchall()
        transfer_syntax_rows = connection.execute(
            """
            SELECT uid_value, explicit_vr, endian, encapsulated, compression_family
            FROM transfer_syntax_detail
            WHERE edition_id = ?
            ORDER BY uid_value
            """,
            ("2026b",),
        ).fetchall()
        file_meta_rows = connection.execute(
            """
            SELECT attribute_tag, type_designation, rule_context
            FROM file_meta_requirement
            WHERE edition_id = ?
            ORDER BY attribute_tag
            """,
            ("2026b",),
        ).fetchall()
        media_type_rows = connection.execute(
            """
            SELECT media_type, service_context, transfer_syntax_constraints_json,
                   directions_json
            FROM dicom_media_type
            WHERE edition_id = ?
            ORDER BY media_type, service_context
            """,
            ("2026b",),
        ).fetchall()
        dicomweb_rows = connection.execute(
            """
            SELECT transaction_name, resource_category, http_method, route_template,
                   request_constraints_json, response_constraints_json,
                   status_codes_json, media_type_refs_json
            FROM dicomweb_transaction
            WHERE edition_id = ?
            ORDER BY transaction_name
            """,
            ("2026b",),
        ).fetchall()
        sr_template_rows = connection.execute(
            """
            SELECT template.tid, template.name, template.extensibility,
                   row.row_order, row.relationship_type, row.value_type,
                   row.concept_name, row.cardinality, row.condition_text,
                   row.include_tid
            FROM sr_template template
            JOIN sr_template_row row ON row.sr_template_id = template.id
            WHERE template.edition_id = ?
            ORDER BY row.row_order
            """,
            ("2026b",),
        ).fetchall()
        context_group_rows = connection.execute(
            """
            SELECT context_group.cid, context_group.name,
                   context_group.extensibility, context_group.version,
                   row.row_order, row.coding_scheme_designator,
                   row.coding_scheme_version, row.code_value, row.code_meaning,
                   row.include_cid
            FROM context_group
            JOIN context_group_row row ON row.context_group_id = context_group.id
            WHERE context_group.edition_id = ?
            ORDER BY row.row_order
            """,
            ("2026b",),
        ).fetchall()
        coded_concept_rows = connection.execute(
            """
            SELECT code_value, coding_scheme_designator, coding_scheme_version,
                   code_meaning
            FROM coded_concept
            WHERE edition_id = ?
            ORDER BY code_value
            """,
            ("2026b",),
        ).fetchall()

    assert tag_response.status == "ok"
    assert sop_response.status == "ok"
    assert terms_response.status == "ok"
    assert terms_response.result is not None
    assert len(terms_response.result["terms"]) == 2
    assert metadata["schema_version"] == "8"
    payload = json.loads(metadata["metadata_json"])
    assert payload["edition"] == "2026b"
    assert {row["part"] for row in v2_parts} == {
        "PS3.5",
        "PS3.7",
        "PS3.8",
        "PS3.10",
        "PS3.16",
        "PS3.18",
    }
    assert len(v2_tables) == 15
    assert [dict(row) for row in vr_rows] == [
        {"vr": "OB", "name": "Other Byte", "binary_or_text": "binary"},
        {"vr": "PN", "name": "Person Name", "binary_or_text": "text"},
        {"vr": "SQ", "name": "Sequence of Items", "binary_or_text": "binary"},
        {"vr": "UN", "name": "Unknown", "binary_or_text": "binary"},
    ]
    assert [dict(row) for row in transfer_syntax_rows] == [
        {
            "uid_value": "1.2.840.10008.1.2",
            "explicit_vr": 0,
            "endian": "little",
            "encapsulated": 0,
            "compression_family": None,
        },
        {
            "uid_value": "1.2.840.10008.1.2.1",
            "explicit_vr": 1,
            "endian": "little",
            "encapsulated": 0,
            "compression_family": None,
        },
        {
            "uid_value": "1.2.840.10008.1.2.1.99",
            "explicit_vr": 1,
            "endian": "little",
            "encapsulated": 0,
            "compression_family": "deflated",
        },
        {
            "uid_value": "1.2.840.10008.1.2.2",
            "explicit_vr": 1,
            "endian": "big",
            "encapsulated": 0,
            "compression_family": None,
        },
        {
            "uid_value": "1.2.840.10008.1.2.4.50",
            "explicit_vr": None,
            "endian": None,
            "encapsulated": 1,
            "compression_family": "jpeg",
        },
    ]
    assert [dict(row) for row in file_meta_rows] == [
        {
            "attribute_tag": "(0002,0000)",
            "type_designation": "1",
            "rule_context": "file_meta_information",
        },
        {
            "attribute_tag": "(0002,0002)",
            "type_designation": "1",
            "rule_context": "file_meta_information",
        },
        {
            "attribute_tag": "(0002,0003)",
            "type_designation": "1",
            "rule_context": "file_meta_information",
        },
        {
            "attribute_tag": "(0002,0010)",
            "type_designation": "1",
            "rule_context": "file_meta_information",
        },
        {
            "attribute_tag": "(0002,0012)",
            "type_designation": "1",
            "rule_context": "file_meta_information",
        },
        {
            "attribute_tag": "(0002,0013)",
            "type_designation": "3",
            "rule_context": "file_meta_information",
        },
        {
            "attribute_tag": "(0002,0016)",
            "type_designation": "3",
            "rule_context": "file_meta_information",
        },
    ]
    assert [dict(row) for row in media_type_rows] == [
        {
            "media_type": "application/dicom",
            "service_context": "Instance Media Types",
            "transfer_syntax_constraints_json": json.dumps(
                ("Explicit VR Little Endian required for single-instance media",),
                separators=(",", ":"),
            ),
            "directions_json": json.dumps(("response",), separators=(",", ":")),
        },
        {
            "media_type": "application/dicom",
            "service_context": "PS3.10 file",
            "transfer_syntax_constraints_json": json.dumps(
                (
                    "Encoded using the Transfer Syntax UID in the "
                    "File Meta Information",
                ),
                separators=(",", ":"),
            ),
            "directions_json": json.dumps(("file",), separators=(",", ":")),
        },
        {
            "media_type": "multipart/related",
            "service_context": "STOW-RS request",
            "transfer_syntax_constraints_json": json.dumps(
                ("Each part supplies a DICOM instance payload",),
                separators=(",", ":"),
            ),
            "directions_json": json.dumps(("request",), separators=(",", ":")),
        },
        {
            "media_type": "multipart/related",
            "service_context": "WADO-RS response",
            "transfer_syntax_constraints_json": json.dumps(
                ("Rendered transfer syntax negotiated by Accept header",),
                separators=(",", ":"),
            ),
            "directions_json": json.dumps(("response",), separators=(",", ":")),
        },
    ]
    assert [dict(row) for row in dicomweb_rows] == [
        {
            "transaction_name": "RetrieveStudy",
            "resource_category": "study",
            "http_method": "GET",
            "route_template": "/studies/{studyInstanceUID}",
            "request_constraints_json": json.dumps(
                ("Study Instance UID required",),
                separators=(",", ":"),
            ),
            "response_constraints_json": json.dumps(
                ("DICOM instances returned",),
                separators=(",", ":"),
            ),
            "status_codes_json": json.dumps(
                ("200", "400", "404"),
                separators=(",", ":"),
            ),
            "media_type_refs_json": json.dumps(
                ("application/dicom",),
                separators=(",", ":"),
            ),
        },
        {
            "transaction_name": "StoreInstances",
            "resource_category": "study",
            "http_method": "POST",
            "route_template": "/studies/{studyInstanceUID}",
            "request_constraints_json": json.dumps(
                ("Multipart request body required",),
                separators=(",", ":"),
            ),
            "response_constraints_json": json.dumps(
                ("Store response returned",),
                separators=(",", ":"),
            ),
            "status_codes_json": json.dumps(
                ("200", "202", "409"),
                separators=(",", ":"),
            ),
            "media_type_refs_json": json.dumps(
                ("multipart/related", "application/dicom"),
                separators=(",", ":"),
            ),
        },
    ]
    assert [dict(row) for row in sr_template_rows] == [
        {
            "tid": "TID 1500",
            "name": "Measurement Report",
            "extensibility": "EXTENSIBLE",
            "row_order": 1,
            "relationship_type": "CONTAINS",
            "value_type": "CONTAINER",
            "concept_name": "Measurement Report",
            "cardinality": "1",
            "condition_text": "Root container is required.",
            "include_tid": None,
        },
        {
            "tid": "TID 1500",
            "name": "Measurement Report",
            "extensibility": "EXTENSIBLE",
            "row_order": 2,
            "relationship_type": "CONTAINS",
            "value_type": "INCLUDE",
            "concept_name": None,
            "cardinality": "1-n",
            "condition_text": "Include measurements when present.",
            "include_tid": "TID 1501",
        },
    ]
    assert [dict(row) for row in context_group_rows] == [
        {
            "cid": "CID 29",
            "name": "Acquisition Modality",
            "extensibility": "EXTENSIBLE",
            "version": "20260101",
            "row_order": 1,
            "coding_scheme_designator": "DCM",
            "coding_scheme_version": None,
            "code_value": "CT",
            "code_meaning": "Computed Tomography",
            "include_cid": None,
        },
        {
            "cid": "CID 29",
            "name": "Acquisition Modality",
            "extensibility": "EXTENSIBLE",
            "version": "20260101",
            "row_order": 2,
            "coding_scheme_designator": None,
            "coding_scheme_version": None,
            "code_value": None,
            "code_meaning": None,
            "include_cid": "CID 30",
        },
    ]
    assert [dict(row) for row in coded_concept_rows] == [
        {
            "code_value": "CT",
            "coding_scheme_designator": "DCM",
            "coding_scheme_version": "",
            "code_meaning": "Computed Tomography",
        },
    ]
    assert set(payload["source_sha256"]) == {
        official_artifact_destination(
            "2026b",
            part=part,
            artifact_format=DOCBOOK_XML_FORMAT,
        )
        for part in DEFAULT_DOCBOOK_PARTS
    }
    assert payload["metrics"] == metrics


def test_build_sqlite_database_derives_transfer_syntax_details_from_part06_only(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_parts(
        cache_dir,
        {"PS3.6": "synthetic_ps3_6_registry_docbook.xml"},
    )

    summary = build_sqlite_database(edition="2026b", cache_dir=cache_dir)

    assert summary.metrics.parts_loaded == ("PS3.6",)
    assert any(
        import_summary.transfer_syntax_details == 5
        for import_summary in summary.import_summaries
    )
    with _connect(summary.db_path) as connection:
        row = connection.execute(
            """
            SELECT explicit_vr, endian
            FROM transfer_syntax_detail
            WHERE edition_id = ? AND uid_value = ?
            """,
            ("2026b", "1.2.840.10008.1.2.1"),
        ).fetchone()

    assert row is not None
    assert dict(row) == {"explicit_vr": 1, "endian": "little"}


def test_build_sqlite_database_imports_official_shape_part05_vr_table(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_parts(
        cache_dir,
        {"PS3.5": "synthetic_ps3_5_official_shape_docbook.xml"},
    )

    summary = build_sqlite_database(edition="2026b", cache_dir=cache_dir)

    assert summary.metrics.parts_loaded == ("PS3.5",)
    assert summary.warnings == ()
    assert any(
        import_summary.vr_definitions == 2
        for import_summary in summary.import_summaries
    )
    with _connect(summary.db_path) as connection:
        response = lookup_vr(connection, vr="PN", edition="2026b")

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["name"] == "Person Name"
    assert response.result["binary_or_text"] == "text"
    assert response.refs[0].part == "PS3.5"
    assert response.refs[0].section == "sect_6.2"
    assert response.refs[0].anchor == "table_6.2-1"


def test_build_sqlite_database_imports_official_shape_part16_rows(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_parts(
        cache_dir,
        {"PS3.16": "synthetic_ps3_16_official_shape_docbook.xml"},
    )

    summary = build_sqlite_database(edition="2026b", cache_dir=cache_dir)

    assert summary.metrics.parts_loaded == ("PS3.16",)
    assert summary.warnings == ()
    assert any(
        import_summary.sr_templates == 1
        and import_summary.sr_template_rows == 4
        for import_summary in summary.import_summaries
    )
    assert any(
        import_summary.context_groups == 1
        and import_summary.context_group_rows == 2
        for import_summary in summary.import_summaries
    )
    assert any(
        import_summary.coded_concepts == 1
        for import_summary in summary.import_summaries
    )
    with _connect(summary.db_path) as connection:
        sr_template_rows = connection.execute(
            """
            SELECT template.tid, template.name, template.extensibility,
                   row.row_order, row.relationship_type, row.value_type,
                   row.concept_name, row.cardinality, row.condition_text,
                   row.include_tid, ref.part, ref.table_id, ref.title
            FROM sr_template template
            JOIN sr_template_row row ON row.sr_template_id = template.id
            JOIN source_ref ref ON ref.id = row.source_ref_id
            WHERE template.edition_id = ?
            ORDER BY row.row_order
            """,
            ("2026b",),
        ).fetchall()
        context_group_rows = connection.execute(
            """
            SELECT context_group.cid, context_group.name,
                   context_group.extensibility, context_group.version,
                   row.row_order, row.coding_scheme_designator,
                   row.coding_scheme_version, row.code_value, row.code_meaning,
                   row.include_cid, ref.part, ref.table_id, ref.title
            FROM context_group
            JOIN context_group_row row ON row.context_group_id = context_group.id
            JOIN source_ref ref ON ref.id = row.source_ref_id
            WHERE context_group.edition_id = ?
            ORDER BY row.row_order
            """,
            ("2026b",),
        ).fetchall()
        coded_concept_rows = connection.execute(
            """
            SELECT concept.code_value, concept.coding_scheme_designator,
                   concept.coding_scheme_version, concept.code_meaning,
                   ref.part, ref.table_id, ref.title
            FROM coded_concept concept
            JOIN source_ref ref ON ref.id = concept.source_ref_id
            WHERE concept.edition_id = ?
            ORDER BY concept.code_value
            """,
            ("2026b",),
        ).fetchall()

    assert [dict(row) for row in sr_template_rows] == [
        {
            "tid": "TID 1500",
            "name": "Measurement Report",
            "extensibility": "Extensible",
            "row_order": 1,
            "relationship_type": None,
            "value_type": "CONTAINER",
            "concept_name": "CID 7021 Measurement Report Document Titles",
            "cardinality": "1",
            "condition_text": None,
            "include_tid": None,
            "part": "PS3.16",
            "table_id": "table_TID_1500",
            "title": "Measurement Report",
        },
        {
            "tid": "TID 1500",
            "name": "Measurement Report",
            "extensibility": "Extensible",
            "row_order": 2,
            "relationship_type": "> HAS OBS CONTEXT",
            "value_type": "INCLUDE",
            "concept_name": "TID 1001 Observation Context",
            "cardinality": "1",
            "condition_text": None,
            "include_tid": "TID 1001",
            "part": "PS3.16",
            "table_id": "table_TID_1500",
            "title": "Measurement Report",
        },
        {
            "tid": "TID 1500",
            "name": "Measurement Report",
            "extensibility": "Extensible",
            "row_order": 3,
            "relationship_type": "> CONTAINS",
            "value_type": "INCLUDE",
            "concept_name": "TID 1501 Measurement Group",
            "cardinality": "1-n",
            "condition_text": None,
            "include_tid": "TID 1501",
            "part": "PS3.16",
            "table_id": "table_TID_1500",
            "title": "Measurement Report",
        },
        {
            "tid": "TID 1500",
            "name": "Measurement Report",
            "extensibility": "Extensible",
            "row_order": 4,
            "relationship_type": "> CONTAINS",
            "value_type": "TEXT",
            "concept_name": None,
            "cardinality": "0-1",
            "condition_text": None,
            "include_tid": None,
            "part": "PS3.16",
            "table_id": "table_TID_1500",
            "title": "Measurement Report",
        },
    ]
    assert [dict(row) for row in context_group_rows] == [
        {
            "cid": "CID 29",
            "name": "Acquisition Modality",
            "extensibility": "Extensible",
            "version": "20231115",
            "row_order": 1,
            "coding_scheme_designator": "DCM",
            "coding_scheme_version": None,
            "code_value": "CT",
            "code_meaning": "Computed Tomography",
            "include_cid": None,
            "part": "PS3.16",
            "table_id": "table_CID_29",
            "title": "Acquisition Modality",
        },
        {
            "cid": "CID 29",
            "name": "Acquisition Modality",
            "extensibility": "Extensible",
            "version": "20231115",
            "row_order": 2,
            "coding_scheme_designator": None,
            "coding_scheme_version": None,
            "code_value": None,
            "code_meaning": None,
            "include_cid": "CID 34",
            "part": "PS3.16",
            "table_id": "table_CID_29",
            "title": "Acquisition Modality",
        },
    ]
    assert [dict(row) for row in coded_concept_rows] == [
        {
            "code_value": "CT",
            "coding_scheme_designator": "DCM",
            "coding_scheme_version": "",
            "code_meaning": "Computed Tomography",
            "part": "PS3.16",
            "table_id": "table_CID_29",
            "title": "Acquisition Modality",
        },
    ]


def test_build_sqlite_database_refuses_existing_db_without_force(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_artifacts(cache_dir)
    build_sqlite_database(edition="2026b", cache_dir=cache_dir)

    with pytest.raises(DatabaseExistsError):
        build_sqlite_database(edition="2026b", cache_dir=cache_dir)


def test_build_metrics_aggregate_import_summaries() -> None:
    metrics = BuildMetrics.from_imports(
        edition="2026b",
        parts_loaded=("PS3.3", "PS3.6"),
        import_summaries=(
            ImportSummary(
                edition="2026b",
                source_refs=3,
                data_elements=2,
                uid_registry_entries=1,
                xrefs=4,
                xrefs_unresolved=1,
            ),
            ImportSummary(
                edition="2026b",
                source_refs=5,
                iods=1,
                modules=2,
                attribute_uses=3,
                include_rows_resolved=1,
                include_rows_unresolved=1,
            ),
        ),
        parse_warnings=2,
        parse_warnings_by_part={"PS3.6": 2},
    )

    assert metrics.as_jsonable() == {
        "edition": "2026b",
        "parts_loaded": ["PS3.3", "PS3.6"],
        "data_elements": 2,
        "uids": 1,
        "iods": 1,
        "modules": 2,
        "macros": 0,
        "iod_module_uses": 0,
        "iod_functional_group_uses": 0,
        "attribute_uses": 3,
        "include_rows_resolved": 1,
        "include_rows_unresolved": 1,
        "sop_classes": 0,
        "conditions": 0,
        "xrefs_total": 4,
        "xrefs_unresolved": 1,
        "parse_warnings": 2,
        "parse_warnings_by_part": {"PS3.3": 0, "PS3.6": 2},
        "source_refs": 8,
    }


def test_evaluate_quality_gates_reports_threshold_failures() -> None:
    metrics = BuildMetrics(
        edition="2026b",
        parts_loaded=("PS3.3",),
        include_rows_resolved=3,
        include_rows_unresolved=1,
        xrefs_total=10,
        xrefs_unresolved=2,
        parse_warnings=4,
    )

    failures = evaluate_quality_gates(
        metrics,
        QualityGateSettings(
            max_unresolved_xref_rate=0.1,
            max_unresolved_include_rate=0.2,
            max_parse_warnings=3,
        ),
    )

    assert failures == (
        "unresolved xref rate 0.2 exceeds configured maximum 0.1",
        "unresolved include-row rate 0.25 exceeds configured maximum 0.2",
        "parse warning count 4 exceeds configured maximum 3",
    )
