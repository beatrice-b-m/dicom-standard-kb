from io import BytesIO
from pathlib import Path

import pytest

from dicom_kb.sources.checksums import sha256_bytes, sha256_file
from dicom_kb.sources.downloader import (
    CHTML_FORMAT,
    DEFAULT_DOCBOOK_PARTS,
    DOCBOOK_XML_FORMAT,
    HTML_FORMAT,
    PDF_FORMAT,
    TARGETDB_FORMAT,
    ArtifactRequest,
    OfficialFetchError,
    discover_official_archive_editions,
    discover_official_current_edition,
    fetch_official_artifacts,
    fetch_official_docbook_artifacts,
    official_archive_release_url,
    official_artifact_destination,
    official_artifact_url,
    official_chtml_directory_url,
    official_chtml_tree_destination,
    official_docbook_xml_url,
    register_local_artifacts,
)
from dicom_kb.sources.edition_resolver import EditionResolutionError, EditionResolver
from dicom_kb.sources.manifest import (
    ManifestChecksumError,
    ManifestExistsError,
    read_manifest,
    write_manifest,
)


class _FakeResponse(BytesIO):
    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()


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


def test_discover_official_current_edition_from_release_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_url = "https://dicom.example/current/"

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        assert timeout == 60
        assert url == base_url
        return _FakeResponse(
            b'<a href="DocBookDICOM2026b_release_docbook_20260327091344.zip">'
            b"docbook</a>"
        )

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)

    assert discover_official_current_edition(base_url) == "2026b"


def test_discover_official_archive_editions_from_root_listing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_url = "https://dicom.example/dicom/"

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        assert timeout == 60
        assert url == archive_url
        return _FakeResponse(
            b'<a href="2025e/">2025e</a>'
            b'<a href="2026a/">2026a</a>'
            b'<a href="current/">current</a>'
            b'<a href="Final/">Final</a>'
        )

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)

    assert discover_official_archive_editions(archive_url) == {"2025e", "2026a"}


def test_official_artifact_urls_and_destinations_are_format_specific() -> None:
    base_url = "https://dicom.example/current/"

    assert official_artifact_url(
        base_url, part="PS3.6", artifact_format=DOCBOOK_XML_FORMAT
    ) == "https://dicom.example/current/source/docbook/part06/part06.xml"
    assert official_artifact_url(
        base_url, part="PS3.6", artifact_format=PDF_FORMAT
    ) == "https://dicom.example/current/output/pdf/part06.pdf"
    assert official_artifact_url(
        base_url, part="PS3.6", artifact_format=HTML_FORMAT
    ) == "https://dicom.example/current/output/html/part06.html"
    assert official_artifact_url(
        base_url, part="PS3.6", artifact_format="chtml"
    ) == "https://dicom.example/current/output/chtml/part06/PS3.6.html"
    assert official_artifact_url(
        base_url, part="PS3.6", artifact_format=TARGETDB_FORMAT
    ) == "https://dicom.example/current/output/html/targetdb/PS3_06_target.db"

    assert official_artifact_destination(
        "2026b", part="PS3.6", artifact_format=PDF_FORMAT
    ) == "artifacts/2026b/raw/pdf/part06.pdf"
    assert official_artifact_destination(
        "2026b", part="PS3.6", artifact_format=TARGETDB_FORMAT
    ) == "artifacts/2026b/raw/targetdb/PS3_06_target.db"
    assert official_archive_release_url(
        "https://dicom.example/dicom/",
        edition="2025e",
    ) == "https://dicom.example/dicom/2025e/"


def test_official_chtml_tree_destination_rejects_unsafe_paths() -> None:
    with pytest.raises(OfficialFetchError, match="unsafe"):
        official_chtml_tree_destination(
            "2026b",
            part="PS3.6",
            relative_path="../part05/PS3.5.html",
        )


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
        assert timeout == 60
        return _FakeResponse(responses[url])

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)

    manifest = fetch_official_docbook_artifacts(
        edition="current",
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
    assert read_manifest(
        tmp_path / "cache" / "artifacts" / "2026b" / "manifest.json"
    ) == manifest


def test_fetch_official_docbook_artifacts_defaults_to_v2_parts(
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
        assert timeout == 60
        return _FakeResponse(responses[url])

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)

    manifest = fetch_official_docbook_artifacts(
        edition="current",
        cache_dir=tmp_path / "cache",
        base_url=base_url,
    )

    assert tuple(artifact.part for artifact in manifest.artifacts) == (
        DEFAULT_DOCBOOK_PARTS
    )
    assert tuple(artifact.local_path for artifact in manifest.artifacts) == tuple(
        official_artifact_destination(
            "2026b",
            part=part,
            artifact_format=DOCBOOK_XML_FORMAT,
        )
        for part in DEFAULT_DOCBOOK_PARTS
    )


def test_fetch_official_artifacts_writes_requested_formats(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_url = "https://dicom.example/current/"
    docbook_url = official_artifact_url(
        base_url, part="PS3.6", artifact_format=DOCBOOK_XML_FORMAT
    )
    pdf_url = official_artifact_url(
        base_url, part="PS3.6", artifact_format=PDF_FORMAT
    )
    targetdb_url = official_artifact_url(
        base_url, part="PS3.6", artifact_format=TARGETDB_FORMAT
    )
    responses = {
        base_url: (
            b'<a href="DocBookDICOM2026b_release_docbook_20260327091344.zip">'
            b"docbook</a>"
        ),
        docbook_url: b"<book><title>Part 6</title></book>",
        pdf_url: b"%PDF-1.7\n",
        targetdb_url: b"SQLite format 3\000",
    }

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        assert timeout == 60
        return _FakeResponse(responses[url])

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)

    manifest = fetch_official_artifacts(
        edition="current",
        parts=("PS3.6",),
        formats=(DOCBOOK_XML_FORMAT, PDF_FORMAT, TARGETDB_FORMAT),
        cache_dir=tmp_path / "cache",
        base_url=base_url,
    )

    assert [artifact.format for artifact in manifest.artifacts] == [
        DOCBOOK_XML_FORMAT,
        PDF_FORMAT,
        TARGETDB_FORMAT,
    ]
    assert [artifact.source_url for artifact in manifest.artifacts] == [
        docbook_url,
        pdf_url,
        targetdb_url,
    ]
    assert (
        tmp_path / "cache" / "artifacts" / "2026b" / "raw" / "pdf" / "part06.pdf"
    ).read_bytes() == responses[pdf_url]
    assert (
        tmp_path
        / "cache"
        / "artifacts"
        / "2026b"
        / "raw"
        / "targetdb"
        / "PS3_06_target.db"
    ).read_bytes() == responses[targetdb_url]


def test_fetch_official_artifacts_mirrors_chtml_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_url = "https://dicom.example/current/"
    chtml_root = official_chtml_directory_url(base_url, part="PS3.6")
    entry_url = f"{chtml_root}PS3.6.html"
    chapter_url = f"{chtml_root}chapter/"
    section_url = f"{chapter_url}sect_A.html"
    responses = {
        base_url: (
            b'<a href="DocBookDICOM2026b_release_docbook_20260327091344.zip">'
            b"docbook</a>"
        ),
        chtml_root: (
            b'<a href="../">Parent</a>'
            b'<a href="PS3.6.html">entry</a>'
            b'<a href="chapter/">chapter</a>'
            b'<a href="?C=N">sort</a>'
            b'<a href="https://other.example/elsewhere.html">external</a>'
        ),
        entry_url: b"<html>Part 6 entry</html>",
        chapter_url: (
            b'<a href="../">Parent</a>'
            b'<a href="sect_A.html">section</a>'
        ),
        section_url: b"<html>Section A</html>",
    }

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        assert timeout == 60
        return _FakeResponse(responses[url])

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)

    manifest = fetch_official_artifacts(
        edition="current",
        parts=("PS3.6",),
        formats=(CHTML_FORMAT,),
        cache_dir=tmp_path / "cache",
        base_url=base_url,
        mirror_chtml_tree=True,
    )

    assert [artifact.source_url for artifact in manifest.artifacts] == [
        entry_url,
        section_url,
    ]
    assert [artifact.local_path for artifact in manifest.artifacts] == [
        "artifacts/2026b/raw/chtml/part06/PS3.6.html",
        "artifacts/2026b/raw/chtml/part06/chapter/sect_A.html",
    ]
    assert [artifact.format for artifact in manifest.artifacts] == [
        CHTML_FORMAT,
        CHTML_FORMAT,
    ]
    assert (
        tmp_path
        / "cache"
        / "artifacts"
        / "2026b"
        / "raw"
        / "chtml"
        / "part06"
        / "chapter"
        / "sect_A.html"
    ).read_bytes() == responses[section_url]


def test_fetch_official_artifacts_uses_archive_for_concrete_edition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current_url = "https://dicom.example/current/"
    archive_url = "https://dicom.example/dicom/"
    release_url = official_archive_release_url(archive_url, edition="2025e")
    part_url = official_docbook_xml_url(release_url, "PS3.6")
    responses = {
        archive_url: b'<a href="2025e/">2025e</a><a href="2026a/">2026a</a>',
        part_url: b"<book><title>Archived Part 6</title></book>",
    }

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        assert timeout == 60
        assert url != current_url
        return _FakeResponse(responses[url])

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)

    manifest = fetch_official_artifacts(
        edition="2025e",
        parts=("PS3.6",),
        cache_dir=tmp_path / "cache",
        base_url=current_url,
        archive_base_url=archive_url,
    )

    assert manifest.edition == "2025e"
    assert manifest.resolved_from == "2025e"
    assert manifest.artifacts[0].source_url == part_url
    assert (
        tmp_path
        / "cache"
        / "artifacts"
        / "2025e"
        / "raw"
        / "source"
        / "docbook"
        / "part06"
        / "part06.xml"
    ).read_bytes() == responses[part_url]


def test_fetch_official_artifacts_rejects_unknown_format(tmp_path: Path) -> None:
    with pytest.raises(OfficialFetchError, match="artifact format"):
        fetch_official_artifacts(
            edition="current",
            parts=("PS3.6",),
            formats=("docx",),
            cache_dir=tmp_path / "cache",
            base_url="https://dicom.example/current/",
        )


def test_fetch_official_docbook_rejects_unlisted_concrete_edition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_url = "https://dicom.example/dicom/"

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        assert url == archive_url
        return _FakeResponse(b'<a href="2026b/">2026b</a>')

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)

    with pytest.raises(OfficialFetchError, match="not listed"):
        fetch_official_docbook_artifacts(
            edition="2025e",
            parts=("PS3.6",),
            cache_dir=tmp_path / "cache",
            archive_base_url=archive_url,
        )
