from __future__ import annotations

import sqlite3
from pathlib import Path

from dicom_kb.db.importers import (
    import_attribute_value_terms,
    import_docbook_structure,
    import_part03,
    import_part04,
    import_part06,
    import_transfer_syntax_details,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part03_iods import parse_part03
from dicom_kb.parsers.part04_sop_classes import parse_part04
from dicom_kb.parsers.part05_encoding import TransferSyntaxUID, parse_transfer_syntaxes
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from dicom_kb.query.markdown import render_markdown
from dicom_kb.query.resolver import (
    element_usage,
    iod_modules,
    module_attributes,
    read_standard,
    search_standard,
)
from tests.fixtures_synthetic import (
    EDITION,
    PS33_CT_IMAGE_DOCBOOK,
    PS34_SOP_CLASSES_DOCBOOK,
    PS35_ENCODING_DOCBOOK,
    PS36_REGISTRY_DOCBOOK,
)


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    parsed = parse_part06(
        parse_docbook_xml(PS36_REGISTRY_DOCBOOK, part="PS3.6"),
        edition=EDITION,
    )
    import_part06(
        connection,
        edition=EDITION,
        data_elements=parsed.data_elements,
        uid_registry_entries=parsed.uid_registry_entries,
    )
    return connection


def _doc_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    document = parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3")
    import_docbook_structure(
        connection,
        edition=EDITION,
        document=document,
    )
    return connection


def _context_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = _connection(tmp_path)
    parsed_part03 = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"),
        edition=EDITION,
    )
    import_part03(
        connection,
        edition=EDITION,
        iods=parsed_part03.iods,
        modules=parsed_part03.modules,
        macros=parsed_part03.macros,
        iod_module_uses=parsed_part03.iod_module_uses,
        iod_functional_group_uses=parsed_part03.iod_functional_group_uses,
        attribute_uses=parsed_part03.attribute_uses,
        conditions=parsed_part03.conditions,
    )
    import_attribute_value_terms(
        connection,
        edition=EDITION,
        document=parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"),
    )
    parsed_part04 = parse_part04(
        parse_docbook_xml(PS34_SOP_CLASSES_DOCBOOK, part="PS3.4"),
        edition=EDITION,
        iod_id_by_ref={
            "sect_A.3": f"{EDITION}.iod.ct_image",
            "sect_A.38": f"{EDITION}.iod.enhanced_ct_image",
        },
    )
    import_part04(
        connection,
        edition=EDITION,
        service_classes=parsed_part04.service_classes,
        sop_classes=parsed_part04.sop_classes,
        sop_class_iods=parsed_part04.sop_class_iods,
    )
    return connection


def test_v1_tool_responses_render_markdown_with_source(tmp_path: Path) -> None:
    registry_connection = _connection(tmp_path / "registry")
    context_connection = _context_connection(tmp_path / "context")
    document_connection = _doc_connection(tmp_path / "document")

    responses = [
        read_standard(
            registry_connection, reference="ExplicitVRLittleEndian", edition=EDITION
        ),
        element_usage(context_connection, name="PatientName", edition=EDITION),
        element_usage(
            context_connection, name="PatientName", iod="CT Image", edition=EDITION
        ),
        iod_modules(context_connection, name="CT Image Storage", edition=EDITION),
        iod_modules(context_connection, name="CT Image", expand=True, edition=EDITION),
        module_attributes(context_connection, name="Patient", edition=EDITION),
        read_standard(
            document_connection,
            reference="PS3.3 A.3",
            edition=EDITION,
        ),
        search_standard(
            document_connection,
            query="Patient",
            edition=EDITION,
        ),
    ]

    for response in responses:
        assert response.status == "ok"
        markdown = render_markdown(response)
        assert markdown.rstrip().splitlines()[-1].startswith("Source: PS3.")
        assert markdown.rstrip().endswith(f"({EDITION})")
        assert "{" not in markdown


def _encoding_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS35_ENCODING_DOCBOOK, part="PS3.5")
    import_docbook_structure(connection, edition=EDITION, document=document)
    uids = [
        TransferSyntaxUID(uid=str(row["uid_value"]), retired=bool(row["retired"]))
        for row in connection.execute(
            "SELECT uid_value, retired FROM uid_registry_entry "
            "WHERE uid_type = 'Transfer Syntax'"
        )
    ]
    parsed = parse_transfer_syntaxes(document, edition=EDITION, transfer_syntaxes=uids)
    import_transfer_syntax_details(
        connection, edition=EDITION, transfer_syntax_details=parsed.details
    )
    return connection


def _read(connection: sqlite3.Connection, reference: str) -> str:
    response = read_standard(connection, reference=reference, edition=EDITION)
    assert response.status == "ok", response.result
    return render_markdown(response)


def test_read_transfer_syntax_uid_gives_encoding_facts(tmp_path: Path) -> None:
    markdown = _read(_encoding_connection(tmp_path), "1.2.840.10008.1.2.4.50")

    assert markdown.startswith("**1.2.840.10008.1.2.4.50** JPEG Baseline")
    assert "| Explicit VR | Little Endian | Encapsulated | No |" in markdown
    assert "Rules: PS3.5 Section A.4.1 JPEG Image Compression" in markdown
    assert "Also named in: PS3.5 Table A.4-3" in markdown
    assert markdown.rstrip().endswith(
        f"Source: PS3.6 Table A-1; PS3.5 Section A.4.1 ({EDITION})"
    )


def test_read_transfer_syntax_by_keyword_or_name(tmp_path: Path) -> None:
    connection = _encoding_connection(tmp_path)

    deflated = _read(connection, "DeflatedExplicitVRLittleEndian")
    implicit = _read(
        connection, "Implicit VR Little Endian: Default Transfer Syntax for DICOM"
    )

    assert "| Explicit VR | Little Endian | Native | Whole Data Set |" in deflated
    assert "| Implicit VR | Little Endian | Native | No |" in implicit
    assert "Also named in: PS3.5 Section 10.1" in implicit


def test_read_retired_transfer_syntax_says_it_is_no_longer_specified(
    tmp_path: Path,
) -> None:
    markdown = _read(_encoding_connection(tmp_path), "1.2.840.10008.1.2.2")

    assert "Explicit VR Big Endian (retired)" in markdown
    assert f"Retired: PS3.5 ({EDITION}) no longer specifies its encoding." in markdown


def test_read_vr_gives_its_table_row_and_header_layout(tmp_path: Path) -> None:
    connection = _encoding_connection(tmp_path)

    ob = _read(connection, "OB")
    pn = _read(connection, "VR pn")

    assert ob.startswith("**OB** Other Byte")
    assert "**Length of Value:** 2^32-2 bytes maximum." in ob
    assert (
        "2 reserved bytes (0000H), then a 32-bit Value Length (PS3.5 Table 7.1-1)" in ob
    )
    assert "VR, then a 16-bit Value Length (PS3.5 Table 7.1-2)" in pn
    assert ob.rstrip().endswith(
        f"Source: PS3.5 Table 6.2-1; PS3.5 Table 7.1-1 ({EDITION})"
    )


def test_read_unknown_vr_or_uid_falls_back_to_sections(tmp_path: Path) -> None:
    connection = _encoding_connection(tmp_path)

    unknown_vr = read_standard(connection, reference="VR QQ", edition=EDITION)
    section = read_standard(connection, reference="PS3.5 10.1", edition=EDITION)

    assert unknown_vr.status == "not_found"
    assert section.status == "ok"
    assert "Default Transfer Syntax" in render_markdown(section)
