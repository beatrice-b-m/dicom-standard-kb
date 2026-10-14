from __future__ import annotations

import sqlite3
from pathlib import Path

from dicom_kb.db.importers import import_docbook_structure
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part07_messages import parse_part07
from tests.fixtures_synthetic import PS37_MESSAGES_DOCBOOK


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    return connection


def test_parse_part07_classifies_dimse_service_tables_and_warns_on_gaps() -> None:
    document = parse_docbook_xml(PS37_MESSAGES_DOCBOOK, part="PS3.7")

    result = parse_part07(document, edition="2026b")

    assert [table.table_id for table in result.recognized_tables] == ["table_7-1"]
    service_table = result.recognized_tables[0]
    assert service_table.table_kind == "dimse_service"
    assert service_table.source_ref.part == "PS3.7"
    assert service_table.source_ref.section == "sect_7.1"
    assert service_table.source_ref.table_id == "table_7-1"
    assert service_table.source_ref.title == "Synthetic Message Services"
    assert [
        (record.service, record.role, record.behavior)
        for record in result.service_behaviors
    ] == [
        (
            "C-ECHO",
            "verification",
            "Confirms application-level communication between peer DICOM AEs.",
        )
    ]
    assert result.service_behaviors[0].source_ref.table_id == "table_7-1"
    assert [(warning.table_id, warning.message) for warning in result.warnings] == [
        ("table_7-2", "unsupported PS3.7 table shape")
    ]


def test_part07_docbook_structure_persists_nodes_refs_and_table_markdown(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS37_MESSAGES_DOCBOOK, part="PS3.7")

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
        ("sect_7.1",),
    ).fetchone()
    assert dict(section) == {
        "title": "DIMSE Services Overview",
        "part": "PS3.7",
        "xml_id": "sect_7.1",
    }

    table = connection.execute(
        """
        SELECT node.markdown, ref.part, ref.table_id
        FROM doc_node node
        JOIN source_ref ref ON ref.id = node.source_ref_id
        WHERE node.xml_id = ? AND node.node_type = 'table'
        """,
        ("table_7-1",),
    ).fetchone()
    assert table["markdown"].startswith("**Table 7-1: Synthetic Message Services**\n")
    assert (
        "| C-ECHO | verification"
        " | Confirms application-level communication between peer DICOM AEs. |"
    ) in table["markdown"]
    assert table["part"] == "PS3.7"
    assert table["table_id"] == "table_7-1"
