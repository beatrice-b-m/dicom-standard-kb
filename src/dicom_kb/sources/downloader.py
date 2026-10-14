"""Fetch the current DocBook release from NEMA, or register local copies."""

from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import cast
from urllib.parse import urljoin
from urllib.request import urlopen

from dicom_kb.sources.checksums import sha256_file
from dicom_kb.sources.manifest import (
    SourceArtifact,
    SourceManifest,
    utc_now,
    write_manifest,
)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "dicom-standard-kb"
DEFAULT_DICOM_CURRENT_BASE_URL = "https://dicom.nema.org/medical/dicom/current/"
DOCBOOK_XML_FORMAT = "docbook_xml"
# Every part published in the current edition; PS3.9 and PS3.13 are retired.
DEFAULT_DOCBOOK_PARTS = tuple(
    f"PS3.{number}" for number in (*range(1, 9), 10, 11, 12, *range(14, 23))
)
DOWNLOAD_ATTEMPTS = 4
EDITION_RE = re.compile(r"^20\d{2}[a-z]$")
OFFICIAL_EDITION_RE = re.compile(r"DocBookDICOM(20\d{2}[a-z])_release_docbook_")
RELEASE_NOTES_EDITION_RE = re.compile(r"releasenotes_(20\d{2}[a-z])\.xml")


@dataclass(frozen=True)
class ArtifactRequest:
    """A local DocBook file to register into the cache."""

    part: str
    format: str
    source: Path | str
    destination: str
    source_url: str | None = None


class ArtifactExistsError(FileExistsError):
    """Raised when a cached artifact would be overwritten."""


class OfficialFetchError(RuntimeError):
    """Raised when the official release cannot be fetched."""


def register_local_artifacts(
    *,
    edition: str,
    artifacts: list[ArtifactRequest],
    cache_dir: Path = DEFAULT_CACHE_DIR,
    force: bool = False,
) -> SourceManifest:
    """Copy local DocBook files into the cache under an edition label."""
    edition = edition.strip().lower()
    if not EDITION_RE.match(edition):
        raise ValueError(f"edition must look like '2026d', got {edition!r}")
    entries: list[SourceArtifact] = []
    for request in artifacts:
        source = Path(request.source)
        destination = cache_dir / request.destination
        if destination.exists() and not force:
            raise ArtifactExistsError(f"artifact already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        entries.append(
            SourceArtifact(
                part=request.part,
                format=request.format,
                local_path=str(destination.relative_to(cache_dir)),
                source_url=request.source_url,
                sha256=sha256_file(destination),
                byte_size=destination.stat().st_size,
            )
        )

    manifest = SourceManifest(
        edition=edition,
        resolved_from="local",
        acquired_at=utc_now(),
        artifacts=tuple(entries),
    )
    write_manifest(manifest, cache_dir, force=force)
    return manifest.with_digest()


def fetch_current_docbook(
    *,
    parts: tuple[str, ...] = DEFAULT_DOCBOOK_PARTS,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    base_url: str = DEFAULT_DICOM_CURRENT_BASE_URL,
    force: bool = False,
) -> SourceManifest:
    """Download the current edition's DocBook XML for each part."""
    edition = discover_official_current_edition(base_url)
    entries: list[SourceArtifact] = []
    for part in parts:
        normalized_part = _normalize_docbook_part(part)
        url = official_docbook_xml_url(base_url, normalized_part)
        destination = cache_dir / official_artifact_destination(
            edition, part=normalized_part
        )
        download_artifact(url, destination, force=force)
        entries.append(
            SourceArtifact(
                part=normalized_part,
                format=DOCBOOK_XML_FORMAT,
                local_path=str(destination.relative_to(cache_dir)),
                source_url=url,
                sha256=sha256_file(destination),
                byte_size=destination.stat().st_size,
            )
        )

    manifest = SourceManifest(
        edition=edition,
        resolved_from="current",
        acquired_at=utc_now(),
        artifacts=tuple(entries),
    )
    write_manifest(manifest, cache_dir, force=force)
    return manifest.with_digest()


def discover_official_current_edition(
    base_url: str = DEFAULT_DICOM_CURRENT_BASE_URL,
) -> str:
    """Read the edition label (e.g. 2026d) from the current release listing."""
    listing = _read_url_text(_ensure_trailing_slash(base_url))
    editions = _edition_labels_from_listing(listing)
    if not editions:
        release_notes_url = urljoin(
            _ensure_trailing_slash(base_url),
            "source/docbook/releasenotes/",
        )
        editions = _edition_labels_from_listing(_read_url_text(release_notes_url))
    if len(editions) != 1:
        raise OfficialFetchError(
            "could not determine a single DICOM edition from the current release "
            f"listing at {base_url!r}: {sorted(editions)!r}"
        )
    return next(iter(editions))


def official_docbook_xml_url(base_url: str, part: str) -> str:
    """Return the DocBook XML URL for a DICOM part under a release base URL."""
    part_number = _normalize_docbook_part(part).removeprefix("PS3.").zfill(2)
    return urljoin(
        _ensure_trailing_slash(base_url),
        f"source/docbook/part{part_number}/part{part_number}.xml",
    )


def official_artifact_destination(
    edition: str, *, part: str, artifact_format: str = DOCBOOK_XML_FORMAT
) -> str:
    """Return the cache-relative path for a part's DocBook XML."""
    if artifact_format != DOCBOOK_XML_FORMAT:
        raise OfficialFetchError(f"unsupported artifact format: {artifact_format!r}")
    part_number = _normalize_docbook_part(part).removeprefix("PS3.").zfill(2)
    return (
        f"artifacts/{edition}/raw/source/docbook/part{part_number}/"
        f"part{part_number}.xml"
    )


def download_artifact(url: str, destination: Path, *, force: bool = False) -> Path:
    """Download an artifact URL into a destination path."""
    if destination.exists() and not force:
        raise ArtifactExistsError(f"artifact already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(f"{destination.name}.part")
    # NEMA connections sometimes reset or close early without an error; a
    # short file would otherwise fail much later as malformed XML.
    problem = ""
    for attempt in range(DOWNLOAD_ATTEMPTS):
        if attempt:
            time.sleep(2**attempt)
        try:
            with urlopen(url, timeout=60) as response, partial.open("wb") as handle:
                shutil.copyfileobj(response, handle)
                expected = response.headers.get("Content-Length")
        except OSError as exc:
            problem = str(exc)
            continue
        received = partial.stat().st_size
        if expected is None or int(expected) == received:
            partial.replace(destination)
            return destination
        problem = f"stopped at {received} of {expected} bytes"
    partial.unlink(missing_ok=True)
    raise OfficialFetchError(
        f"download of {url} failed after {DOWNLOAD_ATTEMPTS} attempts: {problem}"
    )


class _HrefParser(HTMLParser):
    """Collect href attributes from simple directory listings."""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.hrefs.append(value)


def _edition_labels_from_listing(html: str) -> set[str]:
    parser = _HrefParser()
    parser.feed(html)
    editions: set[str] = set()
    for href in parser.hrefs:
        for pattern in (OFFICIAL_EDITION_RE, RELEASE_NOTES_EDITION_RE):
            match = pattern.search(href)
            if match:
                editions.add(match.group(1).lower())
    return editions


def _read_url_text(url: str) -> str:
    with urlopen(url, timeout=60) as response:
        data = cast(bytes, response.read())
        return data.decode("utf-8", errors="replace")


def _ensure_trailing_slash(url: str) -> str:
    return url if url.endswith("/") else f"{url}/"


def _normalize_docbook_part(part: str) -> str:
    normalized = part.strip().upper()
    if not normalized.startswith("PS3."):
        normalized = f"PS3.{normalized}"
    part_number = normalized.removeprefix("PS3.")
    if not part_number.isdigit():
        raise OfficialFetchError(f"DICOM part must look like PS3.6, got {part!r}")
    return f"PS3.{int(part_number)}"
