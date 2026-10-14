from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from dicom_kb.build import (
    SCHEMA_VERSION,
    BuildMetrics,
    DatabaseExistsError,
    build_sqlite_database,
    default_db_path,
    gap_log_path,
)
from dicom_kb.db.importers import ImportSummary
from dicom_kb.query.resolver import (
    attribute_values,
    code_lookup,
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
    "PS3.16": "synthetic_ps3_16_content_mapping_docbook.xml",
}


def _register_synthetic_parts(
    cache_dir: Path, fixtures: dict[str, str] = SYNTHETIC_PARTS
) -> None:
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


def test_build_publishes_a_kb_every_tool_can_answer_from(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_parts(cache_dir)

    summary = build_sqlite_database(edition=EDITION, cache_dir=cache_dir)

    assert summary.db_path == default_db_path(cache_dir, EDITION)
    assert summary.metrics.parts_loaded == tuple(sorted(SYNTHETIC_PARTS))
    with _connect(summary.db_path) as connection:
        answers = {
            "element": element_usage(connection, name="Modality", edition=EDITION),
            "iod": iod_modules(connection, name="CT Image Storage", edition=EDITION),
            "values": attribute_values(connection, name="PatientName", edition=EDITION),
            "code": code_lookup(connection, query="TID 1500", edition=EDITION),
            "read": read_standard(
                connection, reference="ExplicitVRLittleEndian", edition=EDITION
            ),
        }
    assert {name: answer.status for name, answer in answers.items()} == dict.fromkeys(
        answers, "ok"
    )


def test_build_records_its_schema_and_sources(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_parts(cache_dir)

    summary = build_sqlite_database(edition=EDITION, cache_dir=cache_dir)

    with _connect(summary.db_path) as connection:
        metadata = connection.execute(
            "SELECT metadata_json, schema_version FROM build_metadata"
        ).fetchone()
    assert metadata["schema_version"] == SCHEMA_VERSION
    payload = json.loads(metadata["metadata_json"])
    assert set(payload["source_sha256"]) == {
        official_artifact_destination(
            EDITION, part=part, artifact_format=DOCBOOK_XML_FORMAT
        )
        for part in SYNTHETIC_PARTS
    }
    assert payload["metrics"] == summary.metrics.as_jsonable()


def test_build_gap_log_attributes_every_warning_to_a_part(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_parts(cache_dir)

    summary = build_sqlite_database(edition=EDITION, cache_dir=cache_dir)

    # The fixture has a malformed tag row the parser must report, not drop.
    assert any("skipped malformed tag row" in warning for warning in summary.warnings)
    by_part = summary.metrics.parse_warnings_by_part or {}
    assert sum(by_part.values()) == len(summary.warnings)
    assert all(warning.split()[0] in by_part for warning in summary.warnings)
    assert gap_log_path(summary.db_path).read_text(encoding="utf-8").splitlines() == (
        list(summary.warnings)
    )


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


def test_build_sqlite_database_refuses_existing_db_without_force(
    tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "cache"
    _register_synthetic_parts(cache_dir)
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
    _register_synthetic_parts(cache_dir)
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
    _register_synthetic_parts(cache_dir)

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
    _register_synthetic_parts(cache_dir)
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
