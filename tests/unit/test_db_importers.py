import sqlite3
from pathlib import Path

import pytest

from dicom_kb.db.importers import import_part06
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.db.repositories import DataElementRepository, UIDRepository
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from tests.unit.test_part06_parser import PS36_FIXTURE


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    return connection


def test_import_part06_and_lookup_tag_uid(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    parsed = parse_part06(
        parse_docbook_xml(PS36_FIXTURE, part="PS3.6"), edition="2026b"
    )

    summary = import_part06(
        connection,
        edition="2026b",
        data_elements=parsed.data_elements,
        uid_registry_entries=parsed.uid_registry_entries,
    )

    assert summary.data_elements == 3
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


def test_range_tag_lookup_returns_match_warning(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    parsed = parse_part06(
        parse_docbook_xml(PS36_FIXTURE, part="PS3.6"), edition="2026b"
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
        parse_docbook_xml(PS36_FIXTURE, part="PS3.6"), edition="2026b"
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
        parse_docbook_xml(PS36_FIXTURE, part="PS3.6"), edition="2026b"
    )
    parsed_2026c = parse_part06(
        parse_docbook_xml(PS36_FIXTURE, part="PS3.6"), edition="2026c"
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
    assert count == 6
