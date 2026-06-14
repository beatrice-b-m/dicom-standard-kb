"""Local SQLite knowledge-base build orchestration."""

from __future__ import annotations

import sqlite3
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from dicom_kb.db.importers import (
    ImportSummary,
    import_attribute_value_terms,
    import_build_metadata,
    import_dicom_media_types,
    import_dicomweb_transactions,
    import_docbook_structure,
    import_file_meta_requirements,
    import_manifest,
    import_part03,
    import_part04,
    import_part06,
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
from dicom_kb.parsers.part06_data_dictionary import Part06ParseResult, parse_part06
from dicom_kb.parsers.part07_messages import parse_part07
from dicom_kb.parsers.part08_network import parse_part08
from dicom_kb.parsers.part10_media_storage import parse_part10
from dicom_kb.parsers.part16_content_mapping import parse_part16
from dicom_kb.parsers.part18_web_services import parse_part18
from dicom_kb.sources.downloader import DEFAULT_CACHE_DIR
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
    """Section 16 ingestion metrics emitted and persisted after a build."""

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
    source_refs: int = 0

    @classmethod
    def from_imports(
        cls,
        *,
        edition: str,
        parts_loaded: tuple[str, ...],
        import_summaries: tuple[ImportSummary, ...],
        parse_warnings: int,
        source_refs: int | None = None,
    ) -> BuildMetrics:
        """Aggregate import summaries into the public Section 16 shape."""
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
        return payload


@dataclass(frozen=True)
class QualityGateSettings:
    """Optional build quality thresholds."""

    max_unresolved_xref_rate: float | None = None
    max_unresolved_include_rate: float | None = None
    max_parse_warnings: int | None = None
    allow_gate_failures: bool = False


@dataclass(frozen=True)
class BuildSummary:
    """Summary emitted after building a local SQLite KB."""

    edition: str
    db_path: Path
    manifest_sha256: str
    import_summaries: tuple[ImportSummary, ...]
    warnings: tuple[str, ...]
    metrics: BuildMetrics
    gate_failures: tuple[str, ...] = ()

    def as_jsonable(self) -> dict[str, object]:
        """Return a JSON-serializable representation for CLI output."""
        return {
            "edition": self.edition,
            "db_path": str(self.db_path),
            "manifest_sha256": self.manifest_sha256,
            "imports": [asdict(summary) for summary in self.import_summaries],
            "metrics": self.metrics.as_jsonable(),
            "gate_failures": list(self.gate_failures),
            "warnings": list(self.warnings),
        }


class BuildError(RuntimeError):
    """Raised when a local knowledge-base build cannot be completed."""


class DatabaseExistsError(BuildError):
    """Raised when a target database exists and force was not requested."""


class BuildQualityGateError(BuildError):
    """Raised when a build completes but configured quality gates fail."""

    def __init__(self, summary: BuildSummary) -> None:
        self.summary = summary
        super().__init__(
            "build quality gates failed: " + "; ".join(summary.gate_failures)
        )


def default_db_path(cache_dir: Path, edition: str) -> Path:
    """Return the conventional SQLite database path for an edition."""
    return cache_dir / "db" / f"{edition}.sqlite"


def evaluate_quality_gates(
    metrics: BuildMetrics, settings: QualityGateSettings
) -> tuple[str, ...]:
    """Return configured quality-gate failure messages."""
    failures: list[str] = []
    if settings.max_unresolved_xref_rate is not None:
        rate = _rate(metrics.xrefs_unresolved, metrics.xrefs_total)
        if rate > settings.max_unresolved_xref_rate:
            failures.append(
                "unresolved xref rate "
                f"{rate:.6g} exceeds configured maximum "
                f"{settings.max_unresolved_xref_rate:.6g}"
            )
    if settings.max_unresolved_include_rate is not None:
        include_total = (
            metrics.include_rows_resolved + metrics.include_rows_unresolved
        )
        rate = _rate(metrics.include_rows_unresolved, include_total)
        if rate > settings.max_unresolved_include_rate:
            failures.append(
                "unresolved include-row rate "
                f"{rate:.6g} exceeds configured maximum "
                f"{settings.max_unresolved_include_rate:.6g}"
            )
    if (
        settings.max_parse_warnings is not None
        and metrics.parse_warnings > settings.max_parse_warnings
    ):
        failures.append(
            "parse warning count "
            f"{metrics.parse_warnings} exceeds configured maximum "
            f"{settings.max_parse_warnings}"
        )
    return tuple(failures)


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def build_sqlite_database(
    *,
    edition: str,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    db_path: Path | None = None,
    force: bool = False,
    quality_gates: QualityGateSettings | None = None,
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
    metrics: BuildMetrics | None = None
    gate_failures: tuple[str, ...] = ()
    gate_settings = quality_gates or QualityGateSettings()
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

        parsed_part06: Part06ParseResult | None = None
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
            summaries.append(
                import_transfer_syntax_details(
                    connection,
                    edition=manifest.edition,
                    transfer_syntax_details=(
                        transfer_syntax_details_from_uid_registry(
                            edition=manifest.edition,
                            uid_registry_entries=parsed_part06.uid_registry_entries,
                        )
                    ),
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
                    conditions=parsed_part03.conditions,
                )
            )
            summaries.append(
                import_attribute_value_terms(
                    connection,
                    edition=manifest.edition,
                    document=documents["PS3.3"],
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
        if "PS3.5" in documents:
            parsed_part05 = parse_part05(
                documents["PS3.5"], edition=manifest.edition
            )
            warnings.extend(_warning_messages(parsed_part05.warnings))
            summaries.append(
                import_vr_definitions(
                    connection,
                    edition=manifest.edition,
                    vr_definitions=parsed_part05.vr_definitions,
                )
            )
        if "PS3.7" in documents:
            parsed_part07 = parse_part07(
                documents["PS3.7"], edition=manifest.edition
            )
            warnings.extend(_warning_messages(parsed_part07.warnings))
        if "PS3.8" in documents:
            parsed_part08 = parse_part08(
                documents["PS3.8"], edition=manifest.edition
            )
            warnings.extend(_warning_messages(parsed_part08.warnings))
        if "PS3.10" in documents:
            parsed_part10 = parse_part10(
                documents["PS3.10"], edition=manifest.edition
            )
            warnings.extend(_warning_messages(parsed_part10.warnings))
            summaries.append(
                import_file_meta_requirements(
                    connection,
                    edition=manifest.edition,
                    file_meta_requirements=parsed_part10.file_meta_requirements,
                )
            )
            summaries.append(
                import_dicom_media_types(
                    connection,
                    edition=manifest.edition,
                    media_types=parsed_part10.media_types,
                )
            )
        if "PS3.16" in documents:
            parsed_part16 = parse_part16(
                documents["PS3.16"], edition=manifest.edition
            )
            warnings.extend(_warning_messages(parsed_part16.warnings))
        if "PS3.18" in documents:
            parsed_part18 = parse_part18(
                documents["PS3.18"], edition=manifest.edition
            )
            warnings.extend(_warning_messages(parsed_part18.warnings))
            summaries.append(
                import_dicomweb_transactions(
                    connection,
                    edition=manifest.edition,
                    transactions=parsed_part18.dicomweb_transactions,
                )
            )

        metrics = BuildMetrics.from_imports(
            edition=manifest.edition,
            parts_loaded=tuple(sorted(documents)),
            import_summaries=tuple(summaries),
            parse_warnings=len(warnings),
            source_refs=_source_ref_count(connection),
        )
        gate_failures = evaluate_quality_gates(metrics, gate_settings)
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
            metrics=metrics.as_jsonable(),
        )
    except (sqlite3.Error, ImportError, OSError) as exc:
        raise BuildError(f"failed to build SQLite KB for {manifest.edition}") from exc
    finally:
        connection.close()

    if metrics is None:
        raise BuildError(f"failed to compute build metrics for {manifest.edition}")
    summary_warnings = (
        tuple([*warnings, *gate_failures])
        if gate_failures and gate_settings.allow_gate_failures
        else tuple(warnings)
    )
    summary = BuildSummary(
        edition=manifest.edition,
        db_path=target_path,
        manifest_sha256=manifest.source_manifest_sha256,
        import_summaries=tuple(summaries),
        warnings=summary_warnings,
        metrics=metrics,
        gate_failures=gate_failures,
    )
    if gate_failures and not gate_settings.allow_gate_failures:
        raise BuildQualityGateError(summary)
    return summary


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
