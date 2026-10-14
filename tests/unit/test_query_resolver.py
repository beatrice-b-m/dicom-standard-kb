from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from dicom_kb.db.importers import (
    import_attribute_value_terms,
    import_dicom_media_types,
    import_dicomweb_transactions,
    import_docbook_structure,
    import_part03,
    import_part04,
    import_part06,
    import_transfer_syntax_details,
    import_vr_definitions,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part03_iods import parse_part03
from dicom_kb.parsers.part04_sop_classes import parse_part04
from dicom_kb.parsers.part05_encoding import (
    parse_part05,
    transfer_syntax_details_from_uid_registry,
)
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from dicom_kb.parsers.part10_media_storage import parse_part10
from dicom_kb.parsers.part18_web_services import parse_part18
from dicom_kb.query.markdown import render_markdown
from dicom_kb.query.resolver import (
    element_usage,
    explain_encoding_rule,
    iod_modules,
    lookup_dicomweb_transaction,
    lookup_media_type,
    lookup_transfer_syntax,
    lookup_uid,
    lookup_vr,
    module_attributes,
    read_standard,
    search_standard,
)
from tests.fixtures_synthetic import (
    PS33_CT_IMAGE_DOCBOOK,
    PS34_SOP_CLASSES_DOCBOOK,
    PS35_ENCODING_DOCBOOK,
    PS36_REGISTRY_DOCBOOK,
    PS37_MESSAGES_DOCBOOK,
    PS38_NETWORK_DOCBOOK,
    PS310_MEDIA_STORAGE_DOCBOOK,
    PS318_OFFICIAL_SHAPE_DOCBOOK,
    PS318_WEB_SERVICES_DOCBOOK,
)

RESOLVED_AT = datetime(2026, 6, 11, tzinfo=UTC)


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
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
    return connection


def _part03_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    parsed = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"),
        edition="2026b",
    )
    import_part03(
        connection,
        edition="2026b",
        iods=parsed.iods,
        modules=parsed.modules,
        macros=parsed.macros,
        iod_module_uses=parsed.iod_module_uses,
        iod_functional_group_uses=parsed.iod_functional_group_uses,
        attribute_uses=parsed.attribute_uses,
        conditions=parsed.conditions,
    )
    return connection


def _doc_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    document = parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3")
    import_docbook_structure(
        connection,
        edition="2026b",
        document=document,
    )
    return connection


def _part07_doc_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    document = parse_docbook_xml(PS37_MESSAGES_DOCBOOK, part="PS3.7")
    import_docbook_structure(
        connection,
        edition="2026b",
        document=document,
    )
    return connection


def _part08_doc_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    document = parse_docbook_xml(PS38_NETWORK_DOCBOOK, part="PS3.8")
    import_docbook_structure(
        connection,
        edition="2026b",
        document=document,
    )
    return connection


def _part05_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = _connection(tmp_path)
    parsed_part05 = parse_part05(
        parse_docbook_xml(PS35_ENCODING_DOCBOOK, part="PS3.5"),
        edition="2026b",
    )
    import_docbook_structure(
        connection,
        edition="2026b",
        document=parse_docbook_xml(PS35_ENCODING_DOCBOOK, part="PS3.5"),
    )
    import_vr_definitions(
        connection,
        edition="2026b",
        vr_definitions=parsed_part05.vr_definitions,
    )
    parsed_part06 = parse_part06(
        parse_docbook_xml(PS36_REGISTRY_DOCBOOK, part="PS3.6"),
        edition="2026b",
    )
    import_transfer_syntax_details(
        connection,
        edition="2026b",
        transfer_syntax_details=transfer_syntax_details_from_uid_registry(
            edition="2026b",
            uid_registry_entries=parsed_part06.uid_registry_entries,
        ),
    )
    return connection


def _part10_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    document = parse_docbook_xml(PS310_MEDIA_STORAGE_DOCBOOK, part="PS3.10")
    parsed_part10 = parse_part10(document, edition="2026b")
    import_docbook_structure(
        connection,
        edition="2026b",
        document=document,
    )
    import_dicom_media_types(
        connection,
        edition="2026b",
        media_types=parsed_part10.media_types,
    )
    return connection


def _part18_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    document = parse_docbook_xml(PS318_WEB_SERVICES_DOCBOOK, part="PS3.18")
    parsed_part18 = parse_part18(document, edition="2026b")
    import_docbook_structure(
        connection,
        edition="2026b",
        document=document,
    )
    import_dicomweb_transactions(
        connection,
        edition="2026b",
        transactions=parsed_part18.dicomweb_transactions,
    )
    import_dicom_media_types(
        connection,
        edition="2026b",
        media_types=parsed_part18.media_types,
    )
    return connection


def _part10_part18_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = _part10_connection(tmp_path)
    document = parse_docbook_xml(PS318_WEB_SERVICES_DOCBOOK, part="PS3.18")
    parsed_part18 = parse_part18(document, edition="2026b")
    import_docbook_structure(
        connection,
        edition="2026b",
        document=document,
    )
    import_dicomweb_transactions(
        connection,
        edition="2026b",
        transactions=parsed_part18.dicomweb_transactions,
    )
    import_dicom_media_types(
        connection,
        edition="2026b",
        media_types=parsed_part18.media_types,
    )
    return connection


def _part18_official_shape_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    document = parse_docbook_xml(PS318_OFFICIAL_SHAPE_DOCBOOK, part="PS3.18")
    parsed_part18 = parse_part18(document, edition="2026b")
    import_docbook_structure(
        connection,
        edition="2026b",
        document=document,
    )
    import_dicomweb_transactions(
        connection,
        edition="2026b",
        transactions=parsed_part18.dicomweb_transactions,
    )
    import_dicom_media_types(
        connection,
        edition="2026b",
        media_types=parsed_part18.media_types,
    )
    return connection


def _context_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = _connection(tmp_path)
    parsed_part03 = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"),
        edition="2026b",
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
        conditions=parsed_part03.conditions,
    )
    import_attribute_value_terms(
        connection,
        edition="2026b",
        document=parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"),
    )
    parsed_part04 = parse_part04(
        parse_docbook_xml(PS34_SOP_CLASSES_DOCBOOK, part="PS3.4"),
        edition="2026b",
        iod_id_by_ref={
            "sect_A.3": "2026b.iod.ct_image",
            "sect_A.38": "2026b.iod.enhanced_ct_image",
        },
    )
    import_part04(
        connection,
        edition="2026b",
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
        lookup_uid(
            registry_connection,
            uid_or_keyword="ExplicitVRLittleEndian",
            edition="2026b",
        ),
        element_usage(context_connection, name="PatientName", edition="2026b"),
        element_usage(
            context_connection, name="PatientName", iod="CT Image", edition="2026b"
        ),
        iod_modules(context_connection, name="CT Image Storage", edition="2026b"),
        iod_modules(context_connection, name="CT Image", expand=True, edition="2026b"),
        module_attributes(context_connection, name="Patient", edition="2026b"),
        read_standard(
            document_connection,
            reference="PS3.3 A.3",
            edition="2026b",
        ),
        search_standard(
            document_connection,
            query="Patient",
            edition="2026b",
        ),
    ]

    for response in responses:
        assert response.status == "ok"
        markdown = render_markdown(response)
        assert markdown.rstrip().splitlines()[-1].startswith("Source: PS3.")
        assert markdown.rstrip().endswith("(2026b)")
        assert "{" not in markdown


def test_lookup_uid_reports_retired_entry(tmp_path: Path) -> None:
    response = lookup_uid(
        _connection(tmp_path),
        uid_or_keyword="ExplicitVRBigEndian",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result == {
        "uid_value": "1.2.840.10008.1.2.2",
        "uid_name": "Explicit VR Big Endian",
        "uid_keyword": "ExplicitVRBigEndian",
        "uid_type": "Transfer Syntax",
        "part": "PS3.5",
        "retired": True,
    }
    assert response.refs[0].part == "PS3.6"


def test_lookup_vr_returns_ps35_definition(tmp_path: Path) -> None:
    response = lookup_vr(
        _part05_connection(tmp_path),
        vr="pn",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result == {
        "vr": "PN",
        "name": "Person Name",
        "value_representation_class": "character string",
        "length_notes": ["variable length"],
        "padding_behavior": "space padded",
        "character_repertoire_notes": [
            "uses the default character repertoire",
        ],
        "binary_or_text": "text",
    }
    assert response.refs[0].part == "PS3.5"
    assert response.refs[0].table == "Synthetic VR Behaviors"


def test_lookup_vr_validates_code_and_reports_not_found(tmp_path: Path) -> None:
    connection = _part05_connection(tmp_path)

    malformed = lookup_vr(connection, vr="PERSON", edition="2026b")
    missing = lookup_vr(connection, vr="AE", edition="2026b")

    assert malformed.status == "validation_error"
    assert malformed.result is not None
    assert "two-letter" in str(malformed.result["message"])
    assert missing.status == "not_found"
    assert missing.result == {"message": "No PS3.5 VR definition matched the input."}


def test_lookup_transfer_syntax_returns_uid_metadata_and_encoding_details(
    tmp_path: Path,
) -> None:
    response = lookup_transfer_syntax(
        _part05_connection(tmp_path),
        uid_or_keyword="ExplicitVRLittleEndian",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result == {
        "uid_value": "1.2.840.10008.1.2.1",
        "uid_name": "Explicit VR Little Endian",
        "uid_keyword": "ExplicitVRLittleEndian",
        "explicit_vr": True,
        "endian": "little",
        "encapsulated": False,
        "compression_family": None,
        "retired": False,
        "encoding_notes": [],
    }
    assert {ref.part for ref in response.refs} == {"PS3.6"}


def test_lookup_transfer_syntax_validates_uid_and_reports_not_found(
    tmp_path: Path,
) -> None:
    connection = _part05_connection(tmp_path)

    malformed = lookup_transfer_syntax(
        connection,
        uid_or_keyword="1.2.bad",
        edition="2026b",
    )
    missing = lookup_transfer_syntax(
        connection,
        uid_or_keyword="1.2.840.10008.999",
        edition="2026b",
    )

    assert malformed.status == "validation_error"
    assert malformed.result is not None
    assert "malformed DICOM UID" in malformed.result["message"]
    assert missing.status == "not_found"
    assert missing.result == {"message": "No transfer syntax detail matched the input."}


def test_explain_encoding_rule_uses_structured_vr_rows(tmp_path: Path) -> None:
    response = explain_encoding_rule(
        _part05_connection(tmp_path),
        topic="OB",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["summary"] == "OB is the Other Byte VR."
    assert response.result["structured_facts"] == [
        "name: Other Byte",
        "value representation class: byte string",
        "binary or text: binary",
        "padding behavior: null padded",
        "length note: variable length",
    ]
    assert response.refs[0].part == "PS3.5"


def test_explain_encoding_rule_uses_transfer_syntax_details(
    tmp_path: Path,
) -> None:
    response = explain_encoding_rule(
        _part05_connection(tmp_path),
        topic="JPEG Baseline (Process 1)",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["structured_facts"] == [
        "encapsulated: true",
        "compression family: jpeg",
        "encoding note: jpeg compressed transfer syntax",
        "encoding note: encapsulated pixel data",
    ]
    assert response.refs[0].part == "PS3.6"


def test_explain_encoding_rule_falls_back_to_cited_ps35_text(
    tmp_path: Path,
) -> None:
    response = explain_encoding_rule(
        _part05_connection(tmp_path),
        topic="Encoding Overview",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["text_excerpt"]
    assert response.refs[0].part == "PS3.5"


def test_explain_encoding_rule_validates_empty_topic(tmp_path: Path) -> None:
    response = explain_encoding_rule(
        _part05_connection(tmp_path),
        topic="   ",
        edition="2026b",
    )

    assert response.status == "validation_error"
    assert response.result == {"message": "topic must not be empty."}


def test_lookup_media_type_returns_ps310_media_type_row(tmp_path: Path) -> None:
    response = lookup_media_type(
        _part10_connection(tmp_path),
        media_type_or_context="application/dicom",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result == {
        "media_type": "application/dicom",
        "service_context": "PS3.10 file",
        "transfer_syntax_constraints": [
            "Encoded using the Transfer Syntax UID in the File Meta Information",
        ],
        "directions": ["file"],
    }
    assert response.refs[0].part == "PS3.10"
    assert response.refs[0].table == "Synthetic Media Types"


def test_lookup_media_type_matches_ps310_context(tmp_path: Path) -> None:
    response = lookup_media_type(
        _part10_connection(tmp_path),
        media_type_or_context="file",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["media_type"] == "application/dicom"
    assert response.result["service_context"] == "PS3.10 file"


def test_lookup_media_type_matches_ps318_dicomweb_context(tmp_path: Path) -> None:
    response = lookup_media_type(
        _part18_connection(tmp_path),
        media_type_or_context="STOW-RS request",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result == {
        "media_type": "multipart/related",
        "service_context": "STOW-RS request",
        "transfer_syntax_constraints": [
            "Each part supplies a DICOM instance payload",
        ],
        "directions": ["request"],
    }
    assert response.refs[0].part == "PS3.18"
    assert response.refs[0].table == "Synthetic DICOMweb Media Types"
    assert response.refs[0].anchor == "table_18-2"


def test_lookup_media_type_prefers_instance_media_types_for_exact_match(
    tmp_path: Path,
) -> None:
    response = lookup_media_type(
        _part10_part18_connection(tmp_path),
        media_type_or_context="application/dicom",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result == {
        "media_type": "application/dicom",
        "service_context": "Instance Media Types",
        "transfer_syntax_constraints": [
            "Explicit VR Little Endian required for single-instance media",
        ],
        "directions": ["response"],
    }
    assert response.refs[0].part == "PS3.18"
    assert response.refs[0].anchor == "table_18-2"


def test_lookup_media_type_returns_official_shape_application_dicom(
    tmp_path: Path,
) -> None:
    response = lookup_media_type(
        _part18_official_shape_connection(tmp_path),
        media_type_or_context="application/dicom",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result == {
        "media_type": "application/dicom",
        "service_context": "Instance Media Types",
        "transfer_syntax_constraints": [
            "1.2.840.10008.1.2.1 Explicit VR Little Endian (D)",
        ],
        "directions": ["response"],
    }
    assert response.refs[0].part == "PS3.18"
    assert response.refs[0].anchor == "table_8.7.3-2"


def test_lookup_media_type_returns_official_shape_wado_response_context(
    tmp_path: Path,
) -> None:
    response = lookup_media_type(
        _part18_official_shape_connection(tmp_path),
        media_type_or_context="WADO-RS response",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result == {
        "media_type": "multipart/related",
        "service_context": "WADO-RS response",
        "transfer_syntax_constraints": [
            "Retrieve response payload: Instance(s), Metadata, Renderings, "
            "Pixel Data, or Bulk Data",
        ],
        "directions": ["response"],
    }
    assert response.refs[0].part == "PS3.18"
    assert response.refs[0].anchor == "table_10.4.1-1"


def test_lookup_media_type_returns_official_shape_stow_request_context(
    tmp_path: Path,
) -> None:
    response = lookup_media_type(
        _part18_official_shape_connection(tmp_path),
        media_type_or_context="STOW-RS request",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result == {
        "media_type": "multipart/related",
        "service_context": "STOW-RS request",
        "transfer_syntax_constraints": [
            "Store request payload: DICOM Instances",
        ],
        "directions": ["request"],
    }
    assert response.refs[0].part == "PS3.18"
    assert response.refs[0].anchor == "table_10.5.1-1"


def test_lookup_media_type_validates_empty_input_and_reports_not_found(
    tmp_path: Path,
) -> None:
    connection = _part10_connection(tmp_path)

    empty = lookup_media_type(
        connection,
        media_type_or_context="  ",
        edition="2026b",
    )
    missing = lookup_media_type(
        connection,
        media_type_or_context="application/not-dicom",
        edition="2026b",
    )

    assert empty.status == "validation_error"
    assert empty.result == {"message": "media_type_or_context must not be empty."}
    assert missing.status == "not_found"
    assert missing.result == {"message": "No DICOM media type matched the input."}


def test_lookup_media_type_falls_back_to_cited_ps310_text_for_prose_rule(
    tmp_path: Path,
) -> None:
    response = lookup_media_type(
        _part10_connection(tmp_path),
        media_type_or_context="File Preamble",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["part"] == "PS3.10"
    assert response.result["section"] == "table_10-3"
    assert response.result["title"] == "Synthetic Media Storage Notes"
    assert "Prose-only rule" in str(response.result["text_excerpt"])
    assert response.refs[0].part == "PS3.10"
    assert response.warnings == [
        "No parsed media-type row matched; returning bounded PS3.10 text fallback."
    ]


def test_lookup_media_type_returns_candidates_for_multiple_contexts(
    tmp_path: Path,
) -> None:
    connection = _part10_connection(tmp_path)
    connection.execute(
        """
        INSERT INTO source_ref (id, edition_id, part, title)
        VALUES (?, ?, ?, ?)
        """,
        (
            "2026b.PS3.18.table_8.7-1",
            "2026b",
            "PS3.18",
            "Synthetic PS3.18 Media Types",
        ),
    )
    connection.execute(
        """
        INSERT INTO dicom_media_type (
          id, edition_id, media_type, service_context,
          transfer_syntax_constraints_json, directions_json, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026b.PS3.18.media_type.application_dicom",
            "2026b",
            "application/dicom",
            "PS3.18 rendered request",
            json.dumps(("Explicit transfer syntax only",), separators=(",", ":")),
            json.dumps(("request",), separators=(",", ":")),
            "2026b.PS3.18.table_8.7-1",
        ),
    )

    response = lookup_media_type(
        connection,
        media_type_or_context="application/dicom",
        edition="2026b",
    )

    assert response.status == "validation_error"
    assert response.result is not None
    assert response.result["message"] == "Media type input matched multiple contexts."
    assert response.result["candidates"] == [
        {
            "media_type": "application/dicom",
            "service_context": "PS3.10 file",
            "transfer_syntax_constraints": [
                "Encoded using the Transfer Syntax UID in the File Meta Information",
            ],
            "directions": ["file"],
        },
        {
            "media_type": "application/dicom",
            "service_context": "PS3.18 rendered request",
            "transfer_syntax_constraints": ["Explicit transfer syntax only"],
            "directions": ["request"],
        },
    ]
    assert {ref.part for ref in response.refs} == {"PS3.10", "PS3.18"}


def test_lookup_dicomweb_transaction_returns_ps318_transaction_by_name(
    tmp_path: Path,
) -> None:
    response = lookup_dicomweb_transaction(
        _part18_connection(tmp_path),
        name_or_route="RetrieveStudy",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result == {
        "transaction_name": "RetrieveStudy",
        "resource_category": "study",
        "http_method": "GET",
        "route_template": "/studies/{studyInstanceUID}",
        "request_constraints": ["Study Instance UID required"],
        "response_constraints": ["DICOM instances returned"],
        "status_codes": ["200", "400", "404"],
        "media_type_refs": ["application/dicom"],
    }
    assert response.refs[0].part == "PS3.18"
    assert response.refs[0].table == "Synthetic Transactions"
    assert response.refs[0].anchor == "table_18-1"


def test_lookup_dicomweb_transaction_returns_official_shape_retrieve_study(
    tmp_path: Path,
) -> None:
    response = lookup_dicomweb_transaction(
        _part18_official_shape_connection(tmp_path),
        name_or_route="RetrieveStudy",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result == {
        "transaction_name": "RetrieveStudy",
        "resource_category": "study",
        "http_method": "GET",
        "route_template": "/studies/{study}",
        "request_constraints": ["Target resource: Study Instances"],
        "response_constraints": [
            "Success response payload: Instance(s), Metadata, Renderings, "
            "Pixel Data, or Bulk Data",
            "Retrieve one or more representations of DICOM Resources.",
        ],
        "status_codes": [],
        "media_type_refs": ["application/dicom", "application/dicom+json"],
    }
    assert response.refs[0].part == "PS3.18"
    assert response.refs[0].anchor == "table_10.4.1-1"


def test_lookup_dicomweb_transaction_returns_official_shape_store_instances(
    tmp_path: Path,
) -> None:
    response = lookup_dicomweb_transaction(
        _part18_official_shape_connection(tmp_path),
        name_or_route="StoreInstances",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result == {
        "transaction_name": "StoreInstances",
        "resource_category": "study",
        "http_method": "POST",
        "route_template": "/studies/{study}",
        "request_constraints": [
            "Target resource: Study Instances",
            "Request payload: DICOM Instances",
        ],
        "response_constraints": [
            "Success response payload: Store Instances Response Module",
            "Store one or more DICOM Instances.",
        ],
        "status_codes": [],
        "media_type_refs": ["multipart/related", "application/dicom"],
    }
    assert response.refs[0].part == "PS3.18"
    assert response.refs[0].anchor == "table_10.5.1-1"


def test_lookup_dicomweb_transaction_returns_unique_route_template(
    tmp_path: Path,
) -> None:
    connection = _part18_connection(tmp_path)
    connection.execute(
        """
        INSERT INTO dicomweb_transaction (
          id, edition_id, transaction_name, resource_category, http_method,
          route_template, request_constraints_json, response_constraints_json,
          status_codes_json, media_type_refs_json, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026b.PS3.18.dicomweb_transaction.retrieve_study_metadata",
            "2026b",
            "RetrieveStudyMetadata",
            "study",
            "GET",
            "/studies/{studyInstanceUID}/metadata",
            json.dumps(("Study Instance UID required",), separators=(",", ":")),
            json.dumps(("Metadata returned",), separators=(",", ":")),
            json.dumps(("200", "404"), separators=(",", ":")),
            json.dumps(("application/dicom+json",), separators=(",", ":")),
            "2026b.PS3.18.table_18-1",
        ),
    )

    response = lookup_dicomweb_transaction(
        connection,
        name_or_route="/studies/{studyInstanceUID}/metadata",
        edition="2026b",
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["transaction_name"] == "RetrieveStudyMetadata"
    assert response.result["route_template"] == "/studies/{studyInstanceUID}/metadata"


def test_lookup_dicomweb_transaction_returns_candidates_for_ambiguous_route(
    tmp_path: Path,
) -> None:
    response = lookup_dicomweb_transaction(
        _part18_connection(tmp_path),
        name_or_route="/studies/{studyInstanceUID}",
        edition="2026b",
    )

    assert response.status == "validation_error"
    assert response.result is not None
    assert response.result["message"] == (
        "DICOMweb transaction input matched multiple rows."
    )
    assert [
        candidate["transaction_name"] for candidate in response.result["candidates"]
    ] == ["RetrieveStudy", "StoreInstances"]
    methods = {candidate["http_method"] for candidate in response.result["candidates"]}
    assert methods == {"GET", "POST"}
    assert {ref.table for ref in response.refs} == {"Synthetic Transactions"}
    assert {ref.anchor for ref in response.refs} == {"table_18-1"}


def test_lookup_dicomweb_transaction_validates_empty_input_and_reports_not_found(
    tmp_path: Path,
) -> None:
    connection = _part18_connection(tmp_path)

    empty = lookup_dicomweb_transaction(
        connection,
        name_or_route="  ",
        edition="2026b",
    )
    missing = lookup_dicomweb_transaction(
        connection,
        name_or_route="DeleteStudy",
        edition="2026b",
    )

    assert empty.status == "validation_error"
    assert empty.result == {"message": "name_or_route must not be empty."}
    assert missing.status == "not_found"
    assert missing.result == {"message": "No DICOMweb transaction matched the input."}
