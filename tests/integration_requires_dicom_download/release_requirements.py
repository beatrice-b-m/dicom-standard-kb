from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from dicom_kb.sources.manifest import SourceManifest

REQUIRED_RELEASE_DOCBOOK_PARTS = frozenset(
    {
        "PS3.3",
        "PS3.4",
        "PS3.5",
        "PS3.6",
        "PS3.7",
        "PS3.8",
        "PS3.10",
        "PS3.16",
        "PS3.18",
    }
)

REQUIRED_RELEASE_SEMANTIC_TABLES = (
    "vr_definition",
    "transfer_syntax_detail",
    "file_meta_requirement",
    "dicom_media_type",
    "dicomweb_transaction",
    "sr_template",
    "sr_template_row",
    "context_group",
    "context_group_row",
    "coded_concept",
    "attribute_value_term",
)


@dataclass(frozen=True)
class OfficialKbReleaseRequirements:
    edition: str
    missing_docbook_parts: tuple[str, ...]
    missing_semantic_tables: tuple[str, ...]
    missing_docbook_structure_parts: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not (
            self.missing_docbook_parts
            or self.missing_semantic_tables
            or self.missing_docbook_structure_parts
        )

    def failure_message(self) -> str:
        if self.ok:
            return ""
        messages: list[str] = [
            f"official KB for edition {self.edition!r} is not release-ready"
        ]
        if self.missing_docbook_parts:
            messages.append(
                "missing DocBook artifacts for: "
                + ", ".join(self.missing_docbook_parts)
            )
        if self.missing_semantic_tables:
            messages.append(
                "missing semantic rows in: " + ", ".join(self.missing_semantic_tables)
            )
        if self.missing_docbook_structure_parts:
            messages.append(
                "missing DocBook structure rows for: "
                + ", ".join(self.missing_docbook_structure_parts)
            )
        return "; ".join(messages)


def evaluate_official_kb_release_requirements(
    connection: sqlite3.Connection,
    *,
    edition: str,
    manifest: SourceManifest,
) -> OfficialKbReleaseRequirements:
    """Return strict v2 official-KB release prerequisite gaps."""
    manifest_docbook_parts = {
        artifact.part
        for artifact in manifest.artifacts
        if artifact.format == "docbook_xml"
    }
    missing_docbook_parts = tuple(
        sorted(REQUIRED_RELEASE_DOCBOOK_PARTS - manifest_docbook_parts)
    )
    missing_semantic_tables = tuple(
        table
        for table in REQUIRED_RELEASE_SEMANTIC_TABLES
        if _edition_row_count(connection, table=table, edition=edition) == 0
    )
    missing_docbook_structure_parts = tuple(
        part
        for part in sorted(REQUIRED_RELEASE_DOCBOOK_PARTS)
        if _docbook_structure_row_count(connection, edition=edition, part=part) == 0
    )
    return OfficialKbReleaseRequirements(
        edition=edition,
        missing_docbook_parts=missing_docbook_parts,
        missing_semantic_tables=missing_semantic_tables,
        missing_docbook_structure_parts=missing_docbook_structure_parts,
    )


def require_official_kb_release_ready(
    connection: sqlite3.Connection,
    *,
    edition: str,
    manifest: SourceManifest,
) -> None:
    requirements = evaluate_official_kb_release_requirements(
        connection, edition=edition, manifest=manifest
    )
    if not requirements.ok:
        raise AssertionError(requirements.failure_message())


def _edition_row_count(
    connection: sqlite3.Connection, *, table: str, edition: str
) -> int:
    row = connection.execute(
        f"SELECT COUNT(*) AS count FROM {table} WHERE edition_id = ?",
        (edition,),
    ).fetchone()
    return int(row["count"])


def _docbook_structure_row_count(
    connection: sqlite3.Connection, *, edition: str, part: str
) -> int:
    row = connection.execute(
        """
        SELECT
          (
            SELECT COUNT(*)
            FROM doc_node
            WHERE edition_id = ? AND part = ?
          )
          +
          (
            SELECT COUNT(*)
            FROM raw_table_ir
            WHERE edition_id = ? AND part = ?
          ) AS count
        """,
        (edition, part, edition, part),
    ).fetchone()
    return int(row["count"])
