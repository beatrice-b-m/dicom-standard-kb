from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dicom_kb.db.importers import import_docbook_structure
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part08_network import parse_part08
from tests.fixtures_synthetic import PS38_NETWORK_DOCBOOK


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    return connection


def test_parse_part08_classifies_association_pdu_tables_and_warns_on_gaps() -> None:
    document = parse_docbook_xml(PS38_NETWORK_DOCBOOK, part="PS3.8")

    result = parse_part08(document, edition="2026b")

    assert [table.table_id for table in result.recognized_tables] == ["table_8-1"]
    pdu_table = result.recognized_tables[0]
    assert pdu_table.table_kind == "association_pdu"
    assert pdu_table.source_ref.part == "PS3.8"
    assert pdu_table.source_ref.section == "sect_8_1"
    assert pdu_table.source_ref.table_id == "table_8-1"
    assert pdu_table.source_ref.title == "Synthetic Association PDUs"
    assert [
        (record.pdu, record.direction, record.behavior)
        for record in result.pdu_behaviors
    ] == [
        (
            "A-ASSOCIATE-RQ",
            "request",
            "Starts association establishment by proposing presentation contexts.",
        ),
        (
            "A-ASSOCIATE-AC",
            "response",
            "Accepts association establishment with negotiated presentation contexts.",
        ),
    ]
    assert result.pdu_behaviors[0].source_ref.table_id == "table_8-1"
    assert [(warning.table_id, warning.message) for warning in result.warnings] == [
        ("table_8-2", "unsupported PS3.8 table shape")
    ]


def test_part08_docbook_structure_persists_nodes_refs_and_raw_table_ir(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS38_NETWORK_DOCBOOK, part="PS3.8")

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
        ("sect_8_1",),
    ).fetchone()
    assert dict(section) == {
        "title": "Association PDU Behavior Overview",
        "part": "PS3.8",
        "xml_id": "sect_8_1",
    }

    raw_table = connection.execute(
        """
        SELECT ir.ir_json, ir.ir_sha256, ref.part, ref.table_id
        FROM raw_table_ir ir
        JOIN source_ref ref ON ref.id = ir.source_ref_id
        WHERE ir.table_id = ?
        """,
        ("table_8-1",),
    ).fetchone()
    payload = json.loads(raw_table["ir_json"])
    assert payload["title"] == "Synthetic Association PDUs"
    assert payload["rows"][1]["cells"][0]["text"] == "A-ASSOCIATE-RQ"
    assert (
        payload["rows"][1]["cells"][2]["text"]
        == "Starts association establishment by proposing presentation contexts."
    )
    assert len(raw_table["ir_sha256"]) == 64
    assert raw_table["part"] == "PS3.8"
    assert raw_table["table_id"] == "table_8-1"
