from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dicom_kb.db.importers import import_docbook_structure
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part05_encoding import parse_part05
from tests.fixtures_synthetic import PS35_ENCODING_DOCBOOK


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    return connection


def test_parse_part05_classifies_vr_tables_and_warns_on_gaps() -> None:
    document = parse_docbook_xml(PS35_ENCODING_DOCBOOK, part="PS3.5")

    result = parse_part05(document, edition="2026b")

    assert [table.table_id for table in result.recognized_tables] == ["table_5-1"]
    vr_table = result.recognized_tables[0]
    assert vr_table.table_kind == "vr_behavior"
    assert vr_table.source_ref.part == "PS3.5"
    assert vr_table.source_ref.section == "sect_5_1"
    assert vr_table.source_ref.table_id == "table_5-1"
    assert vr_table.source_ref.title == "Synthetic VR Behaviors"
    assert [(warning.table_id, warning.message) for warning in result.warnings] == [
        ("table_5-2", "unsupported PS3.5 table shape")
    ]


def test_part05_docbook_structure_persists_nodes_refs_and_raw_table_ir(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS35_ENCODING_DOCBOOK, part="PS3.5")

    summary = import_docbook_structure(
        connection,
        edition="2026b",
        document=document,
    )

    assert summary.doc_nodes == 5
    assert summary.raw_table_irs == 2
    section = connection.execute(
        """
        SELECT node.title, ref.part, ref.xml_id
        FROM doc_node node
        JOIN source_ref ref ON ref.id = node.source_ref_id
        WHERE node.xml_id = ?
        """,
        ("sect_5_1",),
    ).fetchone()
    assert dict(section) == {
        "title": "Encoding Overview",
        "part": "PS3.5",
        "xml_id": "sect_5_1",
    }

    raw_table = connection.execute(
        """
        SELECT ir.ir_json, ir.ir_sha256, ref.part, ref.table_id
        FROM raw_table_ir ir
        JOIN source_ref ref ON ref.id = ir.source_ref_id
        WHERE ir.table_id = ?
        """,
        ("table_5-1",),
    ).fetchone()
    payload = json.loads(raw_table["ir_json"])
    assert payload["title"] == "Synthetic VR Behaviors"
    assert payload["rows"][1]["cells"][0]["text"] == "PN"
    assert len(raw_table["ir_sha256"]) == 64
    assert raw_table["part"] == "PS3.5"
    assert raw_table["table_id"] == "table_5-1"
