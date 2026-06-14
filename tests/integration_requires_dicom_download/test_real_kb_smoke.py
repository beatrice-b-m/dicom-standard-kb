from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from dicom_kb.query.resolver import (
    list_modules_for_iod,
    lookup_data_element,
    lookup_sop_class,
    lookup_uid,
)
from dicom_kb.sources.manifest import SourceManifest, manifest_path

SCHEMA_DIR = Path(__file__).parents[2] / "schemas"


def test_real_build_outputs_exist_and_manifest_matches_schema_shape(
    cache_dir: Path,
    db_path: Path,
    edition: str,
    manifest: SourceManifest,
) -> None:
    assert db_path.exists()
    assert manifest.edition == edition
    assert len(manifest.artifacts) >= 3

    manifest_payload = json.loads(
        manifest_path(cache_dir, edition).read_text(encoding="utf-8")
    )
    schema = json.loads(
        (SCHEMA_DIR / "source_manifest.schema.json").read_text(encoding="utf-8")
    )
    _assert_manifest_schema_shape(manifest_payload, schema)


def test_real_kb_sanity_counts(connection: sqlite3.Connection, edition: str) -> None:
    assert _count(connection, "data_element", edition) > 4000
    assert _count(connection, "uid_registry_entry", edition) > 400
    assert _count(connection, "iod", edition) > 100
    assert _count(connection, "module", edition) > 200


def test_real_kb_resolves_well_known_data_elements_and_uids(
    connection: sqlite3.Connection, edition: str
) -> None:
    modality = lookup_data_element(
        connection, tag_or_keyword="(0008,0060)", edition=edition
    )
    assert modality.status == "ok"
    assert modality.result is not None
    assert modality.result["name"] == "Modality"
    assert modality.result["vr"] == "CS"
    assert modality.result["vm"] == "1"

    little_endian = lookup_uid(
        connection, uid_or_keyword="1.2.840.10008.1.2.1", edition=edition
    )
    assert little_endian.status == "ok"
    assert little_endian.result is not None
    assert little_endian.result["uid_name"] == "Explicit VR Little Endian"
    assert little_endian.result["retired"] is False

    big_endian = lookup_uid(
        connection, uid_or_keyword="1.2.840.10008.1.2.2", edition=edition
    )
    assert big_endian.status == "ok"
    assert big_endian.result is not None
    assert big_endian.result["uid_name"] == "Explicit VR Big Endian"
    assert big_endian.result["retired"] is True


def test_real_kb_resolves_ct_modules_and_sop_class(
    connection: sqlite3.Connection, edition: str
) -> None:
    modules = list_modules_for_iod(connection, iod_name="CT Image", edition=edition)
    assert modules.status == "ok"
    assert modules.result is not None
    module_by_name = {
        module["module_name"]: module for module in modules.result["modules"]
    }
    assert module_by_name["Patient"]["usage"] == "M"
    assert module_by_name["Contrast/Bolus"]["usage"] == "C"

    sop_class = lookup_sop_class(
        connection,
        uid_or_name_or_keyword="1.2.840.10008.5.1.4.1.1.2",
        edition=edition,
    )
    assert sop_class.status == "ok"
    assert sop_class.result is not None
    assert sop_class.result["sop_class"]["name"] == "CT Image Storage"
    assert {
        iod["iod_name"] for iod in sop_class.result["iods"]
    } == {"CT Image"}


def test_real_kb_range_tag_lookup_warns(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = lookup_data_element(
        connection, tag_or_keyword="(6002,3000)", edition=edition
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["tag"] == "(60xx,3000)"
    assert response.warnings == [
        "concrete tag (6002,3000) matched range row (60xx,3000)"
    ]


def _count(connection: sqlite3.Connection, table: str, edition: str) -> int:
    row = connection.execute(
        f"SELECT COUNT(*) AS count FROM {table} WHERE edition_id = ?",
        (edition,),
    ).fetchone()
    return int(row["count"])


def _assert_manifest_schema_shape(
    payload: dict[str, Any], schema: dict[str, Any]
) -> None:
    assert set(payload) == set(schema["properties"])
    for key in schema["required"]:
        assert key in payload
    assert len(payload["artifacts"]) >= schema["properties"]["artifacts"]["minItems"]
    artifact_schema = schema["$defs"]["sourceArtifact"]
    for artifact in payload["artifacts"]:
        assert set(artifact) == set(artifact_schema["properties"])
        for key in artifact_schema["required"]:
            assert key in artifact
