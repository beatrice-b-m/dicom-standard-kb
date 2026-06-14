"""Local cache and SQLite build verification."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dicom_kb.sources.checksums import sha256_file
from dicom_kb.sources.manifest import (
    ManifestChecksumError,
    SourceManifest,
    manifest_path,
    read_manifest,
)


@dataclass(frozen=True)
class ArtifactCheck:
    """Verification result for one cached source artifact."""

    path: str
    part: str
    format: str
    expected_sha256: str
    actual_sha256: str | None
    status: str

    def as_jsonable(self) -> dict[str, object]:
        return {
            "path": self.path,
            "part": self.part,
            "format": self.format,
            "expected_sha256": self.expected_sha256,
            "actual_sha256": self.actual_sha256,
            "status": self.status,
        }


@dataclass(frozen=True)
class DatabaseChecks:
    """Verification result for the optional SQLite build."""

    path: str
    status: str
    edition: str | None = None
    source_manifest_sha256: str | None = None
    schema_version: str | None = None
    message: str | None = None

    def as_jsonable(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "path": self.path,
            "status": self.status,
        }
        if self.edition is not None:
            payload["edition"] = self.edition
        if self.source_manifest_sha256 is not None:
            payload["source_manifest_sha256"] = self.source_manifest_sha256
        if self.schema_version is not None:
            payload["schema_version"] = self.schema_version
        if self.message is not None:
            payload["message"] = self.message
        return payload


@dataclass(frozen=True)
class VerificationResult:
    """Structured result emitted by `dicom-kb verify`."""

    status: str
    edition: str
    manifest_sha256: str | None
    artifact_checks: tuple[ArtifactCheck, ...]
    db_checks: DatabaseChecks
    warnings: tuple[str, ...]

    def as_jsonable(self) -> dict[str, object]:
        return {
            "status": self.status,
            "edition": self.edition,
            "manifest_sha256": self.manifest_sha256,
            "artifact_checks": [
                artifact.as_jsonable() for artifact in self.artifact_checks
            ],
            "db_checks": self.db_checks.as_jsonable(),
            "warnings": list(self.warnings),
        }

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def verify_edition_cache(
    *,
    edition: str,
    cache_dir: Path,
    db_path: Path,
) -> VerificationResult:
    """Verify a cached edition manifest, source artifacts, and optional DB."""
    try:
        manifest = read_manifest(manifest_path(cache_dir, edition))
    except FileNotFoundError:
        return _manifest_failure(
            edition=edition,
            db_path=db_path,
            message=f"manifest does not exist: {manifest_path(cache_dir, edition)}",
        )
    except (ManifestChecksumError, ValueError) as exc:
        return _manifest_failure(edition=edition, db_path=db_path, message=str(exc))

    artifact_checks = _verify_artifacts(cache_dir=cache_dir, manifest=manifest)
    db_checks, db_warnings = _verify_database(
        db_path=db_path,
        manifest=manifest,
    )
    has_failures = any(check.status != "ok" for check in artifact_checks) or (
        db_checks.status not in {"ok", "missing"}
    )
    return VerificationResult(
        status="failed" if has_failures else "ok",
        edition=manifest.edition,
        manifest_sha256=manifest.source_manifest_sha256,
        artifact_checks=tuple(artifact_checks),
        db_checks=db_checks,
        warnings=db_warnings,
    )


def _manifest_failure(
    *, edition: str, db_path: Path, message: str
) -> VerificationResult:
    return VerificationResult(
        status="failed",
        edition=edition,
        manifest_sha256=None,
        artifact_checks=(),
        db_checks=DatabaseChecks(path=str(db_path), status="not_checked"),
        warnings=(message,),
    )


def _verify_artifacts(
    *, cache_dir: Path, manifest: SourceManifest
) -> list[ArtifactCheck]:
    checks: list[ArtifactCheck] = []
    for artifact in manifest.artifacts:
        path = cache_dir / artifact.local_path
        if not path.exists():
            checks.append(
                ArtifactCheck(
                    path=artifact.local_path,
                    part=artifact.part,
                    format=artifact.format,
                    expected_sha256=artifact.sha256,
                    actual_sha256=None,
                    status="missing",
                )
            )
            continue
        actual = sha256_file(path)
        checks.append(
            ArtifactCheck(
                path=artifact.local_path,
                part=artifact.part,
                format=artifact.format,
                expected_sha256=artifact.sha256,
                actual_sha256=actual,
                status="ok" if actual == artifact.sha256 else "checksum_mismatch",
            )
        )
    return checks


def _verify_database(
    *, db_path: Path, manifest: SourceManifest
) -> tuple[DatabaseChecks, tuple[str, ...]]:
    if not db_path.exists():
        return (
            DatabaseChecks(
                path=str(db_path),
                status="missing",
                message="SQLite KB does not exist; artifact verification completed",
            ),
            (f"SQLite KB does not exist: {db_path}",),
        )
    try:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT edition_id, source_manifest_sha256, schema_version, metadata_json
            FROM build_metadata
            WHERE edition_id = ?
            """,
            (manifest.edition,),
        ).fetchone()
    except sqlite3.Error as exc:
        return (
            DatabaseChecks(
                path=str(db_path),
                status="error",
                message=f"SQLite metadata check failed: {exc}",
            ),
            (),
        )
    finally:
        if "connection" in locals():
            connection.close()

    if row is None:
        return (
            DatabaseChecks(
                path=str(db_path),
                status="metadata_missing",
                message=f"build metadata for edition {manifest.edition} was not found",
            ),
            (),
        )

    metadata = _metadata_json(row["metadata_json"])
    row_edition = str(row["edition_id"])
    row_manifest_sha = str(row["source_manifest_sha256"])
    if row_edition != manifest.edition:
        return (
            DatabaseChecks(
                path=str(db_path),
                status="metadata_mismatch",
                edition=row_edition,
                source_manifest_sha256=row_manifest_sha,
                schema_version=str(row["schema_version"]),
                message=(
                    f"DB metadata edition {row_edition} does not match manifest "
                    f"edition {manifest.edition}"
                ),
            ),
            (),
        )
    if row_manifest_sha != manifest.source_manifest_sha256:
        return (
            DatabaseChecks(
                path=str(db_path),
                status="metadata_mismatch",
                edition=row_edition,
                source_manifest_sha256=row_manifest_sha,
                schema_version=str(row["schema_version"]),
                message="DB source manifest SHA-256 does not match the manifest",
            ),
            (),
        )
    if metadata.get("edition") not in {None, manifest.edition}:
        return (
            DatabaseChecks(
                path=str(db_path),
                status="metadata_mismatch",
                edition=str(metadata["edition"]),
                source_manifest_sha256=row_manifest_sha,
                schema_version=str(row["schema_version"]),
                message="DB metadata JSON edition does not match the manifest",
            ),
            (),
        )
    return (
        DatabaseChecks(
            path=str(db_path),
            status="ok",
            edition=row_edition,
            source_manifest_sha256=row_manifest_sha,
            schema_version=str(row["schema_version"]),
        ),
        (),
    )


def _metadata_json(value: str) -> dict[str, Any]:
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
