from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dicom_kb.db.importers import (
    import_coded_concepts,
    import_context_groups,
    import_docbook_structure,
    import_sr_templates,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part16_content_mapping import parse_part16
from tests.fixtures_synthetic import (
    PS316_CONTENT_MAPPING_DOCBOOK,
    PS316_OFFICIAL_SHAPE_DOCBOOK,
)


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    return connection


def test_parse_part16_classifies_sr_template_tables_and_warns_on_gaps() -> None:
    document = parse_docbook_xml(PS316_CONTENT_MAPPING_DOCBOOK, part="PS3.16")

    result = parse_part16(document, edition="2026b")

    assert [table.table_id for table in result.recognized_tables] == [
        "table_16-1",
        "table_16-3",
    ]
    template_table = result.recognized_tables[0]
    assert template_table.table_kind == "sr_template"
    assert template_table.source_ref.part == "PS3.16"
    assert template_table.source_ref.section == "sect_16_1"
    assert template_table.source_ref.table_id == "table_16-1"
    assert template_table.source_ref.title == "Synthetic Template Rows"
    assert [
        (record.tid, record.name, record.extensibility)
        for record in result.sr_templates
    ] == [("TID 1500", "Measurement Report", "EXTENSIBLE")]
    assert [
        (
            record.row_order,
            record.relationship_type,
            record.value_type,
            record.concept_name,
            record.cardinality,
            record.condition_text,
            record.include_tid,
        )
        for record in result.sr_template_rows
    ] == [
        (
            1,
            "CONTAINS",
            "CONTAINER",
            "Measurement Report",
            "1",
            "Root container is required.",
            None,
        ),
        (
            2,
            "CONTAINS",
            "INCLUDE",
            None,
            "1-n",
            "Include measurements when present.",
            "TID 1501",
        ),
    ]
    assert result.sr_template_rows[0].source_ref.table_id == "table_16-1"
    context_group_table = result.recognized_tables[1]
    assert context_group_table.table_kind == "context_group"
    assert context_group_table.source_ref.part == "PS3.16"
    assert context_group_table.source_ref.section == "sect_16_1"
    assert context_group_table.source_ref.table_id == "table_16-3"
    assert context_group_table.source_ref.title == "Synthetic Context Group Rows"
    assert [
        (record.cid, record.name, record.extensibility, record.version)
        for record in result.context_groups
    ] == [("CID 29", "Acquisition Modality", "EXTENSIBLE", "20260101")]
    assert [
        (
            record.row_order,
            record.coding_scheme_designator,
            record.coding_scheme_version,
            record.code_value,
            record.code_meaning,
            record.include_cid,
        )
        for record in result.context_group_rows
    ] == [
        (1, "DCM", None, "CT", "Computed Tomography", None),
        (2, None, None, None, None, "CID 30"),
    ]
    assert [
        (
            record.code_value,
            record.coding_scheme_designator,
            record.coding_scheme_version,
            record.code_meaning,
        )
        for record in result.coded_concepts
    ] == [("CT", "DCM", "", "Computed Tomography")]
    assert result.context_group_rows[0].source_ref.table_id == "table_16-3"
    assert [(warning.table_id, warning.message) for warning in result.warnings] == [
        ("table_16-2", "unsupported PS3.16 table shape")
    ]


def test_parse_part16_supports_official_shape_tid_and_cid_tables() -> None:
    document = parse_docbook_xml(PS316_OFFICIAL_SHAPE_DOCBOOK, part="PS3.16")

    result = parse_part16(document, edition="2026b")

    recognized_tables = [
        (table.table_id, table.table_kind) for table in result.recognized_tables
    ]
    assert recognized_tables == [
        ("table_TID_1500", "sr_template"),
        ("table_CID_29", "context_group"),
    ]
    templates = [
        (record.tid, record.name, record.extensibility)
        for record in result.sr_templates
    ]
    assert templates == [("TID 1500", "Measurement Report", "Extensible")]
    assert [
        (
            record.row_order,
            record.relationship_type,
            record.value_type,
            record.concept_name,
            record.cardinality,
            record.condition_text,
            record.include_tid,
        )
        for record in result.sr_template_rows
    ] == [
        (
            1,
            None,
            "CONTAINER",
            "D",
            "1",
            None,
            None,
        ),
        (
            2,
            "> HAS OBS CONTEXT",
            "INCLUDE",
            "D",
            "1",
            None,
            "TID 1001",
        ),
        (
            3,
            "> CONTAINS",
            "INCLUDE",
            "D",
            "1-n",
            None,
            "TID 1501",
        ),
    ]
    assert [
        (record.cid, record.name, record.extensibility, record.version)
        for record in result.context_groups
    ] == [("CID 29", "Acquisition Modality", "Extensible", "20231115")]
    assert [
        (
            record.row_order,
            record.coding_scheme_designator,
            record.code_value,
            record.code_meaning,
            record.include_cid,
        )
        for record in result.context_group_rows
    ] == [
        (1, "DCM", "CT", "Computed Tomography", None),
        (2, None, None, None, "CID 34"),
    ]
    assert [
        (
            record.code_value,
            record.coding_scheme_designator,
            record.code_meaning,
        )
        for record in result.coded_concepts
    ] == [("CT", "DCM", "Computed Tomography")]
    assert result.warnings == ()


def test_import_sr_templates_persists_metadata_and_rows_with_source_refs(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS316_CONTENT_MAPPING_DOCBOOK, part="PS3.16")
    parsed = parse_part16(document, edition="2026b")

    summary = import_sr_templates(
        connection,
        edition="2026b",
        templates=parsed.sr_templates,
        rows=parsed.sr_template_rows,
    )

    assert summary.sr_templates == 1
    assert summary.sr_template_rows == 2
    assert summary.source_refs == 1
    rows = connection.execute(
        """
        SELECT template.tid, template.name, template.extensibility,
               row.row_order, row.relationship_type, row.value_type,
               row.concept_name, row.cardinality, row.condition_text,
               row.include_tid, ref.part, ref.table_id
        FROM sr_template template
        JOIN sr_template_row row ON row.sr_template_id = template.id
        JOIN source_ref ref ON ref.id = row.source_ref_id
        WHERE template.edition_id = ?
        ORDER BY row.row_order
        """,
        ("2026b",),
    ).fetchall()
    assert [dict(row) for row in rows] == [
        {
            "tid": "TID 1500",
            "name": "Measurement Report",
            "extensibility": "EXTENSIBLE",
            "row_order": 1,
            "relationship_type": "CONTAINS",
            "value_type": "CONTAINER",
            "concept_name": "Measurement Report",
            "cardinality": "1",
            "condition_text": "Root container is required.",
            "include_tid": None,
            "part": "PS3.16",
            "table_id": "table_16-1",
        },
        {
            "tid": "TID 1500",
            "name": "Measurement Report",
            "extensibility": "EXTENSIBLE",
            "row_order": 2,
            "relationship_type": "CONTAINS",
            "value_type": "INCLUDE",
            "concept_name": None,
            "cardinality": "1-n",
            "condition_text": "Include measurements when present.",
            "include_tid": "TID 1501",
            "part": "PS3.16",
            "table_id": "table_16-1",
        },
    ]


def test_import_context_groups_persists_metadata_and_rows_with_source_refs(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS316_CONTENT_MAPPING_DOCBOOK, part="PS3.16")
    parsed = parse_part16(document, edition="2026b")

    summary = import_context_groups(
        connection,
        edition="2026b",
        context_groups=parsed.context_groups,
        rows=parsed.context_group_rows,
    )

    assert summary.context_groups == 1
    assert summary.context_group_rows == 2
    assert summary.source_refs == 1
    rows = connection.execute(
        """
        SELECT context_group.cid, context_group.name,
               context_group.extensibility, context_group.version,
               row.row_order, row.coding_scheme_designator,
               row.coding_scheme_version, row.code_value, row.code_meaning,
               row.include_cid, ref.part, ref.table_id
        FROM context_group
        JOIN context_group_row row ON row.context_group_id = context_group.id
        JOIN source_ref ref ON ref.id = row.source_ref_id
        WHERE context_group.edition_id = ?
        ORDER BY row.row_order
        """,
        ("2026b",),
    ).fetchall()
    assert [dict(row) for row in rows] == [
        {
            "cid": "CID 29",
            "name": "Acquisition Modality",
            "extensibility": "EXTENSIBLE",
            "version": "20260101",
            "row_order": 1,
            "coding_scheme_designator": "DCM",
            "coding_scheme_version": None,
            "code_value": "CT",
            "code_meaning": "Computed Tomography",
            "include_cid": None,
            "part": "PS3.16",
            "table_id": "table_16-3",
        },
        {
            "cid": "CID 29",
            "name": "Acquisition Modality",
            "extensibility": "EXTENSIBLE",
            "version": "20260101",
            "row_order": 2,
            "coding_scheme_designator": None,
            "coding_scheme_version": None,
            "code_value": None,
            "code_meaning": None,
            "include_cid": "CID 30",
            "part": "PS3.16",
            "table_id": "table_16-3",
        },
    ]


def test_import_coded_concepts_persists_complete_context_group_codes(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS316_CONTENT_MAPPING_DOCBOOK, part="PS3.16")
    parsed = parse_part16(document, edition="2026b")

    summary = import_coded_concepts(
        connection,
        edition="2026b",
        coded_concepts=parsed.coded_concepts,
    )

    assert summary.coded_concepts == 1
    assert summary.source_refs == 1
    rows = connection.execute(
        """
        SELECT concept.code_value, concept.coding_scheme_designator,
               concept.coding_scheme_version, concept.code_meaning,
               ref.part, ref.table_id
        FROM coded_concept concept
        JOIN source_ref ref ON ref.id = concept.source_ref_id
        WHERE concept.edition_id = ?
        ORDER BY concept.code_value
        """,
        ("2026b",),
    ).fetchall()
    assert [dict(row) for row in rows] == [
        {
            "code_value": "CT",
            "coding_scheme_designator": "DCM",
            "coding_scheme_version": "",
            "code_meaning": "Computed Tomography",
            "part": "PS3.16",
            "table_id": "table_16-3",
        },
    ]


def test_part16_docbook_structure_persists_nodes_refs_and_raw_table_ir(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS316_CONTENT_MAPPING_DOCBOOK, part="PS3.16")

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
        ("sect_16_1",),
    ).fetchone()
    assert dict(section) == {
        "title": "Template Overview",
        "part": "PS3.16",
        "xml_id": "sect_16_1",
    }

    raw_table = connection.execute(
        """
        SELECT ir.ir_json, ir.ir_sha256, ref.part, ref.table_id
        FROM raw_table_ir ir
        JOIN source_ref ref ON ref.id = ir.source_ref_id
        WHERE ir.table_id = ?
        """,
        ("table_16-1",),
    ).fetchone()
    payload = json.loads(raw_table["ir_json"])
    assert payload["title"] == "Synthetic Template Rows"
    assert payload["rows"][1]["cells"][0]["text"] == "1500"
    assert len(raw_table["ir_sha256"]) == 64
    assert raw_table["part"] == "PS3.16"
    assert raw_table["table_id"] == "table_16-1"
