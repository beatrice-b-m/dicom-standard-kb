from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dicom_kb.db.importers import import_docbook_structure, import_vr_definitions
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
    assert [record.vr for record in result.vr_definitions] == ["PN", "OB", "SQ", "UN"]
    pn = result.vr_definitions[0]
    assert pn.name == "Person Name"
    assert pn.value_representation_class == "character string"
    assert pn.length_notes == ("variable length",)
    assert pn.padding_behavior == "space padded"
    assert pn.character_repertoire_notes == (
        "uses the default character repertoire",
    )
    assert pn.binary_or_text == "text"
    assert result.vr_definitions[1].binary_or_text == "binary"


def test_import_vr_definitions_persists_ps35_rows_with_source_refs(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    parsed = parse_part05(
        parse_docbook_xml(PS35_ENCODING_DOCBOOK, part="PS3.5"),
        edition="2026b",
    )

    summary = import_vr_definitions(
        connection,
        edition="2026b",
        vr_definitions=parsed.vr_definitions,
    )

    assert summary.vr_definitions == 4
    row = connection.execute(
        """
        SELECT
          vr.vr,
          vr.name,
          vr.value_representation_class,
          vr.length_notes_json,
          vr.padding_behavior,
          vr.character_repertoire_notes_json,
          vr.binary_or_text,
          ref.part,
          ref.table_id
        FROM vr_definition vr
        JOIN source_ref ref ON ref.id = vr.source_ref_id
        WHERE vr.edition_id = ? AND vr.vr = ?
        """,
        ("2026b", "PN"),
    ).fetchone()
    assert dict(row) == {
        "vr": "PN",
        "name": "Person Name",
        "value_representation_class": "character string",
        "length_notes_json": '["variable length"]',
        "padding_behavior": "space padded",
        "character_repertoire_notes_json": (
            '["uses the default character repertoire"]'
        ),
        "binary_or_text": "text",
        "part": "PS3.5",
        "table_id": "table_5-1",
    }


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
