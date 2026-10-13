"""Local SQLite knowledge-base build orchestration."""

from __future__ import annotations

import os
import sqlite3
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from tempfile import TemporaryDirectory

from dicom_kb.db.importers import (
    ImportSummary,
    import_attribute_value_terms,
    import_build_metadata,
    import_coded_concepts,
    import_context_groups,
    import_dicom_media_types,
    import_dicomweb_transactions,
    import_docbook_structure,
    import_file_meta_requirements,
    import_manifest,
    import_part03,
    import_part04,
    import_part06,
    import_sr_templates,
    import_transfer_syntax_details,
    import_vr_definitions,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import ParsedDocument, parse_docbook_file
from dicom_kb.ir.models import IOD, ParserWarning
from dicom_kb.metadata import __version__
from dicom_kb.parsers.part03_iods import parse_part03
from dicom_kb.parsers.part04_sop_classes import parse_part04
from dicom_kb.parsers.part05_encoding import (
    parse_part05,
    transfer_syntax_details_from_uid_registry,
)
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from dicom_kb.parsers.part07_messages import parse_part07
from dicom_kb.parsers.part08_network import parse_part08
from dicom_kb.parsers.part10_media_storage import parse_part10
from dicom_kb.parsers.part16_content_mapping import parse_part16
from dicom_kb.parsers.part18_web_services import parse_part18
from dicom_kb.sources.downloader import DEFAULT_CACHE_DIR, EDITION_RE
from dicom_kb.sources.manifest import (
    SourceManifest,
    manifest_path,
    read_manifest,
    utc_now,
)

SCHEMA_VERSION = "8"
DOCBOOK_XML_FORMAT = "docbook_xml"


@dataclass(frozen=True)
class BuildMetrics:
    """Ingestion metrics emitted and persisted after a build."""

    edition: str
    parts_loaded: tuple[str, ...]
    data_elements: int = 0
    uids: int = 0
    iods: int = 0
    modules: int = 0
    macros: int = 0
    iod_module_uses: int = 0
    iod_functional_group_uses: int = 0
    attribute_uses: int = 0
    include_rows_resolved: int = 0
    include_rows_unresolved: int = 0
    sop_classes: int = 0
    conditions: int = 0
    xrefs_total: int = 0
    xrefs_unresolved: int = 0
    parse_warnings: int = 0
    parse_warnings_by_part: dict[str, int] | None = None
    source_refs: int = 0

    @classmethod
    def from_imports(
        cls,
        *,
        edition: str,
        parts_loaded: tuple[str, ...],
        import_summaries: tuple[ImportSummary, ...],
        parse_warnings: int,
        parse_warnings_by_part: dict[str, int] | None = None,
        source_refs: int | None = None,
    ) -> BuildMetrics:
        """Aggregate import summaries into the public metrics shape."""
        warning_counts = dict(parse_warnings_by_part or {})
        for part in parts_loaded:
            warning_counts.setdefault(part, 0)
        return cls(
            edition=edition,
            parts_loaded=parts_loaded,
            data_elements=sum(summary.data_elements for summary in import_summaries),
            uids=sum(summary.uid_registry_entries for summary in import_summaries),
            iods=sum(summary.iods for summary in import_summaries),
            modules=sum(summary.modules for summary in import_summaries),
            macros=sum(summary.macros for summary in import_summaries),
            iod_module_uses=sum(
                summary.iod_module_uses for summary in import_summaries
            ),
            iod_functional_group_uses=sum(
                summary.iod_functional_group_uses for summary in import_summaries
            ),
            attribute_uses=sum(summary.attribute_uses for summary in import_summaries),
            include_rows_resolved=sum(
                summary.include_rows_resolved for summary in import_summaries
            ),
            include_rows_unresolved=sum(
                summary.include_rows_unresolved for summary in import_summaries
            ),
            sop_classes=sum(summary.sop_classes for summary in import_summaries),
            conditions=sum(summary.conditions for summary in import_summaries),
            xrefs_total=sum(summary.xrefs for summary in import_summaries),
            xrefs_unresolved=sum(
                summary.xrefs_unresolved for summary in import_summaries
            ),
            parse_warnings=parse_warnings,
            parse_warnings_by_part=warning_counts,
            source_refs=(
                source_refs
                if source_refs is not None
                else sum(summary.source_refs for summary in import_summaries)
            ),
        )

    def as_jsonable(self) -> dict[str, object]:
        """Return a JSON-serializable metrics object."""
        payload = asdict(self)
        payload["parts_loaded"] = list(self.parts_loaded)
        payload["parse_warnings_by_part"] = dict(
            sorted((self.parse_warnings_by_part or {}).items())
        )
        return payload


@dataclass(frozen=True)
class BuildSummary:
    """Summary emitted after building a local SQLite KB."""

    edition: str
    db_path: Path
    manifest_sha256: str
    import_summaries: tuple[ImportSummary, ...]
    warnings: tuple[str, ...]
    metrics: BuildMetrics

    def as_jsonable(self) -> dict[str, object]:
        """Return a JSON-serializable representation for CLI output."""
        return {
            "edition": self.edition,
            "db_path": str(self.db_path),
            "manifest_sha256": self.manifest_sha256,
            "imports": [asdict(summary) for summary in self.import_summaries],
            "metrics": self.metrics.as_jsonable(),
            "warnings": list(self.warnings),
        }


class BuildError(RuntimeError):
    """Raised when a local knowledge-base build cannot be completed."""


class DatabaseExistsError(BuildError):
    """Raised when a target database exists and force was not requested."""


def default_db_path(cache_dir: Path, edition: str) -> Path:
    """Return the conventional SQLite database path for an edition."""
    return cache_dir / "db" / f"{edition}.sqlite"


def gap_log_path(db_path: Path) -> Path:
    """Return where a build writes the gaps it logged, next to its database."""
    return db_path.with_name(f"{db_path.stem}.gaps.txt")


def latest_edition(cache_dir: Path, *, built: bool) -> str | None:
    """Return the newest edition in the cache: built KBs, or fetched sources."""
    if built:
        candidates = [path.stem for path in (cache_dir / "db").glob("*.sqlite")]
    else:
        candidates = [
            path.parent.name
            for path in (cache_dir / "artifacts").glob("*/manifest.json")
        ]
    editions = [label for label in candidates if EDITION_RE.match(label)]
    return max(editions) if editions else None


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
    if target_path.exists() and not force:
        raise DatabaseExistsError(f"SQLite KB already exists: {target_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    # Stage on the destination filesystem so publication is atomic. Importers
    # commit independently; their partial output must never become the live KB.
    with TemporaryDirectory(
        prefix=f".{target_path.name}-", dir=target_path.parent
    ) as tmp:
        staging_path = Path(tmp) / "build.sqlite"
        summary = _build_staged_database(
            manifest=manifest,
            cache_dir=cache_dir,
            staging_path=staging_path,
            target_path=target_path,
        )
        gap_log_path(target_path).write_text(
            "".join(f"{message}\n" for message in summary.warnings),
            encoding="utf-8",
        )
        if force:
            staging_path.replace(target_path)
        else:
            try:
                os.link(staging_path, target_path)
            except FileExistsError as exc:
                raise DatabaseExistsError(
                    f"SQLite KB already exists: {target_path}"
                ) from exc
        return summary


# Data-shaped failures from one part's parser or importer. The build logs the
# gap and keeps going; storage and I/O errors still abort it.
_RECOVERABLE_ERRORS = (
    ImportError,
    sqlite3.IntegrityError,
    AttributeError,
    IndexError,
    KeyError,
    TypeError,
    ValueError,
)


class _BuildLog:
    """Collect parser warnings and skipped-step gaps, counted per part."""

    def __init__(self) -> None:
        self.messages: list[str] = []
        self.by_part: dict[str, int] = {}

    def add(self, part: str, message: str) -> None:
        self.messages.append(f"{part} {message}")
        self.by_part[part] = self.by_part.get(part, 0) + 1

    def parser_warnings(self, warnings: tuple[ParserWarning, ...]) -> None:
        for warning in warnings:
            self.add(
                warning.part, f"{warning.table_id or 'unknown'}: {warning.message}"
            )

    def step[T](self, part: str, label: str, run: Callable[[], T]) -> T | None:
        """Run one parse or import step, logging a gap instead of aborting."""
        try:
            return run()
        except _RECOVERABLE_ERRORS as exc:
            cause = f" ({exc.__cause__})" if exc.__cause__ is not None else ""
            self.add(part, f"{label} skipped: {exc}{cause}")
            return None


def _build_staged_database(
    *,
    manifest: SourceManifest,
    cache_dir: Path,
    staging_path: Path,
    target_path: Path,
) -> BuildSummary:
    """Build a private database before the caller publishes it."""
    documents = _load_docbook_documents(cache_dir=cache_dir, manifest=manifest)
    edition = manifest.edition
    connection = connect_sqlite(staging_path)
    log = _BuildLog()
    summaries: list[ImportSummary] = []

    def record(summary: ImportSummary | None) -> None:
        if summary is not None:
            summaries.append(summary)

    try:
        apply_migrations(connection)
        import_manifest(connection, manifest)
        for part, document in documents.items():
            record(
                log.step(
                    part,
                    "text import",
                    partial(
                        import_docbook_structure,
                        connection,
                        edition=edition,
                        document=document,
                    ),
                )
            )
        if "PS3.6" in documents:
            _build_part06(connection, edition, documents["PS3.6"], log, record)
        iod_id_by_ref: dict[str, str] = {}
        if "PS3.3" in documents:
            iod_id_by_ref = _build_part03(
                connection, edition, documents["PS3.3"], log, record
            )
        if "PS3.4" in documents:
            _build_part04(
                connection, edition, documents["PS3.4"], iod_id_by_ref, log, record
            )
        if "PS3.5" in documents:
            _build_part05(connection, edition, documents["PS3.5"], log, record)
        if "PS3.7" in documents:
            parsed07 = log.step(
                "PS3.7",
                "parse",
                lambda: parse_part07(documents["PS3.7"], edition=edition),
            )
            if parsed07 is not None:
                log.parser_warnings(parsed07.warnings)
        if "PS3.8" in documents:
            parsed08 = log.step(
                "PS3.8",
                "parse",
                lambda: parse_part08(documents["PS3.8"], edition=edition),
            )
            if parsed08 is not None:
                log.parser_warnings(parsed08.warnings)
        if "PS3.10" in documents:
            _build_part10(connection, edition, documents["PS3.10"], log, record)
        if "PS3.16" in documents:
            _build_part16(connection, edition, documents["PS3.16"], log, record)
        if "PS3.18" in documents:
            _build_part18(connection, edition, documents["PS3.18"], log, record)

        metrics = BuildMetrics.from_imports(
            edition=edition,
            parts_loaded=tuple(sorted(documents)),
            import_summaries=tuple(summaries),
            parse_warnings=len(log.messages),
            parse_warnings_by_part=log.by_part,
            source_refs=_source_ref_count(connection),
        )
        import_build_metadata(
            connection,
            edition=edition,
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
            metrics=metrics.as_jsonable(),
        )
    except (sqlite3.Error, ImportError, OSError) as exc:
        raise BuildError(f"failed to build SQLite KB for {edition}") from exc
    finally:
        connection.close()

    return BuildSummary(
        edition=edition,
        db_path=target_path,
        manifest_sha256=manifest.source_manifest_sha256,
        import_summaries=tuple(summaries),
        warnings=tuple(log.messages),
        metrics=metrics,
    )


_Record = Callable[[ImportSummary | None], None]


def _build_part06(
    connection: sqlite3.Connection,
    edition: str,
    document: ParsedDocument,
    log: _BuildLog,
    record: _Record,
) -> None:
    parsed = log.step("PS3.6", "parse", lambda: parse_part06(document, edition=edition))
    if parsed is None:
        return
    log.parser_warnings(parsed.warnings)
    record(
        log.step(
            "PS3.6",
            "dictionary import",
            lambda: import_part06(
                connection,
                edition=edition,
                data_elements=parsed.data_elements,
                uid_registry_entries=parsed.uid_registry_entries,
            ),
        )
    )
    record(
        log.step(
            "PS3.6",
            "transfer syntax import",
            lambda: import_transfer_syntax_details(
                connection,
                edition=edition,
                transfer_syntax_details=transfer_syntax_details_from_uid_registry(
                    edition=edition,
                    uid_registry_entries=parsed.uid_registry_entries,
                ),
            ),
        )
    )


def _build_part03(
    connection: sqlite3.Connection,
    edition: str,
    document: ParsedDocument,
    log: _BuildLog,
    record: _Record,
) -> dict[str, str]:
    parsed = log.step("PS3.3", "parse", lambda: parse_part03(document, edition=edition))
    if parsed is None:
        return {}
    log.parser_warnings(parsed.warnings)
    imported = log.step(
        "PS3.3",
        "IOD and module import",
        lambda: import_part03(
            connection,
            edition=edition,
            iods=parsed.iods,
            modules=parsed.modules,
            macros=parsed.macros,
            iod_module_uses=parsed.iod_module_uses,
            iod_functional_group_uses=parsed.iod_functional_group_uses,
            attribute_uses=parsed.attribute_uses,
            conditions=parsed.conditions,
        ),
    )
    record(imported)
    record(
        log.step(
            "PS3.3",
            "value term import",
            lambda: import_attribute_value_terms(
                connection, edition=edition, document=document
            ),
        )
    )
    if imported is None:
        return {}
    return {ref: iod.id for iod in parsed.iods for ref in _iod_ref_keys(iod)}


def _build_part04(
    connection: sqlite3.Connection,
    edition: str,
    document: ParsedDocument,
    iod_id_by_ref: dict[str, str],
    log: _BuildLog,
    record: _Record,
) -> None:
    parsed = log.step(
        "PS3.4",
        "parse",
        lambda: parse_part04(document, edition=edition, iod_id_by_ref=iod_id_by_ref),
    )
    if parsed is None:
        return
    log.parser_warnings(parsed.warnings)
    known_iods = {
        str(row["id"])
        for row in connection.execute(
            "SELECT id FROM iod WHERE edition_id = ?", (edition,)
        )
    }
    sop_names = {sop_class.id: sop_class.name for sop_class in parsed.sop_classes}
    edges = []
    for edge in parsed.sop_class_iods:
        if edge.iod_id in known_iods:
            edges.append(edge)
            continue
        log.add(
            "PS3.4",
            f"{edge.source_ref.table_id}: SOP Class "
            f"{sop_names.get(edge.sop_class_id, edge.sop_class_id)!r} links to "
            f"IOD {edge.iod_id!r}, which PS3.3 does not define; link dropped",
        )
    record(
        log.step(
            "PS3.4",
            "SOP Class import",
            lambda: import_part04(
                connection,
                edition=edition,
                service_classes=parsed.service_classes,
                sop_classes=parsed.sop_classes,
                sop_class_iods=edges,
            ),
        )
    )


def _build_part05(
    connection: sqlite3.Connection,
    edition: str,
    document: ParsedDocument,
    log: _BuildLog,
    record: _Record,
) -> None:
    parsed = log.step("PS3.5", "parse", lambda: parse_part05(document, edition=edition))
    if parsed is None:
        return
    log.parser_warnings(parsed.warnings)
    record(
        log.step(
            "PS3.5",
            "VR import",
            lambda: import_vr_definitions(
                connection, edition=edition, vr_definitions=parsed.vr_definitions
            ),
        )
    )


def _build_part10(
    connection: sqlite3.Connection,
    edition: str,
    document: ParsedDocument,
    log: _BuildLog,
    record: _Record,
) -> None:
    parsed = log.step(
        "PS3.10", "parse", lambda: parse_part10(document, edition=edition)
    )
    if parsed is None:
        return
    log.parser_warnings(parsed.warnings)
    record(
        log.step(
            "PS3.10",
            "file meta import",
            lambda: import_file_meta_requirements(
                connection,
                edition=edition,
                file_meta_requirements=parsed.file_meta_requirements,
            ),
        )
    )
    record(
        log.step(
            "PS3.10",
            "media type import",
            lambda: import_dicom_media_types(
                connection, edition=edition, media_types=parsed.media_types
            ),
        )
    )


def _build_part16(
    connection: sqlite3.Connection,
    edition: str,
    document: ParsedDocument,
    log: _BuildLog,
    record: _Record,
) -> None:
    parsed = log.step(
        "PS3.16", "parse", lambda: parse_part16(document, edition=edition)
    )
    if parsed is None:
        return
    log.parser_warnings(parsed.warnings)
    record(
        log.step(
            "PS3.16",
            "SR template import",
            lambda: import_sr_templates(
                connection,
                edition=edition,
                templates=parsed.sr_templates,
                rows=parsed.sr_template_rows,
            ),
        )
    )
    record(
        log.step(
            "PS3.16",
            "context group import",
            lambda: import_context_groups(
                connection,
                edition=edition,
                context_groups=parsed.context_groups,
                rows=parsed.context_group_rows,
            ),
        )
    )
    record(
        log.step(
            "PS3.16",
            "coded concept import",
            lambda: import_coded_concepts(
                connection, edition=edition, coded_concepts=parsed.coded_concepts
            ),
        )
    )


def _build_part18(
    connection: sqlite3.Connection,
    edition: str,
    document: ParsedDocument,
    log: _BuildLog,
    record: _Record,
) -> None:
    parsed = log.step(
        "PS3.18", "parse", lambda: parse_part18(document, edition=edition)
    )
    if parsed is None:
        return
    log.parser_warnings(parsed.warnings)
    record(
        log.step(
            "PS3.18",
            "DICOMweb transaction import",
            lambda: import_dicomweb_transactions(
                connection,
                edition=edition,
                transactions=parsed.dicomweb_transactions,
            ),
        )
    )
    record(
        log.step(
            "PS3.18",
            "media type import",
            lambda: import_dicom_media_types(
                connection, edition=edition, media_types=parsed.media_types
            ),
        )
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


def _source_ref_count(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT count(*) AS count FROM source_ref").fetchone()
    return int(row["count"])


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
