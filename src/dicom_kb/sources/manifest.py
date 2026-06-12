"""Artifact manifest models and persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dicom_kb.metadata import LEGAL_NOTICE, __version__
from dicom_kb.sources.checksums import sha256_bytes


class SourceArtifact(BaseModel):
    """A downloaded or locally registered official source artifact."""

    model_config = ConfigDict(frozen=True)

    part: str
    format: str
    local_path: str
    source_url: str | None = None
    sha256: str
    byte_size: int


class SourceManifest(BaseModel):
    """Immutable manifest for one concrete edition acquisition."""

    model_config = ConfigDict(frozen=True)

    edition: str
    resolved_from: str
    acquired_at: datetime
    artifacts: tuple[SourceArtifact, ...]
    parser_version: str = Field(
        default_factory=lambda: f"dicom-kb-parser/{__version__}"
    )
    source_manifest_sha256: str = ""
    notice: str = LEGAL_NOTICE

    def with_digest(self) -> SourceManifest:
        """Return a copy with the digest computed over canonical content."""
        payload = self.model_dump(mode="json", exclude={"source_manifest_sha256"})
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return self.model_copy(update={"source_manifest_sha256": sha256_bytes(encoded)})


class ManifestExistsError(FileExistsError):
    """Raised when writing would overwrite an existing immutable manifest."""


class ManifestChecksumError(ValueError):
    """Raised when manifest checksum verification fails."""


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(UTC)


def manifest_path(cache_dir: Path, edition: str) -> Path:
    """Return the manifest path for a concrete edition."""
    return cache_dir / "artifacts" / edition / "manifest.json"


def write_manifest(
    manifest: SourceManifest, cache_dir: Path, *, force: bool = False
) -> Path:
    """Write a manifest, preserving immutability unless force is explicit."""
    path = manifest_path(cache_dir, manifest.edition)
    if path.exists() and not force:
        raise ManifestExistsError(f"manifest already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    complete = manifest.with_digest()
    path.write_text(
        json.dumps(complete.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def read_manifest(path: Path) -> SourceManifest:
    """Read and verify a manifest from disk."""
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    digest = data.get("source_manifest_sha256")
    manifest = SourceManifest.model_validate(data)
    expected = manifest.model_copy(update={"source_manifest_sha256": ""}).with_digest()
    if digest != expected.source_manifest_sha256:
        raise ManifestChecksumError(f"manifest checksum mismatch: {path}")
    return manifest
