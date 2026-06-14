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
    assert any("PS3.10 table_10-2" in warning for warning in summary.warnings)
    assert any("PS3.16 table_16-2" in warning for warning in summary.warnings)
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
        "source_refs",
    }
    assert metrics["edition"] == "2026b"
    assert metrics["parts_loaded"] == sorted(DEFAULT_DOCBOOK_PARTS)
    assert metrics["parse_warnings"] == len(summary.warnings)
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
    assert len(v2_tables) == 11
    assert set(payload["source_sha256"]) == {
        official_artifact_destination(
            "2026b",
            part=part,
            artifact_format=DOCBOOK_XML_FORMAT,
        )
        for part in DEFAULT_DOCBOOK_PARTS
    }
    assert payload["metrics"] == metrics


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
