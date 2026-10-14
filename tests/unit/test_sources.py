from io import BytesIO
from pathlib import Path

import pytest

from dicom_kb.sources.checksums import sha256_bytes, sha256_file
from dicom_kb.sources.downloader import (
    DEFAULT_DOCBOOK_PARTS,
    DOCBOOK_XML_FORMAT,
    ArtifactRequest,
    OfficialFetchError,
    discover_official_current_edition,
    download_artifact,
    fetch_current_docbook,
    official_artifact_destination,
    official_docbook_xml_url,
    register_local_artifacts,
)
from dicom_kb.sources.manifest import (
    ManifestChecksumError,
    ManifestExistsError,
    read_manifest,
    write_manifest,
)


class _FakeResponse(BytesIO):
    def __init__(self, data: bytes, *, content_length: int | None = None) -> None:
        super().__init__(data)
        self.headers: dict[str, str] = (
            {} if content_length is None else {"Content-Length": str(content_length)}
        )

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()


def test_checksum_file_matches_bytes(tmp_path: Path) -> None:
    artifact = tmp_path / "part06.xml"
    artifact.write_bytes(b"fixture")

    assert sha256_file(artifact) == sha256_bytes(b"fixture")


def test_register_local_artifact_writes_verified_manifest(tmp_path: Path) -> None:
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
                source_url="https://dicom.nema.org/example/part06.xml",
            )
        ],
    )

    assert manifest.edition == "2026b"
    assert manifest.resolved_from == "local"
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


def test_discover_official_current_edition_from_release_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = "https://dicom.example/current/"

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        assert url == base_url
        return _FakeResponse(
            b'<a href="DocBookDICOM2026b_release_docbook_20260327091344.zip">'
            b"docbook</a>"
        )

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)

    assert discover_official_current_edition(base_url) == "2026b"


def test_fetch_official_docbook_artifacts_writes_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_url = "https://dicom.example/current/"
    part_url = official_docbook_xml_url(base_url, "PS3.6")
    responses = {
        base_url: (
            b'<a href="DocBookDICOM2026b_release_docbook_20260327091344.zip">'
            b"docbook</a>"
        ),
        part_url: b"<book><title>Part 6</title></book>",
    }

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        return _FakeResponse(responses[url])

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)

    manifest = fetch_current_docbook(
        parts=("PS3.6",),
        cache_dir=tmp_path / "cache",
        base_url=base_url,
    )

    assert manifest.edition == "2026b"
    assert manifest.resolved_from == "current"
    assert manifest.artifacts[0].source_url == part_url
    assert manifest.artifacts[0].sha256 == sha256_bytes(responses[part_url])
    assert (
        tmp_path
        / "cache"
        / "artifacts"
        / "2026b"
        / "raw"
        / "source"
        / "docbook"
        / "part06"
        / "part06.xml"
    ).read_bytes() == responses[part_url]
    assert (
        read_manifest(tmp_path / "cache" / "artifacts" / "2026b" / "manifest.json")
        == manifest
    )


def test_fetch_official_docbook_artifacts_defaults_to_every_part(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_url = "https://dicom.example/current/"
    responses = {
        base_url: (
            b'<a href="DocBookDICOM2026b_release_docbook_20260327091344.zip">'
            b"docbook</a>"
        ),
        **{
            official_docbook_xml_url(base_url, part): (
                f"<book><title>{part}</title></book>".encode()
            )
            for part in DEFAULT_DOCBOOK_PARTS
        },
    }

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        return _FakeResponse(responses[url])

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)

    manifest = fetch_current_docbook(
        cache_dir=tmp_path / "cache",
        base_url=base_url,
    )

    assert tuple(artifact.part for artifact in manifest.artifacts) == (
        DEFAULT_DOCBOOK_PARTS
    )
    assert len(DEFAULT_DOCBOOK_PARTS) == 20
    assert "PS3.9" not in DEFAULT_DOCBOOK_PARTS
    assert tuple(artifact.local_path for artifact in manifest.artifacts) == tuple(
        official_artifact_destination(
            "2026b",
            part=part,
            artifact_format=DOCBOOK_XML_FORMAT,
        )
        for part in DEFAULT_DOCBOOK_PARTS
    )


def test_register_local_artifacts_rejects_unlabelled_edition(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="edition must look like"):
        register_local_artifacts(
            edition="current", cache_dir=tmp_path / "cache", artifacts=[]
        )


def test_discover_current_edition_refuses_ambiguous_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        return _FakeResponse(
            b'<a href="DocBookDICOM2026c_release_docbook_1.zip">c</a>'
            b'<a href="DocBookDICOM2026d_release_docbook_2.zip">d</a>'
        )

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)

    with pytest.raises(OfficialFetchError, match="single DICOM edition"):
        discover_official_current_edition("https://dicom.example/current/")


def test_download_retries_a_truncated_or_reset_transfer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = b"<book>complete</book>"
    attempts: list[str] = []

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        attempts.append(url)
        if len(attempts) == 1:
            raise ConnectionResetError("Connection reset by peer")
        if len(attempts) == 2:
            return _FakeResponse(body[:5], content_length=len(body))
        return _FakeResponse(body, content_length=len(body))

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)
    monkeypatch.setattr("dicom_kb.sources.downloader.time.sleep", lambda _s: None)

    destination = download_artifact("https://dicom.example/p.xml", tmp_path / "p.xml")

    assert destination.read_bytes() == body
    assert len(attempts) == 3
    assert not (tmp_path / "p.xml.part").exists()


def test_download_gives_up_on_a_transfer_that_keeps_stopping_short(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        return _FakeResponse(b"<bo", content_length=100)

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)
    monkeypatch.setattr("dicom_kb.sources.downloader.time.sleep", lambda _s: None)

    with pytest.raises(OfficialFetchError, match="stopped at 3 of 100 bytes"):
        download_artifact("https://dicom.example/p.xml", tmp_path / "p.xml")
    assert not (tmp_path / "p.xml").exists()
    assert not (tmp_path / "p.xml.part").exists()
