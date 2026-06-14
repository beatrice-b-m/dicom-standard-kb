from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dicom_kb.db.importers import (
    import_dicom_media_types,
    import_docbook_structure,
    import_file_meta_requirements,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part10_media_storage import parse_part10
from tests.fixtures_synthetic import PS310_MEDIA_STORAGE_DOCBOOK


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    return connection


def test_parse_part10_classifies_file_meta_tables_and_warns_on_gaps() -> None:
    document = parse_docbook_xml(PS310_MEDIA_STORAGE_DOCBOOK, part="PS3.10")

    result = parse_part10(document, edition="2026b")

    assert [table.table_id for table in result.recognized_tables] == [
        "table_10-1",
        "table_10-2",
    ]
    file_meta_table = result.recognized_tables[0]
    assert file_meta_table.table_kind == "file_meta_information"
    assert file_meta_table.source_ref.part == "PS3.10"
    assert file_meta_table.source_ref.section == "sect_10_1"
    assert file_meta_table.source_ref.table_id == "table_10-1"
    assert file_meta_table.source_ref.title == "Synthetic File Meta Items"
    assert [
        (record.attribute_tag, record.type_designation)
        for record in result.file_meta_requirements
    ] == [
        ("(0002,0000)", "1"),
        ("(0002,0002)", "1"),
        ("(0002,0003)", "1"),
        ("(0002,0010)", "1"),
        ("(0002,0012)", "1"),
        ("(0002,0013)", "3"),
        ("(0002,0016)", "3"),
    ]
    assert result.file_meta_requirements[3].rule_context == "file_meta_information"
    assert result.file_meta_requirements[3].source_ref.table_id == "table_10-1"
    assert result.recognized_tables[1].table_kind == "media_type"
    assert [record.media_type for record in result.media_types] == ["application/dicom"]
    media_type = result.media_types[0]
    assert media_type.service_context == "PS3.10 file"
    assert media_type.transfer_syntax_constraints == (
        "Encoded using the Transfer Syntax UID in the File Meta Information",
    )
    assert media_type.directions == ("file",)
    assert media_type.source_ref.table_id == "table_10-2"
    assert [(warning.table_id, warning.message) for warning in result.warnings] == [
        ("table_10-3", "unsupported PS3.10 table shape")
    ]


def test_import_file_meta_requirements_persists_rows_and_data_element_links(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS310_MEDIA_STORAGE_DOCBOOK, part="PS3.10")
    parsed = parse_part10(document, edition="2026b")
    connection.execute(
        """
        INSERT INTO source_ref (id, edition_id, part, title)
        VALUES (?, ?, ?, ?)
        """,
        ("2026b.PS3.6.table_6-1", "2026b", "PS3.6", "Synthetic Data Elements"),
    )
    connection.execute(
        """
        INSERT INTO data_element (
          id, edition_id, tag, group_pattern, element_pattern, is_range, name,
          keyword, vr, vm, retired, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026b.data_element.(0002,0010)",
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
            "2026b.PS3.6.table_6-1",
        ),
    )

    summary = import_file_meta_requirements(
        connection,
        edition="2026b",
        file_meta_requirements=parsed.file_meta_requirements,
    )

    assert summary.file_meta_requirements == 7
    assert summary.source_refs == 1
    rows = connection.execute(
        """
        SELECT attribute_tag, attribute_keyword, data_element_id,
               type_designation, rule_context, ref.part, ref.table_id
        FROM file_meta_requirement req
        JOIN source_ref ref ON ref.id = req.source_ref_id
        WHERE req.edition_id = ?
        ORDER BY req.attribute_tag
        """,
        ("2026b",),
    ).fetchall()
    assert [row["type_designation"] for row in rows] == [
        "1",
        "1",
        "1",
        "1",
        "1",
        "3",
        "3",
    ]
    transfer_syntax = rows[3]
    assert dict(transfer_syntax) == {
        "attribute_tag": "(0002,0010)",
        "attribute_keyword": "TransferSyntaxUID",
        "data_element_id": "2026b.data_element.(0002,0010)",
        "type_designation": "1",
        "rule_context": "file_meta_information",
        "part": "PS3.10",
        "table_id": "table_10-1",
    }


def test_import_dicom_media_types_persists_ps310_rows_with_source_refs(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS310_MEDIA_STORAGE_DOCBOOK, part="PS3.10")
    parsed = parse_part10(document, edition="2026b")

    summary = import_dicom_media_types(
        connection,
        edition="2026b",
        media_types=parsed.media_types,
    )

    assert summary.dicom_media_types == 1
    assert summary.source_refs == 1
    row = connection.execute(
        """
        SELECT media.media_type, media.service_context,
               media.transfer_syntax_constraints_json, media.directions_json,
               ref.part, ref.table_id
        FROM dicom_media_type media
        JOIN source_ref ref ON ref.id = media.source_ref_id
        WHERE media.edition_id = ?
        """,
        ("2026b",),
    ).fetchone()
    assert dict(row) == {
        "media_type": "application/dicom",
        "service_context": "PS3.10 file",
        "transfer_syntax_constraints_json": json.dumps(
            ("Encoded using the Transfer Syntax UID in the File Meta Information",),
            separators=(",", ":"),
        ),
        "directions_json": json.dumps(("file",), separators=(",", ":")),
        "part": "PS3.10",
        "table_id": "table_10-2",
    }


def test_part10_docbook_structure_persists_nodes_refs_and_raw_table_ir(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS310_MEDIA_STORAGE_DOCBOOK, part="PS3.10")

    summary = import_docbook_structure(
        connection,
        edition="2026b",
        document=document,
    )

    assert summary.doc_nodes == 6
    assert summary.raw_table_irs == 3
    section = connection.execute(
        """
        SELECT node.title, ref.part, ref.xml_id
        FROM doc_node node
        JOIN source_ref ref ON ref.id = node.source_ref_id
        WHERE node.xml_id = ?
        """,
        ("sect_10_1",),
    ).fetchone()
    assert dict(section) == {
        "title": "File Meta Overview",
        "part": "PS3.10",
        "xml_id": "sect_10_1",
    }

    raw_table = connection.execute(
        """
        SELECT ir.ir_json, ir.ir_sha256, ref.part, ref.table_id
        FROM raw_table_ir ir
        JOIN source_ref ref ON ref.id = ir.source_ref_id
        WHERE ir.table_id = ?
        """,
        ("table_10-1",),
    ).fetchone()
    payload = json.loads(raw_table["ir_json"])
    assert payload["title"] == "Synthetic File Meta Items"
    assert payload["rows"][1]["cells"][0]["text"] == (
        "File Meta Information Group Length"
    )
    assert len(raw_table["ir_sha256"]) == 64
    assert raw_table["part"] == "PS3.10"
    assert raw_table["table_id"] == "table_10-1"
