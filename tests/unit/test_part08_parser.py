from __future__ import annotations

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
    assert pdu_table.source_ref.section == "sect_9.3"
    assert pdu_table.source_ref.table_id == "table_8-1"
    assert pdu_table.source_ref.title == "ASSOCIATE-RQ PDU Fields"
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


def test_part08_docbook_structure_persists_nodes_refs_and_table_markdown(
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
    section = connection.execute(
        """
        SELECT node.title, ref.part, ref.xml_id
        FROM doc_node node
        JOIN source_ref ref ON ref.id = node.source_ref_id
        WHERE node.xml_id = ?
        """,
        ("sect_9.3",),
    ).fetchone()
    assert dict(section) == {
        "title": "PDU Fields Overview",
        "part": "PS3.8",
        "xml_id": "sect_9.3",
    }

    table = connection.execute(
        """
        SELECT node.markdown, ref.part, ref.table_id
        FROM doc_node node
        JOIN source_ref ref ON ref.id = node.source_ref_id
        WHERE node.xml_id = ? AND node.node_type = 'table'
        """,
        ("table_8-1",),
    ).fetchone()
    assert table["markdown"].startswith("**Table 8-1: ASSOCIATE-RQ PDU Fields**\n")
    assert (
        "| A-ASSOCIATE-RQ | request"
        " | Starts association establishment by proposing presentation contexts. |"
    ) in table["markdown"]
    assert table["part"] == "PS3.8"
    assert table["table_id"] == "table_8-1"
