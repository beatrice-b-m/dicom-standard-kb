import json
import sqlite3
from pathlib import Path

import pytest

from dicom_kb.db.importers import (
    import_docbook_structure,
    import_part03,
    import_part04,
    import_part06,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.db.repositories import (
    DataElementRepository,
    Part04Repository,
    UIDRepository,
)
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part03_iods import parse_part03
from dicom_kb.parsers.part04_sop_classes import parse_part04
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from tests.fixtures_synthetic import (
    PS33_CT_IMAGE_DOCBOOK,
    PS34_SOP_CLASSES_DOCBOOK,
    PS36_REGISTRY_DOCBOOK,
)


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    return connection


def test_import_part06_and_lookup_tag_uid(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    parsed = parse_part06(
        parse_docbook_xml(PS36_REGISTRY_DOCBOOK, part="PS3.6"), edition="2026b"
    )

    summary = import_part06(
        connection,
        edition="2026b",
        data_elements=parsed.data_elements,
        uid_registry_entries=parsed.uid_registry_entries,
    )

    assert summary.data_elements == 7
    assert summary.uid_registry_entries == 2
    element, warning = DataElementRepository(connection).find_by_tag_or_keyword(
        "Modality", edition="2026b"
    )
    assert warning is None
    assert element is not None
    assert element.tag == "(0008,0060)"

    uid = UIDRepository(connection).find_by_uid_or_keyword(
        "ExplicitVRLittleEndian", edition="2026b"
    )
    assert uid is not None
    assert uid.uid_value == "1.2.840.10008.1.2.1"


def test_import_docbook_structure_persists_nodes_xrefs_and_table_ir(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3")

    summary = import_docbook_structure(
        connection,
        edition="2026b",
        document=document,
    )

    assert summary.doc_nodes == 10
    assert summary.xrefs == 2
    assert summary.raw_table_irs == 4

    section = connection.execute(
        """
        SELECT child.title, parent.xml_id AS parent_xml_id
        FROM doc_node child
        JOIN doc_node parent ON parent.id = child.parent_id
        WHERE child.xml_id = ?
        """,
        ("sect_A.3",),
    ).fetchone()
    assert section["title"] == "CT Image IOD"
    assert section["parent_xml_id"] == "chapter_A"

    table = connection.execute(
        """
        SELECT table_node.title, parent.xml_id AS parent_xml_id
        FROM doc_node table_node
        JOIN doc_node parent ON parent.id = table_node.parent_id
        WHERE table_node.xml_id = ?
        """,
        ("table_A.3-1",),
    ).fetchone()
    assert table["title"] == "CT Image IOD Modules"
    assert table["parent_xml_id"] == "sect_A.3"

    xref = connection.execute(
        """
        SELECT resolved, target_node_id, resolution_warning
        FROM xref
        WHERE target_ref = ?
        """,
        ("table_10-7",),
    ).fetchone()
    assert xref["resolved"] == 1
    assert xref["target_node_id"] == "2026b.PS3.3.table_10-7"
    assert xref["resolution_warning"] is None

    raw_table = connection.execute(
        """
        SELECT ir_json, ir_sha256
        FROM raw_table_ir
        WHERE table_id = ?
        """,
        ("table_A.3-1",),
    ).fetchone()
    payload = json.loads(raw_table["ir_json"])
    assert payload["title"] == "CT Image IOD Modules"
    assert payload["rows"][1]["cells"][1]["text"] == "Patient"
    assert len(raw_table["ir_sha256"]) == 64

    fts_match = connection.execute(
        """
        SELECT node_id
        FROM doc_node_fts
        WHERE doc_node_fts MATCH ?
        ORDER BY node_id
        LIMIT 1
        """,
        ('"Patient" AND "name"',),
    ).fetchone()
    assert fts_match["node_id"] == "2026b.PS3.3.sect_C.7.1.1"


def test_range_tag_lookup_returns_match_warning(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    parsed = parse_part06(
        parse_docbook_xml(PS36_REGISTRY_DOCBOOK, part="PS3.6"), edition="2026b"
    )
    import_part06(
        connection,
        edition="2026b",
        data_elements=parsed.data_elements,
        uid_registry_entries=parsed.uid_registry_entries,
    )

    element, warning = DataElementRepository(connection).find_by_tag_or_keyword(
        "(6002,3000)", edition="2026b"
    )

    assert element is not None
    assert element.tag == "(60xx,3000)"
    assert warning == "concrete tag (6002,3000) matched range row (60xx,3000)"


def test_import_rolls_back_on_duplicate_tags(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    parsed = parse_part06(
        parse_docbook_xml(PS36_REGISTRY_DOCBOOK, part="PS3.6"), edition="2026b"
    )
    duplicate = parsed.data_elements[0].model_copy(update={"id": "duplicate"})

    with pytest.raises(ImportError):
        import_part06(
            connection,
            edition="2026b",
            data_elements=[*parsed.data_elements, duplicate],
            uid_registry_entries=parsed.uid_registry_entries,
        )

    count = connection.execute("SELECT count(*) FROM data_element").fetchone()[0]
    assert count == 0


def test_imports_keep_editions_isolated(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    parsed_2026b = parse_part06(
        parse_docbook_xml(PS36_REGISTRY_DOCBOOK, part="PS3.6"), edition="2026b"
    )
    parsed_2026c = parse_part06(
        parse_docbook_xml(PS36_REGISTRY_DOCBOOK, part="PS3.6"), edition="2026c"
    )
    import_part06(
        connection,
        edition="2026b",
        data_elements=parsed_2026b.data_elements,
        uid_registry_entries=parsed_2026b.uid_registry_entries,
    )
    import_part06(
        connection,
        edition="2026c",
        data_elements=parsed_2026c.data_elements,
        uid_registry_entries=parsed_2026c.uid_registry_entries,
    )

    count = connection.execute("SELECT count(*) FROM data_element").fetchone()[0]
    assert count == 14


def test_import_part03_graph_records(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    parsed = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"), edition="2026b"
    )

    summary = import_part03(
        connection,
        edition="2026b",
        iods=parsed.iods,
        modules=parsed.modules,
        macros=parsed.macros,
        iod_module_uses=parsed.iod_module_uses,
        iod_functional_group_uses=parsed.iod_functional_group_uses,
        attribute_uses=parsed.attribute_uses,
    )

    assert summary.iods == 2
    assert summary.modules == 3
    assert summary.macros == 1
    assert summary.iod_module_uses == 3
    assert summary.iod_functional_group_uses == 1
    assert summary.attribute_uses == 5

    required_modules = connection.execute(
        """
        SELECT m.name, imu.usage
        FROM iod_module_use imu
        JOIN module m ON m.id = imu.module_id
        WHERE imu.iod_id = ?
        ORDER BY imu.id
        """,
        ("2026b.iod.ct_image",),
    ).fetchall()
    assert [(row["name"], row["usage"]) for row in required_modules] == [
        ("Patient", "M"),
        ("Contrast/Bolus", "C"),
        ("CT Image", "M"),
    ]

    include = connection.execute(
        """
        SELECT au.row_kind, au.included_macro_id, au.include_target_text
        FROM attribute_use au
        WHERE au.owner_id = ? AND au.row_kind = 'include'
        """,
        ("2026b.module.patient",),
    ).fetchone()
    assert include["included_macro_id"] == "2026b.macro.table_10_7"
    assert include["include_target_text"] == (
        'Include Table 10-7 "General Anatomy Optional Macro"'
    )

    nested = connection.execute(
        """
        SELECT child.parent_attribute_use_id, parent.attribute_name AS parent_name
        FROM attribute_use child
        JOIN attribute_use parent ON parent.id = child.parent_attribute_use_id
        WHERE child.attribute_name = 'Referenced SOP Class UID'
        """
    ).fetchone()
    assert nested["parent_name"] == "Referenced Patient Sequence"


def test_import_part03_rolls_back_on_duplicate_iods(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    parsed = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"), edition="2026b"
    )
    duplicate = parsed.iods[0].model_copy(update={"id": "duplicate"})

    with pytest.raises(ImportError):
        import_part03(
            connection,
            edition="2026b",
            iods=[*parsed.iods, duplicate],
            modules=parsed.modules,
            macros=parsed.macros,
            iod_module_uses=parsed.iod_module_uses,
            iod_functional_group_uses=parsed.iod_functional_group_uses,
            attribute_uses=parsed.attribute_uses,
        )

    count = connection.execute("SELECT count(*) FROM iod").fetchone()[0]
    assert count == 0


def test_import_part04_sop_class_records(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    parsed_part03 = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"), edition="2026b"
    )
    import_part03(
        connection,
        edition="2026b",
        iods=parsed_part03.iods,
        modules=parsed_part03.modules,
        macros=parsed_part03.macros,
        iod_module_uses=parsed_part03.iod_module_uses,
        iod_functional_group_uses=parsed_part03.iod_functional_group_uses,
        attribute_uses=parsed_part03.attribute_uses,
    )
    parsed_part04 = parse_part04(
        parse_docbook_xml(PS34_SOP_CLASSES_DOCBOOK, part="PS3.4"), edition="2026b"
    )

    summary = import_part04(
        connection,
        edition="2026b",
        service_classes=parsed_part04.service_classes,
        sop_classes=parsed_part04.sop_classes,
        sop_class_iods=parsed_part04.sop_class_iods,
    )

    assert summary.service_classes == 1
    assert summary.sop_classes == 2
    assert summary.sop_class_iods == 2

    repository = Part04Repository(connection)
    found = repository.find_sop_class_by_uid_or_name(
        "CT Image Storage", edition="2026b"
    )
    assert found is not None
    sop_class, service_class = found
    assert sop_class.uid_value == "1.2.840.10008.5.1.4.1.1.2"
    assert service_class is not None
    assert service_class.name == "Storage Service Class"

    iods = repository.list_iods_for_sop_class(sop_class.id, edition="2026b")
    assert [record.iod.name for record in iods] == ["CT Image"]
    assert iods[0].edge.resolution == "parsed"


def test_import_part04_rolls_back_without_referenced_iods(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    parsed_part04 = parse_part04(
        parse_docbook_xml(PS34_SOP_CLASSES_DOCBOOK, part="PS3.4"), edition="2026b"
    )

    with pytest.raises(ImportError):
        import_part04(
            connection,
            edition="2026b",
            service_classes=parsed_part04.service_classes,
            sop_classes=parsed_part04.sop_classes,
            sop_class_iods=parsed_part04.sop_class_iods,
        )

    count = connection.execute("SELECT count(*) FROM sop_class").fetchone()[0]
    assert count == 0
