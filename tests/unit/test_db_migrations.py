from __future__ import annotations

import sqlite3
from pathlib import Path

from dicom_kb.db.models import apply_migrations, connect_sqlite

V2_TABLES = {
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
}


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    return connection


def _table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    ).fetchall()
    return {str(row["name"]) for row in rows}


def _columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"]) for row in rows}


def test_empty_database_migrations_create_canonical_v2_tables(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)

    assert _table_names(connection) >= V2_TABLES
    for table_name in V2_TABLES:
        assert "edition_id" in _columns(connection, table_name)
        assert "source_ref_id" in _columns(connection, table_name)

    assert {
        "vr",
        "name",
        "value_representation_class",
        "length_notes_json",
        "padding_behavior",
        "character_repertoire_notes_json",
        "binary_or_text",
    } <= _columns(connection, "vr_definition")
    assert {
        "uid_registry_entry_id",
        "uid_value",
        "explicit_vr",
        "endian",
        "encapsulated",
        "compression_family",
        "encoding_notes_json",
    } <= _columns(connection, "transfer_syntax_detail")
    assert {
        "transaction_name",
        "resource_category",
        "http_method",
        "route_template",
        "request_constraints_json",
        "response_constraints_json",
        "status_codes_json",
        "media_type_refs_json",
    } <= _columns(connection, "dicomweb_transaction")
    assert {"tid", "name", "extensibility"} <= _columns(connection, "sr_template")
    assert {
        "sr_template_id",
        "row_order",
        "relationship_type",
        "value_type",
        "concept_name",
        "cardinality",
        "condition_text",
        "condition_id",
        "include_tid",
    } <= _columns(connection, "sr_template_row")
    assert {"cid", "name", "extensibility", "version"} <= _columns(
        connection, "context_group"
    )
    assert {
        "context_group_id",
        "row_order",
        "coding_scheme_designator",
        "coding_scheme_version",
        "code_value",
        "code_meaning",
        "include_cid",
    } <= _columns(connection, "context_group_row")
    assert {
        "code_value",
        "coding_scheme_designator",
        "coding_scheme_version",
        "code_meaning",
    } <= _columns(connection, "coded_concept")


def test_v2_tables_accept_minimal_rows_with_source_refs(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    source_ref_id = "2026b.PS3.5.table"
    connection.execute(
        """
        INSERT INTO source_ref (id, edition_id, part, title)
        VALUES (?, ?, ?, ?)
        """,
        (source_ref_id, "2026b", "PS3.5", "Synthetic V2 Source"),
    )
    connection.execute(
        """
        INSERT INTO uid_registry_entry (
          id, edition_id, uid_value, uid_name, uid_type, retired, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026b.uid.explicit_vr_little_endian",
            "2026b",
            "1.2.840.10008.1.2.1",
            "Explicit VR Little Endian",
            "Transfer Syntax",
            0,
            source_ref_id,
        ),
    )
    connection.execute(
        """
        INSERT INTO data_element (
          id, edition_id, tag, group_pattern, element_pattern, is_range, name,
          keyword, vr, vm, retired, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026b.data_element.transfer_syntax_uid",
            "2026b",
            "(0002,0010)",
            "0002",
            "0010",
            0,
            "Transfer Syntax UID",
            "TransferSyntaxUID",
            "UI",
            "1",
            0,
            source_ref_id,
        ),
    )

    connection.executescript(
        f"""
        INSERT INTO vr_definition (
          id, edition_id, vr, name, source_ref_id
        ) VALUES (
          '2026b.vr.pn', '2026b', 'PN', 'Person Name', '{source_ref_id}'
        );
        INSERT INTO transfer_syntax_detail (
          id, edition_id, uid_registry_entry_id, uid_value, explicit_vr,
          endian, encapsulated, source_ref_id
        ) VALUES (
          '2026b.ts.explicit_vr_le',
          '2026b',
          '2026b.uid.explicit_vr_little_endian',
          '1.2.840.10008.1.2.1',
          1,
          'little',
          0,
          '{source_ref_id}'
        );
        INSERT INTO file_meta_requirement (
          id, edition_id, data_element_id, attribute_tag, attribute_keyword,
          type_designation, rule_context, source_ref_id
        ) VALUES (
          '2026b.file_meta.transfer_syntax_uid',
          '2026b',
          '2026b.data_element.transfer_syntax_uid',
          '(0002,0010)',
          'TransferSyntaxUID',
          '1',
          'file_meta_information',
          '{source_ref_id}'
        );
        INSERT INTO dicom_media_type (
          id, edition_id, media_type, service_context, source_ref_id
        ) VALUES (
          '2026b.media.application_dicom',
          '2026b',
          'application/dicom',
          'PS3.10 file',
          '{source_ref_id}'
        );
        INSERT INTO dicomweb_transaction (
          id, edition_id, transaction_name, resource_category, http_method,
          route_template, source_ref_id
        ) VALUES (
          '2026b.dicomweb.retrieve_study',
          '2026b',
          'RetrieveStudy',
          'study',
          'GET',
          '/studies/{{studyInstanceUID}}',
          '{source_ref_id}'
        );
        INSERT INTO sr_template (
          id, edition_id, tid, name, source_ref_id
        ) VALUES (
          '2026b.tid.1500',
          '2026b',
          'TID 1500',
          'Measurement Report',
          '{source_ref_id}'
        );
        INSERT INTO sr_template_row (
          id, edition_id, sr_template_id, row_order, value_type, source_ref_id
        ) VALUES (
          '2026b.tid.1500.row.1',
          '2026b',
          '2026b.tid.1500',
          1,
          'CONTAINER',
          '{source_ref_id}'
        );
        INSERT INTO context_group (
          id, edition_id, cid, name, source_ref_id
        ) VALUES (
          '2026b.cid.29',
          '2026b',
          'CID 29',
          'Acquisition Modality',
          '{source_ref_id}'
        );
        INSERT INTO context_group_row (
          id, edition_id, context_group_id, row_order, code_value,
          coding_scheme_designator, code_meaning, source_ref_id
        ) VALUES (
          '2026b.cid.29.row.1',
          '2026b',
          '2026b.cid.29',
          1,
          'CT',
          'DCM',
          'Computed Tomography',
          '{source_ref_id}'
        );
        INSERT INTO coded_concept (
          id, edition_id, code_value, coding_scheme_designator, code_meaning,
          source_ref_id
        ) VALUES (
          '2026b.code.dcm.ct',
          '2026b',
          'CT',
          'DCM',
          'Computed Tomography',
          '{source_ref_id}'
        );
        """
    )

    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    counts = {
        table_name: connection.execute(f"SELECT count(*) FROM {table_name}").fetchone()[
            0
        ]
        for table_name in V2_TABLES
    }
    assert counts == {table_name: 1 for table_name in V2_TABLES}
