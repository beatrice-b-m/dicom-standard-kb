from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from dicom_kb.build import (
    DatabaseExistsError,
    build_sqlite_database,
    default_db_path,
)
from dicom_kb.query.resolver import (
    lookup_data_element,
    lookup_defined_terms,
    lookup_sop_class,
)
from dicom_kb.sources.downloader import ArtifactRequest, register_local_artifacts
from tests.fixtures_synthetic import FIXTURE_DIR


def _register_synthetic_artifacts(cache_dir: Path) -> None:
    register_local_artifacts(
        edition="2026b",
        cache_dir=cache_dir,
        artifacts=[
            ArtifactRequest(
                part="PS3.3",
                format="docbook_xml",
                source=FIXTURE_DIR / "synthetic_ps3_3_ct_image_docbook.xml",
                destination=(
                    "artifacts/2026b/raw/source/docbook/part03/part03.xml"
                ),
            ),
            ArtifactRequest(
                part="PS3.4",
                format="docbook_xml",
                source=FIXTURE_DIR / "synthetic_ps3_4_sop_classes_docbook.xml",
                destination=(
                    "artifacts/2026b/raw/source/docbook/part04/part04.xml"
                ),
            ),
            ArtifactRequest(
                part="PS3.6",
                format="docbook_xml",
                source=FIXTURE_DIR / "synthetic_ps3_6_registry_docbook.xml",
                destination=(
                    "artifacts/2026b/raw/source/docbook/part06/part06.xml"
                ),
            ),
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

    assert tag_response.status == "ok"
    assert sop_response.status == "ok"
    assert terms_response.status == "ok"
    assert terms_response.result is not None
    assert len(terms_response.result["terms"]) == 2
    assert metadata["schema_version"] == "7"
    payload = json.loads(metadata["metadata_json"])
    assert payload["edition"] == "2026b"
    assert set(payload["source_sha256"]) == {
        "artifacts/2026b/raw/source/docbook/part03/part03.xml",
        "artifacts/2026b/raw/source/docbook/part04/part04.xml",
        "artifacts/2026b/raw/source/docbook/part06/part06.xml",
    }


def test_build_sqlite_database_refuses_existing_db_without_force(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_artifacts(cache_dir)
    build_sqlite_database(edition="2026b", cache_dir=cache_dir)

    with pytest.raises(DatabaseExistsError):
        build_sqlite_database(edition="2026b", cache_dir=cache_dir)
