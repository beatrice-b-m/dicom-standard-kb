"""Local loading and optional download of official artifacts."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from posixpath import normpath
from typing import cast
from urllib.parse import unquote, urldefrag, urljoin, urlparse
from urllib.request import urlopen

from dicom_kb.sources.checksums import sha256_file
from dicom_kb.sources.edition_resolver import (
    EDITION_RE,
    EditionResolver,
    ResolvedEdition,
)
from dicom_kb.sources.manifest import (
    SourceArtifact,
    SourceManifest,
    utc_now,
    write_manifest,
)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "dicom-standard-kb"
DEFAULT_DICOM_CURRENT_BASE_URL = "https://dicom.nema.org/medical/dicom/current/"
DEFAULT_DICOM_ARCHIVE_BASE_URL = "https://dicom.nema.org/medical/dicom/"
DOCBOOK_XML_FORMAT = "docbook_xml"
PDF_FORMAT = "pdf"
HTML_FORMAT = "html"
CHTML_FORMAT = "chtml"
TARGETDB_FORMAT = "targetdb"
OFFICIAL_ARTIFACT_FORMATS = (
    DOCBOOK_XML_FORMAT,
    PDF_FORMAT,
    HTML_FORMAT,
    CHTML_FORMAT,
    TARGETDB_FORMAT,
)
V1_DOCBOOK_PARTS = ("PS3.3", "PS3.4", "PS3.6")
V2_DOCBOOK_PARTS = (
    "PS3.3",
    "PS3.4",
    "PS3.5",
    "PS3.6",
    "PS3.7",
    "PS3.8",
    "PS3.10",
    "PS3.16",
    "PS3.18",
)
DEFAULT_DOCBOOK_PARTS = V2_DOCBOOK_PARTS
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
    parts: tuple[str, ...] = DEFAULT_DOCBOOK_PARTS,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    base_url: str = DEFAULT_DICOM_CURRENT_BASE_URL,
    archive_base_url: str = DEFAULT_DICOM_ARCHIVE_BASE_URL,
    force: bool = False,
) -> SourceManifest:
    """Download official DocBook XML artifacts into the local cache."""
    return fetch_official_artifacts(
        edition=edition,
        parts=parts,
        formats=(DOCBOOK_XML_FORMAT,),
        cache_dir=cache_dir,
        base_url=base_url,
        archive_base_url=archive_base_url,
        force=force,
    )


def fetch_official_artifacts(
    *,
    edition: str,
    parts: tuple[str, ...] = DEFAULT_DOCBOOK_PARTS,
    formats: tuple[str, ...] = (DOCBOOK_XML_FORMAT,),
    cache_dir: Path = DEFAULT_CACHE_DIR,
    base_url: str = DEFAULT_DICOM_CURRENT_BASE_URL,
    archive_base_url: str = DEFAULT_DICOM_ARCHIVE_BASE_URL,
    mirror_chtml_tree: bool = False,
    force: bool = False,
) -> SourceManifest:
    """Download selected official artifacts into the local cache."""
    normalized_formats = tuple(
        _normalize_official_artifact_format(artifact_format)
        for artifact_format in formats
    )
    resolved, release_base_url = resolve_official_release(
        edition=edition,
        current_base_url=base_url,
        archive_base_url=archive_base_url,
    )
    entries: list[SourceArtifact] = []
    for part in parts:
        normalized_part = _normalize_docbook_part(part)
        for normalized_format in normalized_formats:
            if normalized_format == CHTML_FORMAT and mirror_chtml_tree:
                entries.extend(
                    fetch_official_chtml_tree_artifacts(
                        edition=resolved.edition,
                        part=normalized_part,
                        release_base_url=release_base_url,
                        cache_dir=cache_dir,
                        force=force,
                    )
                )
                continue
            url = official_artifact_url(
                release_base_url,
                part=normalized_part,
                artifact_format=normalized_format,
            )
            destination = cache_dir / official_artifact_destination(
                resolved.edition,
                part=normalized_part,
                artifact_format=normalized_format,
            )
            download_artifact(url, destination, force=force)
            entries.append(
                SourceArtifact(
                    part=normalized_part,
                    format=normalized_format,
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


def fetch_official_chtml_tree_artifacts(
    *,
    edition: str,
    part: str,
    release_base_url: str,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    force: bool = False,
) -> list[SourceArtifact]:
    """Recursively mirror one official CHTML part directory into the cache."""
    normalized_part = _normalize_docbook_part(part)
    root_url = official_chtml_directory_url(release_base_url, part=normalized_part)
    root_destination = Path(
        official_chtml_tree_destination(
            edition,
            part=normalized_part,
            relative_path=".",
        )
    )
    queue = [root_url]
    seen_directories: set[str] = set()
    seen_files: set[str] = set()
    artifacts: list[SourceArtifact] = []

    while queue:
        directory_url = queue.pop(0)
        if directory_url in seen_directories:
            continue
        seen_directories.add(directory_url)
        listing = _read_url_text(directory_url)
        parser = _HrefParser()
        parser.feed(listing)
        for href in sorted(parser.hrefs):
            child_url = _normalize_mirror_url(directory_url, href)
            if child_url is None or not _is_url_within_root(child_url, root_url):
                continue
            relative_path = _relative_mirror_path(root_url, child_url)
            if relative_path is None:
                continue
            if child_url.endswith("/"):
                queue.append(child_url)
                continue
            if child_url in seen_files:
                continue
            seen_files.add(child_url)
            destination = cache_dir / root_destination / relative_path
            download_artifact(child_url, destination, force=force)
            artifacts.append(
                SourceArtifact(
                    part=normalized_part,
                    format=CHTML_FORMAT,
                    local_path=str(destination.relative_to(cache_dir)),
                    source_url=child_url,
                    sha256=sha256_file(destination),
                    byte_size=destination.stat().st_size,
                )
            )
    if not artifacts:
        raise OfficialFetchError(
            f"no CHTML files were discovered under {root_url!r}"
        )
    return artifacts


def resolve_official_release(
    *,
    edition: str,
    current_base_url: str = DEFAULT_DICOM_CURRENT_BASE_URL,
    archive_base_url: str = DEFAULT_DICOM_ARCHIVE_BASE_URL,
) -> tuple[ResolvedEdition, str]:
    """Resolve an edition and the official release directory to fetch from."""
    if edition.strip().lower() == "current":
        resolved = resolve_official_current_edition(
            edition=edition,
            base_url=current_base_url,
        )
        return resolved, _ensure_trailing_slash(current_base_url)

    resolved = EditionResolver().resolve(edition)
    archive_editions = discover_official_archive_editions(archive_base_url)
    if resolved.edition not in archive_editions:
        raise OfficialFetchError(
            f"requested DICOM edition {resolved.edition!r} is not listed in the "
            f"official archive at {_ensure_trailing_slash(archive_base_url)!r}"
        )
    return resolved, official_archive_release_url(
        archive_base_url,
        edition=resolved.edition,
    )


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


def discover_official_archive_editions(
    base_url: str = DEFAULT_DICOM_ARCHIVE_BASE_URL,
) -> set[str]:
    """Discover concrete edition labels listed in the official archive."""
    listing = _read_url_text(_ensure_trailing_slash(base_url))
    parser = _HrefParser()
    parser.feed(listing)
    editions: set[str] = set()
    for href in parser.hrefs:
        candidate = href.strip().strip("/")
        if EDITION_RE.match(candidate):
            editions.add(candidate.lower())
    return editions


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


def official_archive_release_url(base_url: str, *, edition: str) -> str:
    """Return the official archive release URL for a concrete edition."""
    resolved = EditionResolver().resolve(edition)
    return urljoin(_ensure_trailing_slash(base_url), f"{resolved.edition}/")


def official_docbook_xml_url(base_url: str, part: str) -> str:
    """Return the official current DocBook XML URL for a DICOM part."""
    return official_artifact_url(
        base_url,
        part=part,
        artifact_format=DOCBOOK_XML_FORMAT,
    )


def official_artifact_url(base_url: str, *, part: str, artifact_format: str) -> str:
    """Return the official current artifact URL for a DICOM part and format."""
    normalized_part = _normalize_docbook_part(part)
    normalized_format = _normalize_official_artifact_format(artifact_format)
    part_number = normalized_part.removeprefix("PS3.").zfill(2)
    base = _ensure_trailing_slash(base_url)
    if normalized_format == DOCBOOK_XML_FORMAT:
        path = f"source/docbook/part{part_number}/part{part_number}.xml"
    elif normalized_format == PDF_FORMAT:
        path = f"output/pdf/part{part_number}.pdf"
    elif normalized_format == HTML_FORMAT:
        path = f"output/html/part{part_number}.html"
    elif normalized_format == CHTML_FORMAT:
        path = f"output/chtml/part{part_number}/{normalized_part}.html"
    elif normalized_format == TARGETDB_FORMAT:
        path = f"output/html/targetdb/PS3_{part_number}_target.db"
    else:  # pragma: no cover - guarded by normalization.
        raise OfficialFetchError(f"unsupported artifact format: {artifact_format!r}")
    return urljoin(base, path)


def official_chtml_directory_url(base_url: str, *, part: str) -> str:
    """Return the official CHTML directory URL for a DICOM part."""
    normalized_part = _normalize_docbook_part(part)
    part_number = normalized_part.removeprefix("PS3.").zfill(2)
    return urljoin(_ensure_trailing_slash(base_url), f"output/chtml/part{part_number}/")


def official_artifact_destination(
    edition: str, *, part: str, artifact_format: str
) -> str:
    """Return the cache-relative path for an official artifact."""
    normalized_part = _normalize_docbook_part(part)
    normalized_format = _normalize_official_artifact_format(artifact_format)
    part_number = normalized_part.removeprefix("PS3.").zfill(2)
    if normalized_format == DOCBOOK_XML_FORMAT:
        return (
            f"artifacts/{edition}/raw/source/docbook/part{part_number}/"
            f"part{part_number}.xml"
        )
    if normalized_format == PDF_FORMAT:
        return f"artifacts/{edition}/raw/pdf/part{part_number}.pdf"
    if normalized_format == HTML_FORMAT:
        return f"artifacts/{edition}/raw/html/part{part_number}.html"
    if normalized_format == CHTML_FORMAT:
        return (
            f"artifacts/{edition}/raw/chtml/part{part_number}/"
            f"{normalized_part}.html"
        )
    if normalized_format == TARGETDB_FORMAT:
        return f"artifacts/{edition}/raw/targetdb/PS3_{part_number}_target.db"
    raise OfficialFetchError(f"unsupported artifact format: {artifact_format!r}")


def official_chtml_tree_destination(
    edition: str, *, part: str, relative_path: str
) -> str:
    """Return a cache-relative destination for a mirrored CHTML tree member."""
    normalized_part = _normalize_docbook_part(part)
    part_number = normalized_part.removeprefix("PS3.").zfill(2)
    normalized_relative_path = _safe_relative_path(relative_path)
    base = f"artifacts/{edition}/raw/chtml/part{part_number}"
    if normalized_relative_path == ".":
        return base
    return f"{base}/{normalized_relative_path}"


def _normalize_official_artifact_format(artifact_format: str) -> str:
    normalized = artifact_format.strip().lower().replace("-", "_")
    if normalized == "xml":
        normalized = DOCBOOK_XML_FORMAT
    if normalized not in OFFICIAL_ARTIFACT_FORMATS:
        raise OfficialFetchError(
            "official artifact format must be one of "
            f"{', '.join(OFFICIAL_ARTIFACT_FORMATS)}, got {artifact_format!r}"
        )
    return normalized


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


def _normalize_mirror_url(directory_url: str, href: str) -> str | None:
    stripped = href.strip()
    if not stripped or stripped.startswith(("#", "?")):
        return None
    joined, _fragment = urldefrag(
        urljoin(_ensure_trailing_slash(directory_url), stripped)
    )
    parsed = urlparse(joined)
    if parsed.query:
        return None
    return joined


def _is_url_within_root(url: str, root_url: str) -> bool:
    parsed_url = urlparse(url)
    parsed_root = urlparse(root_url)
    if (parsed_url.scheme, parsed_url.netloc) != (
        parsed_root.scheme,
        parsed_root.netloc,
    ):
        return False
    root_path = _ensure_trailing_slash(parsed_root.path)
    return parsed_url.path == root_path or parsed_url.path.startswith(root_path)


def _relative_mirror_path(root_url: str, url: str) -> str | None:
    root_path = _ensure_trailing_slash(urlparse(root_url).path)
    target_path = urlparse(url).path
    if not target_path.startswith(root_path):
        return None
    relative_path = unquote(target_path.removeprefix(root_path))
    if not relative_path:
        return None
    return _safe_relative_path(relative_path)


def _safe_relative_path(relative_path: str) -> str:
    normalized = normpath(relative_path.strip("/"))
    if normalized.startswith("../") or normalized == ".." or normalized.startswith("/"):
        raise OfficialFetchError(f"unsafe relative artifact path: {relative_path!r}")
    return normalized


def _ensure_trailing_slash(url: str) -> str:
    return url if url.endswith("/") else f"{url}/"


def _docbook_destination(edition: str, part: str) -> str:
    return official_artifact_destination(
        edition,
        part=part,
        artifact_format=DOCBOOK_XML_FORMAT,
    )


def _normalize_docbook_part(part: str) -> str:
    normalized = part.strip().upper()
    if not normalized.startswith("PS3."):
        normalized = f"PS3.{normalized}"
    part_number = normalized.removeprefix("PS3.")
    if not part_number.isdigit():
        raise OfficialFetchError(f"DICOM part must look like PS3.6, got {part!r}")
    return f"PS3.{int(part_number)}"
