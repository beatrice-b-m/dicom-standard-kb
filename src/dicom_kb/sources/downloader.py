"""Local loading and optional download of official artifacts."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import cast
from urllib.parse import urljoin
from urllib.request import urlopen

from dicom_kb.sources.checksums import sha256_file
from dicom_kb.sources.edition_resolver import EditionResolver, ResolvedEdition
from dicom_kb.sources.manifest import (
    SourceArtifact,
    SourceManifest,
    utc_now,
    write_manifest,
)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "dicom-standard-kb"
DEFAULT_DICOM_CURRENT_BASE_URL = "https://dicom.nema.org/medical/dicom/current/"
DOCBOOK_XML_FORMAT = "docbook_xml"
V1_DOCBOOK_PARTS = ("PS3.3", "PS3.4", "PS3.6")
OFFICIAL_EDITION_RE = re.compile(r"DocBookDICOM(20\d{2}[a-z])_release_docbook_")
RELEASE_NOTES_EDITION_RE = re.compile(r"releasenotes_(20\d{2}[a-z])\.xml")


@dataclass(frozen=True)
class ArtifactRequest:
    """An artifact to register into the local cache."""

    part: str
    format: str
    source: Path | str
    destination: str
    source_url: str | None = None


class ArtifactExistsError(FileExistsError):
    """Raised when a cached artifact would be overwritten."""


class OfficialFetchError(RuntimeError):
    """Raised when official artifact discovery cannot proceed safely."""


def register_local_artifacts(
    *,
    edition: str,
    artifacts: list[ArtifactRequest],
    cache_dir: Path = DEFAULT_CACHE_DIR,
    current_edition: str | None = None,
    force: bool = False,
) -> SourceManifest:
    """Copy local artifacts into the cache and write an immutable manifest."""
    resolved = EditionResolver(current_edition=current_edition).resolve(edition)
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
        edition=resolved.edition,
        resolved_from=resolved.resolved_from,
        acquired_at=utc_now(),
        artifacts=tuple(entries),
    )
    write_manifest(manifest, cache_dir, force=force)
    return manifest.with_digest()


def fetch_official_docbook_artifacts(
    *,
    edition: str,
    parts: tuple[str, ...] = V1_DOCBOOK_PARTS,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    base_url: str = DEFAULT_DICOM_CURRENT_BASE_URL,
    force: bool = False,
) -> SourceManifest:
    """Download official current DocBook XML artifacts into the local cache."""
    resolved = resolve_official_current_edition(edition=edition, base_url=base_url)
    entries: list[SourceArtifact] = []
    for part in parts:
        normalized_part = _normalize_docbook_part(part)
        url = official_docbook_xml_url(base_url, normalized_part)
        destination = cache_dir / _docbook_destination(
            resolved.edition, normalized_part
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
        edition=resolved.edition,
        resolved_from=resolved.resolved_from,
        acquired_at=utc_now(),
        artifacts=tuple(entries),
    )
    write_manifest(manifest, cache_dir, force=force)
    return manifest.with_digest()


def resolve_official_current_edition(
    *, edition: str, base_url: str = DEFAULT_DICOM_CURRENT_BASE_URL
) -> ResolvedEdition:
    """Resolve an edition using the official current release directory."""
    current_edition = discover_official_current_edition(base_url)
    if edition.strip().lower() == "current":
        return ResolvedEdition(edition=current_edition, resolved_from="current")

    resolved = EditionResolver().resolve(edition)
    if resolved.edition != current_edition:
        raise OfficialFetchError(
            "official fetch currently downloads from the DICOM current release; "
            f"requested {resolved.edition!r}, but current is {current_edition!r}"
        )
    return resolved


def discover_official_current_edition(
    base_url: str = DEFAULT_DICOM_CURRENT_BASE_URL,
) -> str:
    """Discover the concrete edition label from the official current directory."""
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
            "could not determine a single concrete DICOM edition from official "
            f"current release metadata: {sorted(editions)!r}"
        )
    return next(iter(editions))


def official_docbook_xml_url(base_url: str, part: str) -> str:
    """Return the official current DocBook XML URL for a DICOM part."""
    normalized_part = _normalize_docbook_part(part)
    part_number = normalized_part.removeprefix("PS3.").zfill(2)
    return urljoin(
        _ensure_trailing_slash(base_url),
        f"source/docbook/part{part_number}/part{part_number}.xml",
    )


def download_artifact(url: str, destination: Path, *, force: bool = False) -> Path:
    """Download an artifact URL into a destination path."""
    if destination.exists() and not force:
        raise ArtifactExistsError(f"artifact already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=60) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    return destination


class _HrefParser(HTMLParser):
    """Collect href attributes from simple directory listings."""

    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
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


def _docbook_destination(edition: str, part: str) -> str:
    part_number = part.removeprefix("PS3.").zfill(2)
    return (
        f"artifacts/{edition}/raw/source/docbook/part{part_number}/"
        f"part{part_number}.xml"
    )


def _normalize_docbook_part(part: str) -> str:
    normalized = part.strip().upper()
    if not normalized.startswith("PS3."):
        normalized = f"PS3.{normalized}"
    part_number = normalized.removeprefix("PS3.")
    if not part_number.isdigit():
        raise OfficialFetchError(f"DICOM part must look like PS3.6, got {part!r}")
    return f"PS3.{int(part_number)}"
