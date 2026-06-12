"""Local SQLite knowledge-base build orchestration."""

from __future__ import annotations

import sqlite3
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from dicom_kb.db.importers import (
    ImportSummary,
    import_build_metadata,
    import_docbook_structure,
    import_manifest,
    import_part03,
    import_part04,
    import_part06,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import ParsedDocument, parse_docbook_file
from dicom_kb.ir.models import IOD, ParserWarning
from dicom_kb.metadata import __version__
from dicom_kb.parsers.part03_iods import parse_part03
from dicom_kb.parsers.part04_sop_classes import parse_part04
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from dicom_kb.sources.downloader import DEFAULT_CACHE_DIR
from dicom_kb.sources.manifest import (
    SourceManifest,
    manifest_path,
    read_manifest,
    utc_now,
)

SCHEMA_VERSION = "6"
DOCBOOK_XML_FORMAT = "docbook_xml"


@dataclass(frozen=True)
class BuildSummary:
    """Summary emitted after building a local SQLite KB."""

    edition: str
    db_path: Path
    manifest_sha256: str
    import_summaries: tuple[ImportSummary, ...]
    warnings: tuple[str, ...]

    def as_jsonable(self) -> dict[str, object]:
        """Return a JSON-serializable representation for CLI output."""
        return {
            "edition": self.edition,
            "db_path": str(self.db_path),
            "manifest_sha256": self.manifest_sha256,
            "imports": [asdict(summary) for summary in self.import_summaries],
            "warnings": list(self.warnings),
        }


class BuildError(RuntimeError):
    """Raised when a local knowledge-base build cannot be completed."""


class DatabaseExistsError(BuildError):
    """Raised when a target database exists and force was not requested."""


def default_db_path(cache_dir: Path, edition: str) -> Path:
    """Return the conventional SQLite database path for an edition."""
    return cache_dir / "db" / f"{edition}.sqlite"


def build_sqlite_database(
    *,
    edition: str,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    db_path: Path | None = None,
    force: bool = False,
) -> BuildSummary:
    """Build an edition-pinned SQLite KB from cached manifest artifacts."""
    manifest = read_manifest(manifest_path(cache_dir, edition))
    target_path = (
        db_path if db_path is not None else default_db_path(cache_dir, manifest.edition)
    )
    if target_path.exists():
        if not force:
            raise DatabaseExistsError(f"SQLite KB already exists: {target_path}")
        target_path.unlink()

    documents = _load_docbook_documents(cache_dir=cache_dir, manifest=manifest)
    connection = connect_sqlite(target_path)
    warnings: list[str] = []
    summaries: list[ImportSummary] = []
    try:
        apply_migrations(connection)
        import_manifest(connection, manifest)
        for document in documents.values():
            summaries.append(
                import_docbook_structure(
                    connection,
                    edition=manifest.edition,
                    document=document,
                )
            )

        if "PS3.6" in documents:
            parsed_part06 = parse_part06(
                documents["PS3.6"], edition=manifest.edition
            )
            warnings.extend(_warning_messages(parsed_part06.warnings))
            summaries.append(
                import_part06(
                    connection,
                    edition=manifest.edition,
                    data_elements=parsed_part06.data_elements,
                    uid_registry_entries=parsed_part06.uid_registry_entries,
                )
            )
        iod_id_by_ref: dict[str, str] = {}
        if "PS3.3" in documents:
            parsed_part03 = parse_part03(
                documents["PS3.3"], edition=manifest.edition
            )
            iod_id_by_ref = {
                ref: iod.id
                for iod in parsed_part03.iods
                for ref in _iod_ref_keys(iod)
            }
            warnings.extend(_warning_messages(parsed_part03.warnings))
            summaries.append(
                import_part03(
                    connection,
                    edition=manifest.edition,
                    iods=parsed_part03.iods,
                    modules=parsed_part03.modules,
                    macros=parsed_part03.macros,
                    iod_module_uses=parsed_part03.iod_module_uses,
                    iod_functional_group_uses=parsed_part03.iod_functional_group_uses,
                    attribute_uses=parsed_part03.attribute_uses,
                )
            )
        if "PS3.4" in documents:
            parsed_part04 = parse_part04(
                documents["PS3.4"],
                edition=manifest.edition,
                iod_id_by_ref=iod_id_by_ref,
            )
            warnings.extend(_warning_messages(parsed_part04.warnings))
            summaries.append(
                import_part04(
                    connection,
                    edition=manifest.edition,
                    service_classes=parsed_part04.service_classes,
                    sop_classes=parsed_part04.sop_classes,
                    sop_class_iods=parsed_part04.sop_class_iods,
                )
            )

        import_build_metadata(
            connection,
            edition=manifest.edition,
            built_at=utc_now(),
            parser_version=__version__,
            schema_version=SCHEMA_VERSION,
            source_manifest_sha256=manifest.source_manifest_sha256,
            source_urls=(
                artifact.source_url
                for artifact in manifest.artifacts
                if artifact.source_url is not None
            ),
            source_sha256={
                artifact.local_path: artifact.sha256 for artifact in manifest.artifacts
            },
            repository_commit=_repository_commit(),
        )
    except (sqlite3.Error, ImportError, OSError) as exc:
        raise BuildError(f"failed to build SQLite KB for {manifest.edition}") from exc
    finally:
        connection.close()

    return BuildSummary(
        edition=manifest.edition,
        db_path=target_path,
        manifest_sha256=manifest.source_manifest_sha256,
        import_summaries=tuple(summaries),
        warnings=tuple(warnings),
    )


def _load_docbook_documents(
    *, cache_dir: Path, manifest: SourceManifest
) -> dict[str, ParsedDocument]:
    documents: dict[str, ParsedDocument] = {}
    for artifact in manifest.artifacts:
        if artifact.format != DOCBOOK_XML_FORMAT:
            continue
        path = cache_dir / artifact.local_path
        documents[artifact.part] = parse_docbook_file(path, part=artifact.part)
    return documents


def _warning_messages(warnings: tuple[ParserWarning, ...]) -> tuple[str, ...]:
    return tuple(
        f"{warning.part} {warning.table_id or 'unknown'}: {warning.message}"
        for warning in warnings
    )


def _iod_ref_keys(iod: IOD) -> tuple[str, ...]:
    section = iod.section
    candidates = [
        section,
        iod.source_ref.section,
        iod.source_ref.table_id,
        iod.source_ref.xml_id,
    ]
    if isinstance(iod.source_ref.section, str) and iod.source_ref.section.startswith(
        "sect_"
    ):
        parts = iod.source_ref.section.rsplit(".", maxsplit=1)
        if len(parts) == 2:
            candidates.append(parts[0])
    return tuple(dict.fromkeys(ref for ref in candidates if isinstance(ref, str)))


def _repository_commit() -> str | None:
    root = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None
