from __future__ import annotations

import sqlite3
from pathlib import Path

from dicom_kb.db.models import apply_migrations, connect_sqlite

V2_TABLES = {
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
        "uid_value",
        "vr_encoding",
        "byte_order",
        "pixel_data",
        "deflate",
        "section_xml_id",
        "see_also_json",
    } <= _columns(connection, "transfer_syntax_detail")
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
        INSERT INTO transfer_syntax_detail (
          id, edition_id, uid_value, vr_encoding, byte_order, pixel_data,
          section_xml_id
        ) VALUES (
          '2026b.ts.explicit_vr_le',
          '2026b',
          '1.2.840.10008.1.2.1',
          'Explicit VR',
          'Little Endian',
          'Native',
          'sect_A.2'
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
    assert (
        connection.execute("SELECT count(*) FROM transfer_syntax_detail").fetchone()[0]
        == 1
    )
