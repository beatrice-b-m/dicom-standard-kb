from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dicom_kb.db.importers import (
    import_docbook_structure,
    import_part06,
    import_transfer_syntax_details,
    import_vr_definitions,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part05_encoding import (
    parse_part05,
    transfer_syntax_details_from_uid_registry,
)
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from tests.fixtures_synthetic import PS35_ENCODING_DOCBOOK, PS36_REGISTRY_DOCBOOK


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


def test_transfer_syntax_details_derive_deterministic_encoding_fields() -> None:
    parsed = parse_part06(
        parse_docbook_xml(PS36_REGISTRY_DOCBOOK, part="PS3.6"),
        edition="2026b",
    )

    details = transfer_syntax_details_from_uid_registry(
        edition="2026b",
        uid_registry_entries=parsed.uid_registry_entries,
    )

    by_uid = {detail.uid_value: detail for detail in details}
    assert set(by_uid) == {
        "1.2.840.10008.1.2",
        "1.2.840.10008.1.2.1",
        "1.2.840.10008.1.2.1.99",
        "1.2.840.10008.1.2.2",
        "1.2.840.10008.1.2.4.50",
    }
    assert by_uid["1.2.840.10008.1.2"].explicit_vr is False
    assert by_uid["1.2.840.10008.1.2"].endian == "little"
    assert by_uid["1.2.840.10008.1.2"].encapsulated is False
    assert by_uid["1.2.840.10008.1.2.1"].explicit_vr is True
    assert by_uid["1.2.840.10008.1.2.1"].endian == "little"
    assert by_uid["1.2.840.10008.1.2.1"].encapsulated is False
    assert by_uid["1.2.840.10008.1.2.1.99"].compression_family == "deflated"
    assert by_uid["1.2.840.10008.1.2.1.99"].encapsulated is False
    assert by_uid["1.2.840.10008.1.2.2"].endian == "big"
    assert by_uid["1.2.840.10008.1.2.4.50"].compression_family == "jpeg"
    assert by_uid["1.2.840.10008.1.2.4.50"].encapsulated is True
    assert by_uid["1.2.840.10008.1.2.4.50"].encoding_notes == (
        "jpeg compressed transfer syntax",
        "encapsulated pixel data",
    )


def test_import_transfer_syntax_details_persists_joined_uid_rows(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    parsed = parse_part06(
        parse_docbook_xml(PS36_REGISTRY_DOCBOOK, part="PS3.6"),
        edition="2026b",
    )
    import_part06(
        connection,
        edition="2026b",
        data_elements=parsed.data_elements,
        uid_registry_entries=parsed.uid_registry_entries,
    )
    details = transfer_syntax_details_from_uid_registry(
        edition="2026b",
        uid_registry_entries=parsed.uid_registry_entries,
    )

    summary = import_transfer_syntax_details(
        connection,
        edition="2026b",
        transfer_syntax_details=details,
    )

    assert summary.transfer_syntax_details == 5
    rows = connection.execute(
        """
        SELECT
          uid.uid_name,
          detail.explicit_vr,
          detail.endian,
          detail.encapsulated,
          detail.compression_family,
          detail.encoding_notes_json,
          ref.part,
          ref.table_id
        FROM transfer_syntax_detail detail
        JOIN uid_registry_entry uid ON uid.id = detail.uid_registry_entry_id
        JOIN source_ref ref ON ref.id = detail.source_ref_id
        WHERE detail.edition_id = ?
        ORDER BY detail.uid_value
        """,
        ("2026b",),
    ).fetchall()
    assert [dict(row) for row in rows] == [
        {
            "uid_name": (
                "Implicit VR Little Endian: Default Transfer Syntax for DICOM"
            ),
            "explicit_vr": 0,
            "endian": "little",
            "encapsulated": 0,
            "compression_family": None,
            "encoding_notes_json": "[]",
            "part": "PS3.6",
            "table_id": "table_A-1",
        },
        {
            "uid_name": "Explicit VR Little Endian",
            "explicit_vr": 1,
            "endian": "little",
            "encapsulated": 0,
            "compression_family": None,
            "encoding_notes_json": "[]",
            "part": "PS3.6",
            "table_id": "table_A-1",
        },
        {
            "uid_name": "Deflated Explicit VR Little Endian",
            "explicit_vr": 1,
            "endian": "little",
            "encapsulated": 0,
            "compression_family": "deflated",
            "encoding_notes_json": '["deflated dataset encoding"]',
            "part": "PS3.6",
            "table_id": "table_A-1",
        },
        {
            "uid_name": "Explicit VR Big Endian",
            "explicit_vr": 1,
            "endian": "big",
            "encapsulated": 0,
            "compression_family": None,
            "encoding_notes_json": "[]",
            "part": "PS3.6",
            "table_id": "table_A-1",
        },
        {
            "uid_name": "JPEG Baseline (Process 1)",
            "explicit_vr": None,
            "endian": None,
            "encapsulated": 1,
            "compression_family": "jpeg",
            "encoding_notes_json": (
                '["jpeg compressed transfer syntax","encapsulated pixel data"]'
            ),
            "part": "PS3.6",
            "table_id": "table_A-1",
        },
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
