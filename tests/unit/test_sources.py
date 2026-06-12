from pathlib import Path

import pytest

from dicom_kb.sources.checksums import sha256_bytes, sha256_file
from dicom_kb.sources.downloader import ArtifactRequest, register_local_artifacts
from dicom_kb.sources.edition_resolver import EditionResolutionError, EditionResolver
from dicom_kb.sources.manifest import (
    ManifestChecksumError,
    ManifestExistsError,
    read_manifest,
    write_manifest,
)


def test_resolver_requires_concrete_current() -> None:
    with pytest.raises(EditionResolutionError):
        EditionResolver().resolve("current")


def test_resolver_maps_current_to_configured_concrete_edition() -> None:
    resolved = EditionResolver(current_edition="2026b").resolve("current")

    assert resolved.edition == "2026b"
    assert resolved.resolved_from == "current"


def test_checksum_file_matches_bytes(tmp_path: Path) -> None:
    artifact = tmp_path / "part06.xml"
    artifact.write_bytes(b"fixture")

    assert sha256_file(artifact) == sha256_bytes(b"fixture")


def test_register_local_artifact_writes_verified_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source.xml"
    source.write_text("<book/>", encoding="utf-8")

    manifest = register_local_artifacts(
        edition="current",
        current_edition="2026b",
        cache_dir=tmp_path / "cache",
        artifacts=[
            ArtifactRequest(
                part="PS3.6",
                format="docbook_xml",
                source=source,
                destination="artifacts/2026b/raw/source/docbook/part06/part06.xml",
                source_url="https://dicom.nema.org/example/part06.xml",
            )
        ],
    )

    assert manifest.edition == "2026b"
    assert manifest.resolved_from == "current"
    assert manifest.source_manifest_sha256
    assert manifest.artifacts[0].sha256 == sha256_bytes(b"<book/>")

    stored = read_manifest(tmp_path / "cache" / "artifacts" / "2026b" / "manifest.json")
    assert stored == manifest


def test_manifest_is_immutable_without_force(tmp_path: Path) -> None:
    source = tmp_path / "source.xml"
    source.write_text("<book/>", encoding="utf-8")
    manifest = register_local_artifacts(
        edition="2026b",
        cache_dir=tmp_path / "cache",
        artifacts=[
            ArtifactRequest(
                part="PS3.6",
                format="docbook_xml",
                source=source,
                destination="artifacts/2026b/raw/source/docbook/part06/part06.xml",
            )
        ],
    )

    with pytest.raises(ManifestExistsError):
        write_manifest(manifest, tmp_path / "cache")


def test_manifest_checksum_mismatch_fails(tmp_path: Path) -> None:
    source = tmp_path / "source.xml"
    source.write_text("<book/>", encoding="utf-8")
    register_local_artifacts(
        edition="2026b",
        cache_dir=tmp_path / "cache",
        artifacts=[
            ArtifactRequest(
                part="PS3.6",
                format="docbook_xml",
                source=source,
                destination="artifacts/2026b/raw/source/docbook/part06/part06.xml",
            )
        ],
    )
    path = tmp_path / "cache" / "artifacts" / "2026b" / "manifest.json"
    text = path.read_text(encoding="utf-8").replace("PS3.6", "PS3.3")
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ManifestChecksumError):
        read_manifest(path)
