"""Local loading and optional download of official artifacts."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from dicom_kb.sources.checksums import sha256_file
from dicom_kb.sources.edition_resolver import EditionResolver
from dicom_kb.sources.manifest import (
    SourceArtifact,
    SourceManifest,
    utc_now,
    write_manifest,
)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "dicom-standard-kb"


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


def download_artifact(url: str, destination: Path, *, force: bool = False) -> Path:
    """Download an artifact URL into a destination path."""
    if destination.exists() and not force:
        raise ArtifactExistsError(f"artifact already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(url, timeout=60) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    return destination
