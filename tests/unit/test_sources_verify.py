from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from dicom_kb.build import build_sqlite_database, default_db_path
from dicom_kb.cli.main import app
from dicom_kb.sources.downloader import ArtifactRequest, register_local_artifacts
from dicom_kb.sources.verify import verify_edition_cache
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


def _build_fixture_cache(tmp_path: Path) -> tuple[Path, Path]:
    cache_dir = tmp_path / "cache"
    _register_synthetic_artifacts(cache_dir)
    summary = build_sqlite_database(edition="2026b", cache_dir=cache_dir)
    return cache_dir, summary.db_path


def test_verify_edition_cache_accepts_fresh_fixture_build(tmp_path: Path) -> None:
    cache_dir, db_path = _build_fixture_cache(tmp_path)

    result = verify_edition_cache(
        edition="2026b",
        cache_dir=cache_dir,
        db_path=db_path,
    )

    assert result.status == "ok"
    assert result.manifest_sha256
    assert {check.status for check in result.artifact_checks} == {"ok"}
    assert result.db_checks.status == "ok"
    assert result.warnings == ()


def test_verify_edition_cache_reports_checksum_mismatch(tmp_path: Path) -> None:
    cache_dir, db_path = _build_fixture_cache(tmp_path)
    artifact_path = cache_dir / "artifacts/2026b/raw/source/docbook/part03/part03.xml"
    artifact_path.write_text("<book>corrupt</book>", encoding="utf-8")

    result = verify_edition_cache(
        edition="2026b",
        cache_dir=cache_dir,
        db_path=db_path,
    )

    assert result.status == "failed"
    assert any(check.status == "checksum_mismatch" for check in result.artifact_checks)
    assert result.db_checks.status == "ok"


def test_verify_edition_cache_reports_missing_artifact(tmp_path: Path) -> None:
    cache_dir, db_path = _build_fixture_cache(tmp_path)
    artifact_path = cache_dir / "artifacts/2026b/raw/source/docbook/part04/part04.xml"
    artifact_path.unlink()

    result = verify_edition_cache(
        edition="2026b",
        cache_dir=cache_dir,
        db_path=db_path,
    )

    assert result.status == "failed"
    assert any(check.status == "missing" for check in result.artifact_checks)
    assert result.db_checks.status == "ok"


def test_verify_edition_cache_warns_when_database_is_missing(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_artifacts(cache_dir)
    db_path = default_db_path(cache_dir, "2026b")

    result = verify_edition_cache(
        edition="2026b",
        cache_dir=cache_dir,
        db_path=db_path,
    )

    assert result.status == "ok"
    assert result.db_checks.status == "missing"
    assert result.warnings == (f"SQLite KB does not exist: {db_path}",)


def test_verify_edition_cache_reports_db_metadata_mismatch(tmp_path: Path) -> None:
    cache_dir, db_path = _build_fixture_cache(tmp_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE build_metadata SET source_manifest_sha256 = ? "
            "WHERE edition_id = ?",
            ("not-the-manifest", "2026b"),
        )

    result = verify_edition_cache(
        edition="2026b",
        cache_dir=cache_dir,
        db_path=db_path,
    )

    assert result.status == "failed"
    assert result.db_checks.status == "metadata_mismatch"
    assert result.db_checks.source_manifest_sha256 == "not-the-manifest"
    assert "does not match" in (result.db_checks.message or "")


def test_cli_verify_outputs_success_json(tmp_path: Path) -> None:
    cache_dir, db_path = _build_fixture_cache(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "verify",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cache_dir),
            "--db",
            str(db_path),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "ok"
    assert payload["edition"] == "2026b"
    assert payload["db_checks"]["status"] == "ok"
    assert {check["status"] for check in payload["artifact_checks"]} == {"ok"}


def test_cli_verify_exits_nonzero_for_failures(tmp_path: Path) -> None:
    cache_dir, db_path = _build_fixture_cache(tmp_path)
    artifact_path = cache_dir / "artifacts/2026b/raw/source/docbook/part06/part06.xml"
    artifact_path.write_text("<book>corrupt</book>", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "verify",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cache_dir),
            "--db",
            str(db_path),
        ],
    )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "failed"
    assert any(
        check["status"] == "checksum_mismatch"
        for check in payload["artifact_checks"]
    )

