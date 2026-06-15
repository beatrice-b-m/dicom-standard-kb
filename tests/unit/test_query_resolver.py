from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from dicom_kb.db.importers import (
    import_attribute_value_terms,
    import_coded_concepts,
    import_context_groups,
    import_dicom_media_types,
    import_dicomweb_transactions,
    import_docbook_structure,
    import_part03,
    import_part04,
    import_part06,
    import_sr_templates,
    import_transfer_syntax_details,
    import_vr_definitions,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import ParsedDocument, parse_docbook_xml
from dicom_kb.ir.models import AttributeUse, Macro, SourceRef
from dicom_kb.parsers.part03_iods import parse_part03
from dicom_kb.parsers.part04_sop_classes import parse_part04
from dicom_kb.parsers.part05_encoding import (
    parse_part05,
    transfer_syntax_details_from_uid_registry,
)
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from dicom_kb.parsers.part10_media_storage import parse_part10
from dicom_kb.parsers.part16_content_mapping import parse_part16
from dicom_kb.parsers.part18_web_services import parse_part18
from dicom_kb.query.resolver import (
    explain_encoding_rule,
    list_attributes_for_module,
    list_modules_for_iod,
    lookup_code_meaning,
    lookup_context_group,
    lookup_data_element,
    lookup_defined_terms,
    lookup_dicomweb_transaction,
    lookup_enumerated_values,
    lookup_iod,
    lookup_media_type,
    lookup_sop_class,
    lookup_sr_template,
    lookup_transfer_syntax,
    lookup_uid,
    lookup_vr,
    resolve_attribute_context,
    retrieve_standard_text,
    search_standard_text,
)
from tests.fixtures_synthetic import (
    PS33_CT_IMAGE_DOCBOOK,
    PS34_SOP_CLASSES_DOCBOOK,
    PS35_ENCODING_DOCBOOK,
    PS36_REGISTRY_DOCBOOK,
    PS37_MESSAGES_DOCBOOK,
    PS38_NETWORK_DOCBOOK,
    PS310_MEDIA_STORAGE_DOCBOOK,
    PS316_CONTENT_MAPPING_DOCBOOK,
    PS316_OFFICIAL_SHAPE_DOCBOOK,
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


def _part034_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = _part03_connection(tmp_path)
    parsed = parse_part04(
        parse_docbook_xml(PS34_SOP_CLASSES_DOCBOOK, part="PS3.4"),
        edition="2026b",
    )
    import_part04(
        connection,
        edition="2026b",
        service_classes=parsed.service_classes,
        sop_classes=parsed.sop_classes,
        sop_class_iods=parsed.sop_class_iods,
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


def _part16_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    document = parse_docbook_xml(PS316_CONTENT_MAPPING_DOCBOOK, part="PS3.16")
    _import_part16_document(connection, document=document)
    return connection


def _part16_official_shape_connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    document = parse_docbook_xml(PS316_OFFICIAL_SHAPE_DOCBOOK, part="PS3.16")
    _import_part16_document(connection, document=document)
    return connection


def _import_part16_document(
    connection: sqlite3.Connection,
    *,
    document: ParsedDocument,
) -> None:
    parsed_part16 = parse_part16(document, edition="2026b")
    import_sr_templates(
        connection,
        edition="2026b",
        templates=parsed_part16.sr_templates,
        rows=parsed_part16.sr_template_rows,
    )
    import_context_groups(
        connection,
        edition="2026b",
        context_groups=parsed_part16.context_groups,
        rows=parsed_part16.context_group_rows,
    )
    import_coded_concepts(
        connection,
        edition="2026b",
        coded_concepts=parsed_part16.coded_concepts,
    )


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
    )
    import_part04(
        connection,
        edition="2026b",
        service_classes=parsed_part04.service_classes,
        sop_classes=parsed_part04.sop_classes,
        sop_class_iods=parsed_part04.sop_class_iods,
    )
    return connection


def _context_connection_with_ambiguous_value_terms(
    tmp_path: Path,
) -> sqlite3.Connection:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3")
    parsed_part03 = parse_part03(document, edition="2026b")
    patient_module = next(
        module
        for module in parsed_part03.modules
        if module.id == "2026b.module.patient"
    )
    duplicate_patient_name = AttributeUse(
        id="2026b.module.patient.attribute_use.duplicate",
        edition_id="2026b",
        owner_type="module",
        owner_id=patient_module.id,
        row_kind="attribute",
        attribute_tag="(0010,0010)",
        attribute_keyword="PatientName",
        attribute_name="Patient's Name",
        type_designation="2",
        description_text="Second applicable context for ambiguity testing.",
        sequence_depth=0,
        row_order=99,
        source_ref=patient_module.source_ref,
    )
    import_part03(
        connection,
        edition="2026b",
        iods=parsed_part03.iods,
        modules=parsed_part03.modules,
        macros=parsed_part03.macros,
        iod_module_uses=parsed_part03.iod_module_uses,
        iod_functional_group_uses=parsed_part03.iod_functional_group_uses,
        attribute_uses=[*parsed_part03.attribute_uses, duplicate_patient_name],
        conditions=parsed_part03.conditions,
    )
    import_attribute_value_terms(
        connection,
        edition="2026b",
        document=document,
    )
    return connection


def _context_connection_with_duplicate_attribute(
    tmp_path: Path,
    *,
    patient_description: str | None = None,
    duplicate_description: str = "Duplicate contextual use.",
) -> sqlite3.Connection:
    connection = _connection(tmp_path)
    parsed_part03 = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"),
        edition="2026b",
    )
    attribute_uses = [
        row.model_copy(update={"description_text": patient_description})
        if row.id == "2026b.module.patient.attribute_use.0"
        and patient_description is not None
        else row
        for row in parsed_part03.attribute_uses
    ]
    duplicate = AttributeUse(
        id="2026b.module.ct_image.attribute_use.0",
        edition_id="2026b",
        owner_type="module",
        owner_id="2026b.module.ct_image",
        row_kind="attribute",
        attribute_tag="(0010,0010)",
        attribute_name="Patient's Name",
        type_designation="1",
        description_text=duplicate_description,
        sequence_depth=0,
        row_order=0,
        source_ref=parsed_part03.modules[2].source_ref,
    )
    import_part03(
        connection,
        edition="2026b",
        iods=parsed_part03.iods,
        modules=parsed_part03.modules,
        macros=parsed_part03.macros,
        iod_module_uses=parsed_part03.iod_module_uses,
        iod_functional_group_uses=parsed_part03.iod_functional_group_uses,
        attribute_uses=[*attribute_uses, duplicate],
        conditions=parsed_part03.conditions,
    )
    return connection


def _part03_connection_with_recursive_macros(
    tmp_path: Path,
    *,
    include_cycle: bool = False,
) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    parsed = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"),
        edition="2026b",
    )
    nested_source_ref = SourceRef(
        id="2026b.ps3_3.table_11_1",
        edition_id="2026b",
        part="PS3.3",
        section="11.1",
        table_id="table_11-1",
        xml_id="table_11-1",
        title="Nested Device Macro Attributes",
    )
    nested_macro = Macro(
        id="2026b.macro.table_11_1",
        edition_id="2026b",
        name="Nested Device Macro",
        table_id="table_11-1",
        section="11.1",
        macro_kind="attribute",
        source_ref=nested_source_ref,
    )
    attribute_uses = [
        row.model_copy(update={"sequence_depth": 1})
        if row.id == "2026b.module.patient.attribute_use.3"
        else row
        for row in parsed.attribute_uses
    ]
    attribute_uses.extend(
        [
            AttributeUse(
                id="2026b.macro.table_10_7.attribute_use.1",
                edition_id="2026b",
                owner_type="macro",
                owner_id="2026b.macro.table_10_7",
                row_kind="include",
                included_macro_id=nested_macro.id,
                include_target_text='Include Table 11-1 "Nested Device Macro"',
                sequence_depth=1,
                row_order=1,
                source_ref=parsed.macros[0].source_ref,
            ),
            AttributeUse(
                id="2026b.macro.table_11_1.attribute_use.0",
                edition_id="2026b",
                owner_type="macro",
                owner_id=nested_macro.id,
                row_kind="attribute",
                attribute_tag="(0018,1000)",
                attribute_keyword="DeviceSerialNumber",
                attribute_name="Device Serial Number",
                type_designation="3",
                description_text="Nested device identifier.",
                sequence_depth=0,
                row_order=0,
                source_ref=nested_source_ref,
            ),
        ]
    )
    if include_cycle:
        attribute_uses.append(
            AttributeUse(
                id="2026b.macro.table_11_1.attribute_use.1",
                edition_id="2026b",
                owner_type="macro",
                owner_id=nested_macro.id,
                row_kind="include",
                included_macro_id="2026b.macro.table_10_7",
                include_target_text=(
                    'Include Table 10-7 "General Anatomy Optional Macro"'
                ),
                sequence_depth=0,
                row_order=1,
                source_ref=nested_source_ref,
            )
        )
    import_part03(
        connection,
        edition="2026b",
        iods=parsed.iods,
        modules=parsed.modules,
        macros=[*parsed.macros, nested_macro],
        iod_module_uses=parsed.iod_module_uses,
        iod_functional_group_uses=parsed.iod_functional_group_uses,
        attribute_uses=attribute_uses,
        conditions=parsed.conditions,
    )
    return connection


def test_lookup_data_element_tag_and_keyword_return_same_entity(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)

    by_tag = lookup_data_element(
        connection,
        tag_or_keyword="(0008,0060)",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )
    by_keyword = lookup_data_element(
        connection,
        tag_or_keyword="modality",
        edition="2026b",
        query_id="query-2",
        resolved_at=RESOLVED_AT,
    )

    assert by_tag.status == "ok"
    assert by_keyword.status == "ok"
    assert by_tag.result == by_keyword.result
    assert by_tag.result == {
        "tag": "(0008,0060)",
        "name": "Modality",
        "keyword": "Modality",
        "vr": "CS",
        "vm": "1",
        "retired": False,
    }
    assert by_tag.refs[0].part == "PS3.6"
    assert by_tag.classification.normativity == "normative"
    assert by_tag.classification.evidence_level == "parsed_registry"
    assert by_tag.classification.machine_decidability == "decidable"
    assert by_tag.parse_confidence.level == "high"
    assert by_tag.parse_confidence.source == "parsed_registry"
    assert by_tag.trace.query_id == "query-1"
    assert by_tag.trace.resolved_at == RESOLVED_AT


def test_lookup_data_element_returns_validation_error_for_malformed_tag(
    tmp_path: Path,
) -> None:
    response = lookup_data_element(
        _connection(tmp_path),
        tag_or_keyword="0008,0060",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "validation_error"
    assert response.classification.normativity == "unsupported"
    assert response.parse_confidence.level == "unknown"
    assert response.result is not None
    assert "malformed DICOM tag" in str(response.result["message"])
    assert response.refs == []


def test_v1_tool_responses_include_classification_metadata(tmp_path: Path) -> None:
    registry_connection = _connection(tmp_path / "registry")
    context_connection = _context_connection(tmp_path / "context")
    document_connection = _doc_connection(tmp_path / "document")

    responses = [
        lookup_data_element(
            registry_connection,
            tag_or_keyword="Modality",
            edition="2026b",
        ),
        lookup_uid(
            registry_connection,
            uid_or_keyword="ExplicitVRLittleEndian",
            edition="2026b",
        ),
        lookup_sop_class(
            context_connection,
            uid_or_name_or_keyword="CT Image Storage",
            edition="2026b",
        ),
        lookup_iod(context_connection, iod_name="CT Image", edition="2026b"),
        list_modules_for_iod(
            context_connection,
            iod_name="CT Image",
            edition="2026b",
        ),
        list_attributes_for_module(
            context_connection,
            module_name="Patient",
            edition="2026b",
        ),
        resolve_attribute_context(
            context_connection,
            attribute="PatientName",
            iod_name="CT Image",
            edition="2026b",
        ),
        retrieve_standard_text(
            document_connection,
            part="PS3.3",
            section_or_anchor="sect_A.3",
            edition="2026b",
        ),
        search_standard_text(
            document_connection,
            query="Patient",
            edition="2026b",
        ),
    ]

    expected = {
        "lookup_data_element": ("normative", "parsed_registry", "decidable"),
        "lookup_uid": ("normative", "parsed_registry", "decidable"),
        "lookup_sop_class": ("normative", "parsed_cross_reference", "decidable"),
        "lookup_iod": ("normative", "parsed_table", "decidable"),
        "list_modules_for_iod": ("normative", "parsed_table", "decidable"),
        "list_attributes_for_module": ("normative", "parsed_table", "decidable"),
        "resolve_attribute_context": (
            "normative",
            "parsed_cross_reference",
            "partially_decidable",
        ),
        "retrieve_standard_text": ("explanatory", "retrieved_text", "not_applicable"),
        "search_standard_text": ("explanatory", "retrieved_text", "not_applicable"),
    }
    for response in responses:
        assert response.status == "ok"
        assert (
            response.classification.normativity,
            response.classification.evidence_level,
            response.classification.machine_decidability,
        ) == expected[response.tool]
        assert response.parse_confidence.level in {"high", "medium", "low"}
        assert (
            response.parse_confidence.source
            == response.classification.evidence_level
        )


def test_lookup_data_element_returns_not_found_for_unknown_tag(tmp_path: Path) -> None:
    response = lookup_data_element(
        _connection(tmp_path),
        tag_or_keyword="(0008,9999)",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "not_found"
    assert response.result == {"message": "No DICOM data element matched the input."}
    assert response.refs == []


def test_lookup_data_element_reports_retired_and_range_matches(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)

    retired = lookup_data_element(
        connection,
        tag_or_keyword="CurveData",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )
    range_match = lookup_data_element(
        connection,
        tag_or_keyword="(6002,3000)",
        edition="2026b",
        query_id="query-2",
        resolved_at=RESOLVED_AT,
    )

    assert retired.status == "ok"
    assert retired.result is not None
    assert retired.result["retired"] is True
    assert range_match.status == "ok"
    assert range_match.result is not None
    assert range_match.result["tag"] == "(60xx,3000)"
    assert range_match.warnings == [
        "concrete tag (6002,3000) matched range row (60xx,3000)"
    ]


def test_lookup_uid_reports_retired_entry(tmp_path: Path) -> None:
    response = lookup_uid(
        _connection(tmp_path),
        uid_or_keyword="ExplicitVRBigEndian",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
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
        query_id="query-1",
        resolved_at=RESOLVED_AT,
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
    assert response.classification.evidence_level == "parsed_table"
    assert response.trace.query_id == "query-1"


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
        query_id="query-1",
        resolved_at=RESOLVED_AT,
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
    assert response.classification.evidence_level == "parsed_cross_reference"
    assert response.trace.query_id == "query-1"


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
        query_id="query-1",
        resolved_at=RESOLVED_AT,
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
    assert response.classification.evidence_level == "retrieved_text"


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
        query_id="query-1",
        resolved_at=RESOLVED_AT,
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
    assert response.classification.evidence_level == "parsed_table"
    assert response.trace.query_id == "query-1"


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
    assert response.classification.evidence_level == "retrieved_text"
    assert response.classification.machine_decidability == "not_applicable"
    assert response.parse_confidence.level == "low"
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
    assert response.classification.evidence_level == "parsed_table"


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
    assert response.classification.evidence_level == "parsed_table"


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
    methods = {
        candidate["http_method"] for candidate in response.result["candidates"]
    }
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
    assert missing.result == {
        "message": "No DICOMweb transaction matched the input."
    }


def test_lookup_context_group_returns_ps316_rows_and_include_rows(
    tmp_path: Path,
) -> None:
    response = lookup_context_group(
        _part16_connection(tmp_path),
        cid_or_name="29",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result == {
        "cid": "CID 29",
        "name": "Acquisition Modality",
        "extensibility": "EXTENSIBLE",
        "version": "20260101",
        "rows": [
            {
                "order": 1,
                "coding_scheme_designator": "DCM",
                "coding_scheme_version": None,
                "code_value": "CT",
                "code_meaning": "Computed Tomography",
                "include_cid": None,
            },
            {
                "order": 2,
                "coding_scheme_designator": None,
                "coding_scheme_version": None,
                "code_value": None,
                "code_meaning": None,
                "include_cid": "CID 30",
            },
        ],
    }
    assert response.refs[0].part == "PS3.16"
    assert response.refs[0].table == "Synthetic Context Group Rows"
    assert response.classification.evidence_level == "parsed_table"
    assert response.trace.query_id == "query-1"


def test_lookup_context_group_returns_candidates_for_ambiguous_name(
    tmp_path: Path,
) -> None:
    connection = _part16_connection(tmp_path)
    connection.execute(
        """
        INSERT INTO context_group (
          id, edition_id, cid, name, extensibility, version, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026b.PS3.16.context_group.cid_30",
            "2026b",
            "CID 30",
            "Acquisition Modality",
            "BASELINE",
            "20260101",
            "2026b.PS3.16.table_16-3",
        ),
    )

    response = lookup_context_group(
        connection,
        cid_or_name="Acquisition Modality",
        edition="2026b",
    )

    assert response.status == "validation_error"
    assert response.result is not None
    assert response.result["message"] == "Context group input matched multiple rows."
    assert [
        candidate["cid"] for candidate in response.result["candidates"]
    ] == ["CID 29", "CID 30"]
    assert response.result["candidates"][0]["rows"][1]["include_cid"] == "CID 30"
    assert response.result["candidates"][1]["rows"] == []
    assert {ref.part for ref in response.refs} == {"PS3.16"}


def test_lookup_context_group_validates_input_and_reports_not_found(
    tmp_path: Path,
) -> None:
    connection = _part16_connection(tmp_path)

    empty = lookup_context_group(connection, cid_or_name="  ", edition="2026b")
    missing = lookup_context_group(
        connection,
        cid_or_name="CID 9999",
        edition="2026b",
    )

    assert empty.status == "validation_error"
    assert empty.result == {"message": "cid_or_name must not be empty."}
    assert missing.status == "not_found"
    assert missing.result == {"message": "No PS3.16 context group matched the input."}


def test_lookup_sr_template_returns_ps316_rows_and_include_rows(
    tmp_path: Path,
) -> None:
    response = lookup_sr_template(
        _part16_connection(tmp_path),
        tid_or_name="1500",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result == {
        "tid": "TID 1500",
        "name": "Measurement Report",
        "extensibility": "EXTENSIBLE",
        "rows": [
            {
                "order": 1,
                "relationship_type": "CONTAINS",
                "value_type": "CONTAINER",
                "concept_name": "Measurement Report",
                "cardinality": "1",
                "condition": "Root container is required.",
                "include_tid": None,
            },
            {
                "order": 2,
                "relationship_type": "CONTAINS",
                "value_type": "INCLUDE",
                "concept_name": None,
                "cardinality": "1-n",
                "condition": "Include measurements when present.",
                "include_tid": "TID 1501",
            },
        ],
    }
    assert response.refs[0].part == "PS3.16"
    assert response.refs[0].table == "Synthetic Template Rows"
    assert response.classification.evidence_level == "parsed_table"
    assert response.trace.query_id == "query-1"


def test_lookup_sr_template_returns_candidates_for_ambiguous_name(
    tmp_path: Path,
) -> None:
    connection = _part16_connection(tmp_path)
    connection.execute(
        """
        INSERT INTO sr_template (
          id, edition_id, tid, name, extensibility, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "2026b.PS3.16.sr_template.tid_1501",
            "2026b",
            "TID 1501",
            "Measurement Report",
            "NON-EXTENSIBLE",
            "2026b.PS3.16.table_16-1",
        ),
    )

    response = lookup_sr_template(
        connection,
        tid_or_name="Measurement Report",
        edition="2026b",
    )

    assert response.status == "validation_error"
    assert response.result is not None
    assert response.result["message"] == "SR template input matched multiple rows."
    assert [
        candidate["tid"] for candidate in response.result["candidates"]
    ] == ["TID 1500", "TID 1501"]
    assert response.result["candidates"][0]["rows"][1]["include_tid"] == "TID 1501"
    assert response.result["candidates"][1]["rows"] == []
    assert {ref.part for ref in response.refs} == {"PS3.16"}


def test_lookup_sr_template_validates_input_and_reports_not_found(
    tmp_path: Path,
) -> None:
    connection = _part16_connection(tmp_path)

    empty = lookup_sr_template(connection, tid_or_name="  ", edition="2026b")
    missing = lookup_sr_template(
        connection,
        tid_or_name="TID 9999",
        edition="2026b",
    )

    assert empty.status == "validation_error"
    assert empty.result == {"message": "tid_or_name must not be empty."}
    assert missing.status == "not_found"
    assert missing.result == {"message": "No PS3.16 SR template matched the input."}


def test_lookup_code_meaning_returns_ps316_coded_concept(tmp_path: Path) -> None:
    response = lookup_code_meaning(
        _part16_connection(tmp_path),
        code_value="CT",
        scheme="DCM",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result == {
        "code_value": "CT",
        "coding_scheme_designator": "DCM",
        "coding_scheme_version": None,
        "code_meaning": "Computed Tomography",
        "context_groups": ["CID 29"],
    }
    assert response.refs[0].part == "PS3.16"
    assert response.refs[0].table == "Synthetic Context Group Rows"
    assert response.classification.evidence_level == "parsed_table"
    assert response.trace.query_id == "query-1"


def test_part16_resolvers_return_official_shape_fixture_rows(
    tmp_path: Path,
) -> None:
    connection = _part16_official_shape_connection(tmp_path)

    template = lookup_sr_template(
        connection,
        tid_or_name="1500",
        edition="2026b",
    )
    context_group = lookup_context_group(
        connection,
        cid_or_name="29",
        edition="2026b",
    )
    code = lookup_code_meaning(
        connection,
        code_value="CT",
        scheme="DCM",
        edition="2026b",
    )

    assert template.status == "ok"
    assert template.result == {
        "tid": "TID 1500",
        "name": "Measurement Report",
        "extensibility": "Extensible",
        "rows": [
            {
                "order": 1,
                "relationship_type": None,
                "value_type": "CONTAINER",
                "concept_name": "D",
                "cardinality": "1",
                "condition": None,
                "include_tid": None,
            },
            {
                "order": 2,
                "relationship_type": "> HAS OBS CONTEXT",
                "value_type": "INCLUDE",
                "concept_name": "D",
                "cardinality": "1",
                "condition": None,
                "include_tid": "TID 1001",
            },
            {
                "order": 3,
                "relationship_type": "> CONTAINS",
                "value_type": "INCLUDE",
                "concept_name": "D",
                "cardinality": "1-n",
                "condition": None,
                "include_tid": "TID 1501",
            },
        ],
    }
    assert template.refs[0].part == "PS3.16"
    assert template.refs[0].table == "Measurement Report"

    assert context_group.status == "ok"
    assert context_group.result == {
        "cid": "CID 29",
        "name": "Acquisition Modality",
        "extensibility": "Extensible",
        "version": "20231115",
        "rows": [
            {
                "order": 1,
                "coding_scheme_designator": "DCM",
                "coding_scheme_version": None,
                "code_value": "CT",
                "code_meaning": "Computed Tomography",
                "include_cid": None,
            },
            {
                "order": 2,
                "coding_scheme_designator": None,
                "coding_scheme_version": None,
                "code_value": None,
                "code_meaning": None,
                "include_cid": "CID 34",
            },
        ],
    }
    assert context_group.refs[0].part == "PS3.16"
    assert context_group.refs[0].table == "Acquisition Modality"

    assert code.status == "ok"
    assert code.result == {
        "code_value": "CT",
        "coding_scheme_designator": "DCM",
        "coding_scheme_version": None,
        "code_meaning": "Computed Tomography",
        "context_groups": ["CID 29"],
    }
    assert code.refs[0].part == "PS3.16"
    assert code.refs[0].table == "Acquisition Modality"


def test_lookup_code_meaning_returns_candidates_for_ambiguous_code_value(
    tmp_path: Path,
) -> None:
    connection = _part16_connection(tmp_path)
    connection.execute(
        """
        INSERT INTO coded_concept (
          id, edition_id, code_value, coding_scheme_designator,
          coding_scheme_version, code_meaning, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026b.PS3.16.coded_concept.sct.ct",
            "2026b",
            "CT",
            "SCT",
            "",
            "Computed tomography procedure",
            "2026b.PS3.16.table_16-3",
        ),
    )

    response = lookup_code_meaning(
        connection,
        code_value="CT",
        edition="2026b",
    )

    assert response.status == "validation_error"
    assert response.result is not None
    assert response.result["message"] == (
        "Code value input matched multiple coded concepts."
    )
    assert response.result["candidates"] == [
        {
            "code_value": "CT",
            "coding_scheme_designator": "DCM",
            "coding_scheme_version": None,
            "code_meaning": "Computed Tomography",
            "context_groups": ["CID 29"],
        },
        {
            "code_value": "CT",
            "coding_scheme_designator": "SCT",
            "coding_scheme_version": None,
            "code_meaning": "Computed tomography procedure",
            "context_groups": [],
        },
    ]
    assert {ref.part for ref in response.refs} == {"PS3.16"}


def test_lookup_code_meaning_validates_input_and_reports_not_found(
    tmp_path: Path,
) -> None:
    connection = _part16_connection(tmp_path)

    empty_code = lookup_code_meaning(connection, code_value="  ", edition="2026b")
    empty_scheme = lookup_code_meaning(
        connection,
        code_value="CT",
        scheme=" ",
        edition="2026b",
    )
    missing = lookup_code_meaning(
        connection,
        code_value="MR",
        scheme="DCM",
        edition="2026b",
    )

    assert empty_code.status == "validation_error"
    assert empty_code.result == {"message": "code_value must not be empty."}
    assert empty_scheme.status == "validation_error"
    assert empty_scheme.result == {"message": "scheme must not be empty when provided."}
    assert missing.status == "not_found"
    assert missing.result == {"message": "No PS3.16 coded concept matched the input."}


def test_retrieve_standard_text_returns_capped_excerpt_and_tables(
    tmp_path: Path,
) -> None:
    response = retrieve_standard_text(
        _doc_connection(tmp_path),
        part="PS3.3",
        section_or_anchor="sect_A.3",
        edition="2026b",
        max_chars=80,
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["part"] == "PS3.3"
    assert response.result["section"] == "sect_A.3"
    assert response.result["title"] == "CT Image IOD"
    assert len(str(response.result["text_excerpt"])) == 80
    assert response.result["tables"] == [
        {"table_id": "table_A.3-1", "title": "CT Image IOD Modules"}
    ]
    assert response.warnings == ["text excerpt truncated to 80 characters"]
    assert [ref.part for ref in response.refs] == ["PS3.3", "PS3.3"]
    assert response.refs[1].table == "CT Image IOD Modules"
    assert response.trace.query_id == "query-1"


def test_retrieve_standard_text_returns_cited_ps37_service_behavior_fallback(
    tmp_path: Path,
) -> None:
    response = retrieve_standard_text(
        _part07_doc_connection(tmp_path),
        part="PS3.7",
        section_or_anchor="sect_7.1",
        edition="2026b",
        max_chars=240,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["part"] == "PS3.7"
    assert response.result["title"] == "DIMSE Services Overview"
    assert "C-ECHO service behavior that verifi" in str(
        response.result["text_excerpt"]
    )
    assert response.result["tables"] == [
        {"table_id": "table_7-1", "title": "Synthetic Message Services"},
        {"table_id": "table_7-2", "title": "Synthetic Message Notes"},
    ]
    assert [(ref.part, ref.anchor) for ref in response.refs] == [
        ("PS3.7", "sect_7.1"),
        ("PS3.7", "table_7-1"),
        ("PS3.7", "table_7-2"),
    ]


def test_retrieve_standard_text_returns_cited_ps38_network_fallback(
    tmp_path: Path,
) -> None:
    response = retrieve_standard_text(
        _part08_doc_connection(tmp_path),
        part="PS3.8",
        section_or_anchor="sect_9.3",
        edition="2026b",
        max_chars=280,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["part"] == "PS3.8"
    assert response.result["title"] == "PDU Fields Overview"
    assert "A-ASSOCIATE-RQ PDU starts association establishment" in str(
        response.result["text_excerpt"]
    )
    assert response.result["tables"] == [
        {"table_id": "table_8-1", "title": "ASSOCIATE-RQ PDU Fields"},
        {"table_id": "table_8-2", "title": "Synthetic Network Notes"},
    ]
    assert [(ref.part, ref.anchor) for ref in response.refs] == [
        ("PS3.8", "sect_9.3"),
        ("PS3.8", "table_8-1"),
        ("PS3.8", "table_8-2"),
    ]


def test_retrieve_standard_text_validates_inputs(tmp_path: Path) -> None:
    connection = _doc_connection(tmp_path)
    response = retrieve_standard_text(
        connection,
        part="3.3",
        section_or_anchor="sect_A.3",
        edition="2026b",
        max_chars=80,
    )

    assert response.status == "validation_error"
    assert response.result is not None
    assert "part must be" in str(response.result["message"])

    response = retrieve_standard_text(
        connection,
        part="PS3.3",
        section_or_anchor="sect_A.3",
        edition="2026b",
        max_chars=0,
    )

    assert response.status == "validation_error"
    assert response.result is not None
    assert "max_chars" in str(response.result["message"])


def test_retrieve_standard_text_reports_not_found(tmp_path: Path) -> None:
    response = retrieve_standard_text(
        _doc_connection(tmp_path),
        part="PS3.3",
        section_or_anchor="missing",
        edition="2026b",
        max_chars=80,
    )

    assert response.status == "not_found"
    assert response.result == {"message": "No standard text node matched the input."}
    assert response.refs == []


def test_search_standard_text_returns_cited_matches(tmp_path: Path) -> None:
    response = search_standard_text(
        _doc_connection(tmp_path),
        query="Patient name",
        edition="2026b",
        part_filter="PS3.3",
        limit=5,
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    matches = response.result["matches"]
    assert matches[0]["part"] == "PS3.3"
    assert matches[0]["title"] in {"Patient Module", "Patient Module Attributes"}
    assert "Patient" in matches[0]["snippet"]
    assert {ref.part for ref in response.refs} == {"PS3.3"}
    assert response.input == {
        "query": "Patient name",
        "limit": "5",
        "part_filter": "PS3.3",
    }
    assert response.trace.query_id == "query-1"


def test_search_standard_text_validates_inputs(tmp_path: Path) -> None:
    connection = _doc_connection(tmp_path)

    response = search_standard_text(
        connection,
        query="   ",
        edition="2026b",
    )
    assert response.status == "validation_error"
    assert response.result is not None
    assert "query must not be empty" in str(response.result["message"])

    response = search_standard_text(
        connection,
        query="Patient",
        edition="2026b",
        part_filter="3.3",
    )
    assert response.status == "validation_error"
    assert response.result is not None
    assert "part_filter" in str(response.result["message"])

    response = search_standard_text(
        connection,
        query="Patient",
        edition="2026b",
        limit=0,
    )
    assert response.status == "validation_error"
    assert response.result is not None
    assert "limit" in str(response.result["message"])


def test_search_standard_text_reports_not_found(tmp_path: Path) -> None:
    response = search_standard_text(
        _doc_connection(tmp_path),
        query="ultrasound elastography",
        edition="2026b",
    )

    assert response.status == "not_found"
    assert response.result == {"message": "No standard text matched the query."}
    assert response.refs == []


def test_lookup_iod_returns_ps33_iod(tmp_path: Path) -> None:
    response = lookup_iod(
        _part03_connection(tmp_path),
        iod_name="ct_image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result == {
        "id": "2026b.iod.ct_image",
        "name": "CT Image",
        "keyword": "ct_image",
        "iod_type": "composite",
        "part": "PS3.3",
        "section": "table_A.3-1",
    }
    assert response.refs[0].part == "PS3.3"


def test_lookup_sop_class_returns_linked_iod(tmp_path: Path) -> None:
    response = lookup_sop_class(
        _part034_connection(tmp_path),
        uid_or_name_or_keyword="1.2.840.10008.5.1.4.1.1.2",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["sop_class"] == {
        "id": "2026b.sop_class.1.2.840.10008.5.1.4.1.1.2",
        "name": "CT Image Storage",
        "uid_value": "1.2.840.10008.5.1.4.1.1.2",
    }
    assert response.result["service_class"]["name"] == "Storage Service Class"
    assert response.result["iods"] == [
        {
            "iod_id": "2026b.iod.ct_image",
            "iod_name": "CT Image",
            "iod_keyword": "ct_image",
            "resolution": "parsed",
            "resolution_warning": None,
        }
    ]
    assert {ref.part for ref in response.refs} == {"PS3.3", "PS3.4"}


def test_lookup_sop_class_by_name_and_malformed_uid_paths(tmp_path: Path) -> None:
    connection = _part034_connection(tmp_path)
    by_name = lookup_sop_class(
        connection,
        uid_or_name_or_keyword="enhanced ct image storage",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )
    malformed = lookup_sop_class(
        connection,
        uid_or_name_or_keyword="1.2.bad",
        edition="2026b",
        query_id="query-2",
        resolved_at=RESOLVED_AT,
    )

    assert by_name.status == "ok"
    assert by_name.result is not None
    assert by_name.result["iods"][0]["iod_name"] == "Enhanced CT Image"
    assert malformed.status == "validation_error"
    assert malformed.result is not None
    assert "malformed DICOM UID" in malformed.result["message"]


def test_resolve_attribute_context_for_iod_returns_effective_type(
    tmp_path: Path,
) -> None:
    response = resolve_attribute_context(
        _context_connection(tmp_path),
        attribute="PatientName",
        iod_name="CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["attribute"] == {
        "tag": "(0010,0010)",
        "name": "Patient's Name",
        "keyword": "PatientName",
        "vr": "PN",
        "vm": "1",
        "retired": False,
    }
    assert response.result["uses"] == [
        {
            "iod": "CT Image",
            "module": "Patient",
            "information_entity": "Patient",
            "module_usage": "M",
            "module_usage_condition_text": None,
            "attribute_use_id": "2026b.module.patient.attribute_use.0",
            "type_designation": "2",
            "sequence_path": [],
            "via_macro": None,
            "condition": None,
        }
    ]
    assert response.result["effective_type"] == "2"
    assert response.result["effective_type_explanation"] == (
        "Single applicable use in resolved context."
    )
    assert {ref.part for ref in response.refs} == {"PS3.3", "PS3.6"}


def test_resolve_attribute_context_for_sop_class_preserves_sequence_path(
    tmp_path: Path,
) -> None:
    response = resolve_attribute_context(
        _context_connection(tmp_path),
        attribute="ReferencedSOPClassUID",
        sop_class="CT Image Storage",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    use = response.result["uses"][0]
    assert use["iod"] == "CT Image"
    assert use["module"] == "Patient"
    assert use["type_designation"] == "1"
    assert use["sequence_path"] == ["Referenced Patient Sequence"]
    assert response.result["effective_type"] == "1"
    assert {ref.part for ref in response.refs} == {"PS3.3", "PS3.4", "PS3.6"}


def test_resolve_attribute_context_reports_macro_path(tmp_path: Path) -> None:
    response = resolve_attribute_context(
        _context_connection(tmp_path),
        attribute="AnatomicRegionSequence",
        iod_name="CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["uses"][0]["via_macro"] == ["General Anatomy Optional Macro"]
    assert response.result["effective_type"] == "3"


def test_resolve_attribute_context_traverses_functional_group_macros(
    tmp_path: Path,
) -> None:
    response = resolve_attribute_context(
        _context_connection(tmp_path),
        attribute="AnatomicRegionSequence",
        iod_name="Enhanced CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["uses"] == [
        {
            "iod": "Enhanced CT Image",
            "module": None,
            "functional_group_macro": "General Anatomy Optional Macro",
            "information_entity": None,
            "module_usage": "C",
            "module_usage_condition_text": "Required if anatomy is known",
            "attribute_use_id": "2026b.macro.table_10_7.attribute_use.0",
            "type_designation": "3",
            "sequence_path": [],
            "via_macro": ["General Anatomy Optional Macro"],
            "condition": None,
        }
    ]
    assert response.result["effective_type"] == "3"


def test_lookup_defined_terms_returns_attribute_value_terms(tmp_path: Path) -> None:
    response = lookup_defined_terms(
        _context_connection(tmp_path),
        attribute="PatientName",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["attribute"]["tag"] == "(0010,0010)"
    assert response.result["terms"] == [
        {
            "value": "ALPHA",
            "meaning": "Alphabetic representation.",
            "term_kind": "defined_term",
            "context_label": "Patient Module - Defined Terms:",
            "attribute_use_id": "2026b.module.patient.attribute_use.0",
        },
        {
            "value": "IDEOGRAPHIC",
            "meaning": "Ideographic representation.",
            "term_kind": "defined_term",
            "context_label": "Patient Module - Defined Terms:",
            "attribute_use_id": "2026b.module.patient.attribute_use.0",
        },
    ]
    assert {ref.part for ref in response.refs} == {"PS3.3", "PS3.6"}


def test_lookup_value_terms_supports_context_and_missing_term_kind(
    tmp_path: Path,
) -> None:
    connection = _context_connection(tmp_path)
    matched_context = lookup_defined_terms(
        connection,
        attribute="PatientName",
        edition="2026b",
        context="Patient",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )
    missing_context = lookup_defined_terms(
        connection,
        attribute="PatientName",
        edition="2026b",
        context="Missing Context",
        query_id="query-2",
        resolved_at=RESOLVED_AT,
    )
    missing_kind = lookup_enumerated_values(
        connection,
        attribute="PatientName",
        edition="2026b",
        query_id="query-3",
        resolved_at=RESOLVED_AT,
    )

    assert matched_context.status == "ok"
    assert matched_context.result is not None
    assert len(matched_context.result["terms"]) == 2
    assert missing_context.status == "not_found"
    assert missing_kind.status == "not_found"


def test_lookup_value_terms_resolves_iod_and_sop_contexts(
    tmp_path: Path,
) -> None:
    connection = _context_connection(tmp_path)
    iod_context = lookup_defined_terms(
        connection,
        attribute="PatientName",
        edition="2026b",
        context="CT Image",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )
    sop_context = lookup_defined_terms(
        connection,
        attribute="PatientName",
        edition="2026b",
        context="CT Image Storage",
        query_id="query-2",
        resolved_at=RESOLVED_AT,
    )
    mismatched_sop_context = lookup_defined_terms(
        connection,
        attribute="PatientName",
        edition="2026b",
        context="Enhanced CT Image Storage",
        query_id="query-3",
        resolved_at=RESOLVED_AT,
    )

    assert iod_context.status == "ok"
    assert iod_context.result is not None
    assert [term["value"] for term in iod_context.result["terms"]] == [
        "ALPHA",
        "IDEOGRAPHIC",
    ]
    assert {ref.part for ref in iod_context.refs} == {"PS3.3", "PS3.6"}

    assert sop_context.status == "ok"
    assert sop_context.result is not None
    assert [term["attribute_use_id"] for term in sop_context.result["terms"]] == [
        "2026b.module.patient.attribute_use.0",
        "2026b.module.patient.attribute_use.0",
    ]
    assert {ref.part for ref in sop_context.refs} == {"PS3.3", "PS3.4", "PS3.6"}

    assert mismatched_sop_context.status == "not_found"
    assert mismatched_sop_context.refs is not None
    assert {ref.part for ref in mismatched_sop_context.refs} == {
        "PS3.3",
        "PS3.4",
        "PS3.6",
    }


def test_lookup_value_terms_returns_candidates_for_ambiguous_context(
    tmp_path: Path,
) -> None:
    response = lookup_defined_terms(
        _context_connection_with_ambiguous_value_terms(tmp_path),
        attribute="PatientName",
        edition="2026b",
        context="CT Image",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "validation_error"
    assert response.result is not None
    assert response.result["message"] == (
        "Context input matched multiple value-term contexts."
    )
    assert response.result["attribute"]["tag"] == "(0010,0010)"
    assert response.result["candidates"] == [
        {
            "context_label": "Patient Module - Defined Terms:",
            "attribute_use_id": "2026b.module.patient.attribute_use.0",
            "terms": [
                {
                    "value": "ALPHA",
                    "meaning": "Alphabetic representation.",
                    "term_kind": "defined_term",
                },
                {
                    "value": "IDEOGRAPHIC",
                    "meaning": "Ideographic representation.",
                    "term_kind": "defined_term",
                },
            ],
        },
        {
            "context_label": "Patient Module - Defined Terms:",
            "attribute_use_id": "2026b.module.patient.attribute_use.duplicate",
            "terms": [
                {
                    "value": "ALPHA",
                    "meaning": "Alphabetic representation.",
                    "term_kind": "defined_term",
                },
                {
                    "value": "IDEOGRAPHIC",
                    "meaning": "Ideographic representation.",
                    "term_kind": "defined_term",
                },
            ],
        },
    ]
    assert {ref.part for ref in response.refs} == {"PS3.3", "PS3.6"}


def test_resolve_attribute_context_computes_lowest_type_for_multiple_uses(
    tmp_path: Path,
) -> None:
    response = resolve_attribute_context(
        _context_connection_with_duplicate_attribute(tmp_path),
        attribute="Patient's Name",
        iod_name="CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert [use["type_designation"] for use in response.result["uses"]] == ["2", "1"]
    assert response.result["effective_type"] == "1"
    assert response.result["effective_type_explanation"].startswith(
        "Multiple applicable uses"
    )
    assert response.warnings == []


def test_resolve_attribute_context_uses_explicit_type_override(
    tmp_path: Path,
) -> None:
    response = resolve_attribute_context(
        _context_connection_with_duplicate_attribute(
            tmp_path,
            duplicate_description=(
                "For this context, Patient's Name shall be Type 3 in this module."
            ),
        ),
        attribute="Patient's Name",
        iod_name="CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["effective_type"] == "3"
    assert response.result["effective_type_explanation"].startswith(
        "Explicit type override language selected Type 3"
    )
    assert response.warnings == []


def test_resolve_attribute_context_withholds_conflicting_overrides(
    tmp_path: Path,
) -> None:
    response = resolve_attribute_context(
        _context_connection_with_duplicate_attribute(
            tmp_path,
            patient_description=(
                "For this context, Patient's Name shall be Type 2 in this module."
            ),
            duplicate_description=(
                "For this context, Patient's Name shall be Type 1 in this module."
            ),
        ),
        attribute="Patient's Name",
        iod_name="CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["effective_type"] is None
    assert response.classification.machine_decidability == "partially_decidable"
    assert response.warnings is not None
    assert response.warnings[0].startswith("conflicting explicit type overrides found")


def test_resolve_attribute_context_withholds_ambiguous_override_text(
    tmp_path: Path,
) -> None:
    response = resolve_attribute_context(
        _context_connection_with_duplicate_attribute(
            tmp_path,
            duplicate_description=(
                "Patient's Name may be Type 1 or Type 2 depending on context."
            ),
        ),
        attribute="Patient's Name",
        iod_name="CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["effective_type"] is None
    assert response.classification.machine_decidability == "partially_decidable"
    assert response.warnings == [
        "ambiguous type override language found in source refs: "
        "2026b.PS3.3.table_A.3-1"
    ]


def test_resolve_attribute_context_reports_missing_and_invalid_inputs(
    tmp_path: Path,
) -> None:
    connection = _context_connection(tmp_path)
    missing_attribute = resolve_attribute_context(
        connection,
        attribute="MissingAttribute",
        iod_name="CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )
    missing_context = resolve_attribute_context(
        connection,
        attribute="PatientName",
        iod_name="Missing IOD",
        edition="2026b",
        query_id="query-2",
        resolved_at=RESOLVED_AT,
    )
    invalid_context_choice = resolve_attribute_context(
        connection,
        attribute="PatientName",
        edition="2026b",
        query_id="query-3",
        resolved_at=RESOLVED_AT,
    )

    assert missing_attribute.status == "not_found"
    assert missing_attribute.result == {
        "message": "No DICOM data element matched the attribute input."
    }
    assert missing_context.status == "not_found"
    assert missing_context.result == {
        "message": "No DICOM IOD matched the context input."
    }
    assert invalid_context_choice.status == "validation_error"
    assert invalid_context_choice.result == {
        "message": "Provide exactly one context: iod_name or sop_class."
    }


def test_list_modules_for_iod_returns_ordered_ps33_modules(tmp_path: Path) -> None:
    response = list_modules_for_iod(
        _part03_connection(tmp_path),
        iod_name="CT Image",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["iod"]["name"] == "CT Image"
    assert response.result["modules"] == [
        {
            "module_id": "2026b.module.patient",
            "module_name": "Patient",
            "section": "table_C.7-1",
            "information_entity": "Patient",
            "usage": "M",
            "usage_condition_text": None,
            "condition": None,
        },
        {
            "module_id": "2026b.module.contrast_bolus",
            "module_name": "Contrast/Bolus",
            "section": "C.7.6.4",
            "information_entity": "Image",
            "usage": "C",
            "usage_condition_text": "Required if contrast media was used",
            "condition": {
                "condition_id": "2026b.iod.ct_image.module_use.1.condition",
                "source_text": "Required if contrast media was used",
                "condition_kind": "required_if",
                "machine_status": "raw_text",
                "dependencies": [],
                "evaluator": {"available": False},
                "refs": [
                    {
                        "part": "PS3.3",
                        "section": "sect_A.3",
                        "table": "CT Image IOD Modules",
                        "anchor": "table_A.3-1",
                        "official_url": (
                            "https://dicom.nema.org/medical/dicom/2026b/"
                            "output/chtml/part03/table_A.3-1.html"
                        ),
                        "edition": "2026b",
                    }
                ],
            },
        },
        {
            "module_id": "2026b.module.ct_image",
            "module_name": "CT Image",
            "section": "C.8.2.1",
            "information_entity": "Image",
            "usage": "M",
            "usage_condition_text": None,
            "condition": None,
        },
    ]
    assert {ref.part for ref in response.refs} == {"PS3.3"}


def test_list_modules_for_iod_returns_not_found(tmp_path: Path) -> None:
    response = list_modules_for_iod(
        _part03_connection(tmp_path),
        iod_name="Missing IOD",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "not_found"
    assert response.result == {"message": "No DICOM IOD matched the input."}
    assert response.refs == []


def test_list_attributes_for_module_preserves_include_rows(tmp_path: Path) -> None:
    response = list_attributes_for_module(
        _part03_connection(tmp_path),
        module_name="Patient",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    assert response.result["module"]["name"] == "Patient"
    attributes = response.result["attributes"]
    assert [row["row_kind"] for row in attributes] == [
        "attribute",
        "attribute",
        "attribute",
        "include",
    ]
    assert attributes[0]["attribute_tag"] == "(0010,0010)"
    assert attributes[2]["parent_attribute_use_id"] == (
        "2026b.module.patient.attribute_use.1"
    )
    assert attributes[3]["included_macro_name"] == "General Anatomy Optional Macro"


def test_list_attributes_for_module_exposes_attribute_conditions(
    tmp_path: Path,
) -> None:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    xml = PS33_CT_IMAGE_DOCBOOK.replace(
        "<entry>2</entry><entry>Patient name.</entry>",
        "<entry>1C</entry><entry>Required if patient identity is known.</entry>",
    )
    parsed = parse_part03(
        parse_docbook_xml(xml, part="PS3.3"),
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

    response = list_attributes_for_module(
        connection,
        module_name="Patient",
        edition="2026b",
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    patient_name = response.result["attributes"][0]
    assert patient_name["type_designation"] == "1C"
    assert patient_name["condition"] == {
        "condition_id": "2026b.module.patient.attribute_use.0.condition",
        "source_text": "Required if patient identity is known.",
        "condition_kind": "required_if",
        "machine_status": "raw_text",
        "dependencies": [],
        "evaluator": {"available": False},
        "refs": [
            {
                "part": "PS3.3",
                "section": "sect_C.7.1.1",
                "table": "Patient Module Attributes",
                "anchor": "table_C.7-1",
                "official_url": (
                    "https://dicom.nema.org/medical/dicom/2026b/output/chtml/"
                    "part03/table_C.7-1.html"
                ),
                "edition": "2026b",
            }
        ],
    }


def test_list_attributes_for_module_expands_macros_after_include(
    tmp_path: Path,
) -> None:
    response = list_attributes_for_module(
        _part03_connection(tmp_path),
        module_name="Patient",
        edition="2026b",
        expand_macros=True,
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.result is not None
    attributes = response.result["attributes"]
    assert [
        row["attribute_name"] for row in attributes if row["row_kind"] == "attribute"
    ] == [
        "Patient's Name",
        "Referenced Patient Sequence",
        "Referenced SOP Class UID",
        "Anatomic Region Sequence",
    ]
    expanded = attributes[-1]
    assert expanded["owner_type"] == "macro"
    assert expanded["owner_name"] == "General Anatomy Optional Macro"
    assert expanded["expanded_from_include_id"] == (
        "2026b.module.patient.attribute_use.3"
    )
    assert {ref.table for ref in response.refs} >= {
        "Patient Module Attributes",
        "General Anatomy Optional Macro Attributes",
    }


def test_list_attributes_for_module_expands_nested_macros_with_effective_depth(
    tmp_path: Path,
) -> None:
    response = list_attributes_for_module(
        _part03_connection_with_recursive_macros(tmp_path),
        module_name="Patient",
        edition="2026b",
        expand_macros=True,
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.warnings == []
    assert response.result is not None
    attributes = response.result["attributes"]
    anatomic = next(
        row
        for row in attributes
        if row.get("attribute_name") == "Anatomic Region Sequence"
    )
    nested_include = next(
        row
        for row in attributes
        if row["id"] == "2026b.macro.table_10_7.attribute_use.1"
    )
    device = next(
        row for row in attributes if row.get("attribute_name") == "Device Serial Number"
    )

    assert anatomic["sequence_depth"] == 1
    assert anatomic["expanded_from_include_id"] == (
        "2026b.module.patient.attribute_use.3"
    )
    assert nested_include["sequence_depth"] == 2
    assert nested_include["included_macro_name"] == "Nested Device Macro"
    assert nested_include["expanded_from_include_id"] == (
        "2026b.module.patient.attribute_use.3"
    )
    assert device["sequence_depth"] == 2
    assert device["owner_name"] == "Nested Device Macro"
    assert device["expanded_from_include_id"] == (
        "2026b.macro.table_10_7.attribute_use.1"
    )
    assert {ref.table for ref in response.refs} >= {
        "General Anatomy Optional Macro Attributes",
        "Nested Device Macro Attributes",
    }


def test_list_attributes_for_module_reports_macro_include_cycles(
    tmp_path: Path,
) -> None:
    response = list_attributes_for_module(
        _part03_connection_with_recursive_macros(tmp_path, include_cycle=True),
        module_name="Patient",
        edition="2026b",
        expand_macros=True,
        query_id="query-1",
        resolved_at=RESOLVED_AT,
    )

    assert response.status == "ok"
    assert response.warnings == [
        "skipped recursive macro include cycle: "
        "2026b.macro.table_10_7 -> 2026b.macro.table_11_1 -> "
        "2026b.macro.table_10_7"
    ]
