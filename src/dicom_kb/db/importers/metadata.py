"""Edition manifests and build provenance persistence."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import datetime

from dicom_kb.sources.manifest import SourceManifest


def import_manifest(connection: sqlite3.Connection, manifest: SourceManifest) -> None:
    """Import edition and artifact metadata from a source manifest."""
    with connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO standard_edition (
              id, source_label, resolved_from, acquired_at, is_default, manifest_sha256
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                manifest.edition,
                f"DICOM PS3 {manifest.edition}",
                manifest.resolved_from,
                manifest.acquired_at.isoformat(),
                0,
                manifest.source_manifest_sha256,
            ),
        )
        for artifact in manifest.artifacts:
            artifact_id = (
                f"{manifest.edition}.{artifact.part}.{artifact.format}."
                f"{artifact.sha256[:12]}"
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO source_artifact (
                  id, edition_id, part, format, local_path, source_url, sha256,
                  byte_size, acquired_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    manifest.edition,
                    artifact.part,
                    artifact.format,
                    artifact.local_path,
                    artifact.source_url,
                    artifact.sha256,
                    artifact.byte_size,
                    manifest.acquired_at.isoformat(),
                ),
            )


def import_build_metadata(
    connection: sqlite3.Connection,
    *,
    edition: str,
    built_at: datetime,
    parser_version: str,
    schema_version: str,
    source_manifest_sha256: str,
    source_urls: Iterable[str],
    source_sha256: dict[str, str],
    repository_commit: str | None = None,
    metrics: dict[str, object] | None = None,
) -> None:
    """Record reproducible build metadata for a generated SQLite database."""
    metadata: dict[str, object] = {
        "edition": edition,
        "source_urls": tuple(source_urls),
        "source_sha256": source_sha256,
        "built_at": built_at.isoformat(),
        "parser_version": parser_version,
        "schema_version": schema_version,
        "repository_commit": repository_commit,
    }
    if metrics is not None:
        metadata["metrics"] = metrics
    with connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO build_metadata (
              edition_id, built_at, parser_version, schema_version,
              source_manifest_sha256, repository_commit, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                edition,
                built_at.isoformat(),
                parser_version,
                schema_version,
                source_manifest_sha256,
                repository_commit,
                json.dumps(metadata, sort_keys=True, separators=(",", ":")),
            ),
        )
