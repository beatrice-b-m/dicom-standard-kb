from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from dicom_kb.build import (
    BuildMetrics,
    DatabaseExistsError,
    build_sqlite_database,
    default_db_path,
)
from dicom_kb.db.importers import ImportSummary
from dicom_kb.query.resolver import (
    attribute_values,
    element_usage,
    iod_modules,
    read_standard,
)
from dicom_kb.sources.downloader import (
    DOCBOOK_XML_FORMAT,
    ArtifactRequest,
    official_artifact_destination,
    register_local_artifacts,
)
from tests.fixtures_synthetic import EDITION, FIXTURE_DIR

SYNTHETIC_PARTS = {
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


def _register_synthetic_artifacts(cache_dir: Path) -> None:
    register_local_artifacts(
        edition=EDITION,
        cache_dir=cache_dir,
        artifacts=[
            ArtifactRequest(
                part=part,
                format=DOCBOOK_XML_FORMAT,
                source=FIXTURE_DIR / filename,
                destination=official_artifact_destination(
                    EDITION,
                    part=part,
                    artifact_format=DOCBOOK_XML_FORMAT,
                ),
            )
            for part, filename in SYNTHETIC_PARTS.items()
        ],
    )


def _register_synthetic_parts(cache_dir: Path, fixtures: dict[str, str]) -> None:
    register_local_artifacts(
        edition=EDITION,
        cache_dir=cache_dir,
        artifacts=[
            ArtifactRequest(
                part=part,
                format=DOCBOOK_XML_FORMAT,
                source=FIXTURE_DIR / filename,
                destination=official_artifact_destination(
                    EDITION,
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

    summary = build_sqlite_database(edition=EDITION, cache_dir=cache_dir)

    assert summary.edition == EDITION
    assert summary.db_path == default_db_path(cache_dir, EDITION)
    assert summary.db_path.exists()
    assert any("skipped malformed tag row" in warning for warning in summary.warnings)
    assert any("PS3.16 table_16-2" in warning for warning in summary.warnings)
    assert any(
        import_summary.transfer_syntax_details == 4
        for import_summary in summary.import_summaries
    )
    assert any(
        import_summary.sr_templates == 1 for import_summary in summary.import_summaries
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
    assert metrics["edition"] == EDITION
    assert metrics["parts_loaded"] == sorted(SYNTHETIC_PARTS)
    assert metrics["parse_warnings"] == len(summary.warnings)
    assert metrics["parse_warnings_by_part"] == {
        # The fixture lists two modules it gives no table for, and a SOP
        # Class with no IOD reference.
        "PS3.3": 2,
        "PS3.4": 2,
        "PS3.5": 0,
        "PS3.6": 2,
        "PS3.7": 0,
        "PS3.8": 0,
        "PS3.10": 0,
        "PS3.16": 1,
        "PS3.18": 0,
    }
    assert metrics["include_rows_resolved"] == 1
    assert metrics["include_rows_unresolved"] == 0
    assert metrics["xrefs_total"] >= metrics["xrefs_unresolved"]

    with _connect(summary.db_path) as connection:
        tag_response = element_usage(connection, name="Modality", edition=EDITION)
        sop_response = iod_modules(connection, name="CT Image Storage", edition=EDITION)
        terms_response = attribute_values(
            connection, name="PatientName", edition=EDITION
        )
        metadata = connection.execute(
            "SELECT metadata_json, schema_version FROM build_metadata "
            "WHERE edition_id = ?",
            (EDITION,),
        ).fetchone()
        v2_parts = connection.execute(
            "SELECT DISTINCT part FROM doc_node "
            "WHERE edition_id = ? AND part NOT IN ('PS3.3', 'PS3.4', 'PS3.6') "
            "ORDER BY part",
            (EDITION,),
        ).fetchall()
        v2_tables = connection.execute(
            "SELECT part, xml_id, markdown FROM doc_node "
            "WHERE edition_id = ? AND node_type = 'table' "
            "AND part NOT IN ('PS3.3', 'PS3.4', 'PS3.6') "
            "ORDER BY part, xml_id",
            (EDITION,),
        ).fetchall()
        transfer_syntax_rows = connection.execute(
            """
            SELECT uid_value, vr_encoding, byte_order, pixel_data, deflate
            FROM transfer_syntax_detail
            WHERE edition_id = ?
            ORDER BY uid_value
            """,
            (EDITION,),
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
            (EDITION,),
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
            (EDITION,),
        ).fetchall()
        coded_concept_rows = connection.execute(
            """
            SELECT code_value, coding_scheme_designator, coding_scheme_version,
                   code_meaning
            FROM coded_concept
            WHERE edition_id = ?
            ORDER BY code_value
            """,
            (EDITION,),
        ).fetchall()

    assert tag_response.status == "ok"
    assert sop_response.status == "ok"
    assert terms_response.status == "ok"
    assert terms_response.result is not None
    assert "| ALPHA | Alphabetic representation. |" in terms_response.result["markdown"]
    assert metadata["schema_version"] == "12"
    payload = json.loads(metadata["metadata_json"])
    assert payload["edition"] == EDITION
    assert {row["part"] for row in v2_parts} == {
        "PS3.5",
        "PS3.7",
        "PS3.8",
        "PS3.10",
        "PS3.16",
        "PS3.18",
    }
    assert len(v2_tables) == 17
    assert all(row["markdown"].startswith("**") for row in v2_tables)
    assert [tuple(row) for row in transfer_syntax_rows] == [
        ("1.2.840.10008.1.2", "Implicit VR", "Little Endian", "Native", None),
        ("1.2.840.10008.1.2.1", "Explicit VR", "Little Endian", "Native", None),
        (
            "1.2.840.10008.1.2.1.99",
            "Explicit VR",
            "Little Endian",
            "Native",
            "Whole Data Set",
        ),
        (
            "1.2.840.10008.1.2.4.50",
            "Explicit VR",
            "Little Endian",
            "Encapsulated",
            None,
        ),
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
            EDITION,
            part=part,
            artifact_format=DOCBOOK_XML_FORMAT,
        )
        for part in SYNTHETIC_PARTS
    }
    assert payload["metrics"] == metrics


def test_build_reads_transfer_syntaxes_and_vrs_from_ps35(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_parts(
        cache_dir,
        {
            "PS3.5": "synthetic_ps3_5_encoding_docbook.xml",
            "PS3.6": "synthetic_ps3_6_registry_docbook.xml",
        },
    )

    summary = build_sqlite_database(edition=EDITION, cache_dir=cache_dir)

    assert not [w for w in summary.warnings if w.startswith("PS3.5")]
    with _connect(summary.db_path) as connection:
        transfer_syntax = read_standard(
            connection, reference="ExplicitVRLittleEndian", edition=EDITION
        )
        vr = read_standard(connection, reference="PN", edition=EDITION)

    assert transfer_syntax.status == "ok"
    assert transfer_syntax.result is not None
    assert (
        "| Explicit VR | Little Endian | Native | No |"
        in (transfer_syntax.result["markdown"])
    )
    assert vr.status == "ok"
    assert vr.result is not None
    assert vr.result["markdown"].startswith("**PN** Person Name")
    assert [ref.label for ref in vr.refs] == [
        "PS3.5 Table 6.2-1",
        "PS3.5 Table 7.1-2",
    ]


def test_build_sqlite_database_imports_official_shape_part16_rows(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_parts(
        cache_dir,
        {"PS3.16": "synthetic_ps3_16_official_shape_docbook.xml"},
    )

    summary = build_sqlite_database(edition=EDITION, cache_dir=cache_dir)

    assert summary.metrics.parts_loaded == ("PS3.16",)
    # The fixture includes CID 34 without defining it; the gap is logged once.
    assert summary.warnings == ("PS3.16 reference to PS3.16 sect_CID_34 has no target",)
    assert any(
        import_summary.sr_templates == 1 and import_summary.sr_template_rows == 4
        for import_summary in summary.import_summaries
    )
    assert any(
        import_summary.context_groups == 1 and import_summary.context_group_rows == 2
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
            (EDITION,),
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
            (EDITION,),
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
            (EDITION,),
        ).fetchall()

    assert [dict(row) for row in sr_template_rows] == [
        {
            "tid": "TID 1500",
            "name": "Measurement Report",
            "extensibility": "Extensible",
            "row_order": 1,
            "relationship_type": None,
            "value_type": "CONTAINER",
            "concept_name": "DCID 7021",
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
            "concept_name": "DTID 1001",
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
            "concept_name": "DTID 1501",
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
    build_sqlite_database(edition=EDITION, cache_dir=cache_dir)

    with pytest.raises(DatabaseExistsError):
        build_sqlite_database(edition=EDITION, cache_dir=cache_dir)


def test_build_metrics_aggregate_import_summaries() -> None:
    metrics = BuildMetrics.from_imports(
        edition=EDITION,
        parts_loaded=("PS3.3", "PS3.6"),
        import_summaries=(
            ImportSummary(
                edition=EDITION,
                source_refs=3,
                data_elements=2,
                uid_registry_entries=1,
                xrefs=4,
                xrefs_unresolved=1,
            ),
            ImportSummary(
                edition=EDITION,
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
        "edition": EDITION,
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


@pytest.mark.parametrize("existing", [False, True])
def test_storage_error_does_not_publish_partial_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: bool
) -> None:
    from dicom_kb import build

    cache_dir = tmp_path / "cache"
    _register_synthetic_artifacts(cache_dir)
    target = tmp_path / "kb.sqlite"
    original = b"previous database"
    if existing:
        target.write_bytes(original)

    def fail_import(*args: object, **kwargs: object) -> None:
        raise sqlite3.OperationalError("injected storage failure")

    monkeypatch.setattr(build, "import_part06", fail_import)
    with pytest.raises(build.BuildError):
        build_sqlite_database(
            edition=EDITION, cache_dir=cache_dir, db_path=target, force=existing
        )
    assert target.read_bytes() == original if existing else not target.exists()
    assert list(tmp_path.glob(".kb.sqlite-*")) == []


def test_failed_import_step_is_logged_and_build_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dicom_kb import build

    cache_dir = tmp_path / "cache"
    _register_synthetic_artifacts(cache_dir)

    def fail_import(*args: object, **kwargs: object) -> None:
        raise ImportError("injected import failure")

    monkeypatch.setattr(build, "import_transfer_syntax_details", fail_import)
    summary = build_sqlite_database(edition=EDITION, cache_dir=cache_dir)

    assert (
        "PS3.5 transfer syntax import skipped: injected import failure"
        in summary.warnings
    )
    assert summary.metrics.parse_warnings_by_part is not None
    assert summary.metrics.parse_warnings_by_part["PS3.5"] >= 1
    connection = _connect(summary.db_path)
    try:
        element = element_usage(connection, name="Modality", edition=EDITION)
        assert element.result is not None
    finally:
        connection.close()


def test_sop_classes_import_without_links_when_ps33_is_missing(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_parts(
        cache_dir,
        {
            "PS3.4": "synthetic_ps3_4_sop_classes_docbook.xml",
            "PS3.6": "synthetic_ps3_6_registry_docbook.xml",
        },
    )

    summary = build_sqlite_database(edition=EDITION, cache_dir=cache_dir)

    assert summary.metrics.sop_classes == 2
    with _connect(summary.db_path) as connection:
        links = connection.execute("SELECT count(*) FROM sop_class_iod").fetchone()
    assert links[0] == 0


def test_successful_force_build_replaces_previous_database(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_artifacts(cache_dir)
    target = tmp_path / "kb.sqlite"
    target.write_bytes(b"previous database")
    summary = build_sqlite_database(
        edition=EDITION,
        cache_dir=cache_dir,
        db_path=target,
        force=True,
    )
    assert summary.db_path == target
    connection = _connect(target)
    try:
        assert (
            element_usage(connection, name="Modality", edition=EDITION).result
            is not None
        )
    finally:
        connection.close()
    assert list(tmp_path.glob(".kb.sqlite-*")) == []
