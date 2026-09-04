from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

import pytest

from dicom_kb.db.models import apply_migrations
from dicom_kb.sources.manifest import SourceArtifact, SourceManifest
from tests.integration_requires_dicom_download.release_requirements import (
    REQUIRED_RELEASE_DOCBOOK_PARTS,
    REQUIRED_RELEASE_SEMANTIC_TABLES,
    evaluate_official_kb_release_requirements,
    require_official_kb_release_ready,
)


def test_release_requirements_accept_complete_official_kb() -> None:
    connection = _release_ready_connection()
    manifest = _manifest(REQUIRED_RELEASE_DOCBOOK_PARTS)

    requirements = evaluate_official_kb_release_requirements(
        connection, edition="2026b", manifest=manifest
    )

    assert requirements.ok is True
    assert requirements.failure_message() == ""
    require_official_kb_release_ready(connection, edition="2026b", manifest=manifest)


def test_release_requirements_report_missing_docbook_part() -> None:
    connection = _release_ready_connection()
    manifest = _manifest(REQUIRED_RELEASE_DOCBOOK_PARTS - {"PS3.18"})

    requirements = evaluate_official_kb_release_requirements(
        connection, edition="2026b", manifest=manifest
    )

    assert requirements.ok is False
    assert requirements.missing_docbook_parts == ("PS3.18",)
    assert requirements.missing_semantic_tables == ()
    assert requirements.missing_docbook_structure_parts == ()
    with pytest.raises(AssertionError, match="missing DocBook artifacts for: PS3.18"):
        require_official_kb_release_ready(
            connection, edition="2026b", manifest=manifest
        )


def test_release_requirements_report_missing_semantic_rows() -> None:
    connection = _release_ready_connection(omit_tables={"dicomweb_transaction"})
    manifest = _manifest(REQUIRED_RELEASE_DOCBOOK_PARTS)

    requirements = evaluate_official_kb_release_requirements(
        connection, edition="2026b", manifest=manifest
    )

    assert requirements.ok is False
    assert requirements.missing_docbook_parts == ()
    assert requirements.missing_semantic_tables == ("dicomweb_transaction",)
    assert requirements.missing_docbook_structure_parts == ()
    assert "missing semantic rows in: dicomweb_transaction" in (
        requirements.failure_message()
    )


def test_release_requirements_report_missing_docbook_structure() -> None:
    connection = _release_ready_connection(omit_structure_parts={"PS3.16"})
    manifest = _manifest(REQUIRED_RELEASE_DOCBOOK_PARTS)

    requirements = evaluate_official_kb_release_requirements(
        connection, edition="2026b", manifest=manifest
    )

    assert requirements.ok is False
    assert requirements.missing_docbook_parts == ()
    assert requirements.missing_semantic_tables == ()
    assert requirements.missing_docbook_structure_parts == ("PS3.16",)
    assert "missing DocBook structure rows for: PS3.16" in (
        requirements.failure_message()
    )


def _release_ready_connection(
    *,
    omit_tables: set[str] | None = None,
    omit_structure_parts: set[str] | None = None,
) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    apply_migrations(connection)
    _insert_source_refs(connection)
    _insert_docbook_structure(connection, omit_parts=omit_structure_parts or set())
    _insert_semantic_rows(connection, omit_tables=omit_tables or set())
    return connection


def _insert_source_refs(connection: sqlite3.Connection) -> None:
    for part in REQUIRED_RELEASE_DOCBOOK_PARTS:
        connection.execute(
            """
            INSERT INTO source_ref (
              id, edition_id, part, chapter, section, table_id, figure_id,
              xml_id, anchor, title, source_artifact_id, canonical_url,
              text_excerpt, excerpt_hash
            )
            VALUES (
              ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, NULL, NULL, NULL,
              NULL, NULL
            )
            """,
            (_source_ref_id(part), "2026b", part, f"{part.lower()}_anchor"),
        )


def _insert_docbook_structure(
    connection: sqlite3.Connection, *, omit_parts: set[str]
) -> None:
    for index, part in enumerate(sorted(REQUIRED_RELEASE_DOCBOOK_PARTS), start=1):
        if part in omit_parts:
            continue
        connection.execute(
            """
            INSERT INTO doc_node (
              id, edition_id, part, node_type, parent_id, xml_id, anchor,
              number, title, ordinal, plain_text, source_ref_id
            )
            VALUES (?, ?, ?, 'section', NULL, ?, ?, NULL, ?, ?, ?, ?)
            """,
            (
                f"doc-node-{part}",
                "2026b",
                part,
                f"{part.lower()}-section",
                f"{part.lower()}_anchor",
                f"{part} section",
                index,
                "Synthetic release requirement structure.",
                _source_ref_id(part),
            ),
        )


def _insert_semantic_rows(
    connection: sqlite3.Connection, *, omit_tables: set[str]
) -> None:
    for table in REQUIRED_RELEASE_SEMANTIC_TABLES:
        if table in omit_tables:
            continue
        _SEMANTIC_INSERTS[table](connection)


def _insert_vr_definition(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO vr_definition (
          id, edition_id, vr, name, source_ref_id
        )
        VALUES ('vr-pn', '2026b', 'PN', 'Person Name', ?)
        """,
        (_source_ref_id("PS3.5"),),
    )


def _insert_transfer_syntax_detail(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO source_ref (
          id, edition_id, part, chapter, section, table_id, figure_id,
          xml_id, anchor, title, source_artifact_id, canonical_url,
          text_excerpt, excerpt_hash
        )
        VALUES (
          'source-ref-ps3-6-transfer', '2026b', 'PS3.6', NULL, NULL, NULL,
          NULL, NULL, 'table_A-1', NULL, NULL, NULL, NULL, NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO uid_registry_entry (
          id, edition_id, uid_value, uid_name, uid_type, retired,
          source_ref_id
        )
        VALUES (
          'uid-explicit-vr-le', '2026b', '1.2.840.10008.1.2.1',
          'Explicit VR Little Endian', 'Transfer Syntax', 0,
          'source-ref-ps3-6-transfer'
        )
        """
    )
    connection.execute(
        """
        INSERT INTO transfer_syntax_detail (
          id, edition_id, uid_registry_entry_id, uid_value, source_ref_id
        )
        VALUES (
          'ts-explicit-vr-le', '2026b', 'uid-explicit-vr-le',
          '1.2.840.10008.1.2.1', 'source-ref-ps3-6-transfer'
        )
        """
    )


def _insert_file_meta_requirement(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO file_meta_requirement (
          id, edition_id, attribute_tag, attribute_keyword, type_designation,
          source_ref_id
        )
        VALUES (
          'file-meta-tsuid', '2026b', '(0002,0010)', 'TransferSyntaxUID',
          '1', ?
        )
        """,
        (_source_ref_id("PS3.10"),),
    )


def _insert_dicom_media_type(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO dicom_media_type (
          id, edition_id, media_type, service_context, source_ref_id
        )
        VALUES ('media-application-dicom', '2026b', 'application/dicom', 'store', ?)
        """,
        (_source_ref_id("PS3.10"),),
    )


def _insert_dicomweb_transaction(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO dicomweb_transaction (
          id, edition_id, transaction_name, http_method, route_template,
          source_ref_id
        )
        VALUES (
          'dicomweb-retrieve-study', '2026b', 'RetrieveStudy', 'GET',
          '/studies/{study}', ?
        )
        """,
        (_source_ref_id("PS3.18"),),
    )


def _insert_sr_template(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO sr_template (
          id, edition_id, tid, name, source_ref_id
        )
        VALUES ('tid-1500', '2026b', '1500', 'Measurement Report', ?)
        """,
        (_source_ref_id("PS3.16"),),
    )


def _insert_sr_template_row(connection: sqlite3.Connection) -> None:
    _insert_sr_template_if_missing(connection)
    connection.execute(
        """
        INSERT INTO sr_template_row (
          id, edition_id, sr_template_id, row_order, value_type, source_ref_id
        )
        VALUES ('tid-1500-row-1', '2026b', 'tid-1500', 1, 'CONTAINER', ?)
        """,
        (_source_ref_id("PS3.16"),),
    )


def _insert_context_group(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO context_group (
          id, edition_id, cid, name, source_ref_id
        )
        VALUES ('cid-29', '2026b', '29', 'Acquisition Modality', ?)
        """,
        (_source_ref_id("PS3.16"),),
    )


def _insert_context_group_row(connection: sqlite3.Connection) -> None:
    _insert_context_group_if_missing(connection)
    connection.execute(
        """
        INSERT INTO context_group_row (
          id, edition_id, context_group_id, row_order,
          coding_scheme_designator, code_value, code_meaning, source_ref_id
        )
        VALUES ('cid-29-row-1', '2026b', 'cid-29', 1, 'DCM', 'CT',
                'Computed Tomography', ?)
        """,
        (_source_ref_id("PS3.16"),),
    )


def _insert_coded_concept(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO coded_concept (
          id, edition_id, code_value, coding_scheme_designator, code_meaning,
          source_ref_id
        )
        VALUES ('code-ct-dcm', '2026b', 'CT', 'DCM', 'Computed Tomography', ?)
        """,
        (_source_ref_id("PS3.16"),),
    )


def _insert_attribute_value_term(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO attribute_value_term (
          id, edition_id, term_kind, value, meaning, source_ref_id
        )
        VALUES ('modality-ct-term', '2026b', 'defined_term', 'CT',
                'Computed Tomography', ?)
        """,
        (_source_ref_id("PS3.3"),),
    )


def _insert_sr_template_if_missing(connection: sqlite3.Connection) -> None:
    if _row_exists(connection, "sr_template", "tid-1500"):
        return
    _insert_sr_template(connection)


def _insert_context_group_if_missing(connection: sqlite3.Connection) -> None:
    if _row_exists(connection, "context_group", "cid-29"):
        return
    _insert_context_group(connection)


def _row_exists(connection: sqlite3.Connection, table: str, row_id: str) -> bool:
    row = connection.execute(
        f"SELECT 1 FROM {table} WHERE id = ?",
        (row_id,),
    ).fetchone()
    return row is not None


def _source_ref_id(part: str) -> str:
    return f"source-ref-{part.lower().replace('.', '-')}"


def _manifest(parts: set[str] | frozenset[str]) -> SourceManifest:
    return SourceManifest(
        edition="2026b",
        resolved_from="current",
        acquired_at=datetime(2026, 6, 14, tzinfo=UTC),
        artifacts=tuple(
            SourceArtifact(
                part=part,
                format="docbook_xml",
                local_path=f"artifacts/2026b/raw/source/docbook/{part}/part.xml",
                source_url=f"https://example.test/{part}/part.xml",
                sha256="0" * 64,
                byte_size=100,
            )
            for part in sorted(parts)
        ),
    ).with_digest()


_SEMANTIC_INSERTS = {
    "vr_definition": _insert_vr_definition,
    "transfer_syntax_detail": _insert_transfer_syntax_detail,
    "file_meta_requirement": _insert_file_meta_requirement,
    "dicom_media_type": _insert_dicom_media_type,
    "dicomweb_transaction": _insert_dicomweb_transaction,
    "sr_template": _insert_sr_template,
    "sr_template_row": _insert_sr_template_row,
    "context_group": _insert_context_group,
    "context_group_row": _insert_context_group_row,
    "coded_concept": _insert_coded_concept,
    "attribute_value_term": _insert_attribute_value_term,
}
