from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.ir.validators import IdentifierValidationError, normalize_tag, tag_matches
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from tests.fixtures_synthetic import PS36_REGISTRY_DOCBOOK


def test_parse_part06_data_elements_and_range_tags() -> None:
    result = parse_part06(
        parse_docbook_xml(PS36_REGISTRY_DOCBOOK, part="PS3.6"), edition="2026b"
    )

    modality = result.data_elements[0]
    assert modality.tag == "(0008,0060)"
    assert modality.group_pattern == "0008"
    assert modality.element_pattern == "0060"
    assert modality.vr == "CS"
    assert modality.vm == "1"
    assert modality.source_ref.part == "PS3.6"

    overlay = next(
        element for element in result.data_elements if element.tag == "(60xx,3000)"
    )
    assert overlay.tag == "(60xx,3000)"
    assert overlay.is_range is True
    assert tag_matches(overlay.tag, "(6002,3000)")

    retired = next(
        element for element in result.data_elements if element.tag == "(50xx,xxxx)"
    )
    assert retired.retired is True
    assert retired.name == "Curve Data"

    retired_from_column = next(
        element for element in result.data_elements if element.tag == "(0008,0001)"
    )
    assert retired_from_column.retired is True
    assert retired_from_column.name == "Length to End"
    assert any("malformed tag" in warning.message for warning in result.warnings)


def test_parse_part06_uid_registry_and_zero_width_keywords() -> None:
    result = parse_part06(
        parse_docbook_xml(PS36_REGISTRY_DOCBOOK, part="PS3.6"), edition="2026b"
    )

    uid = result.uid_registry_entries[0]
    assert uid.uid_value == "1.2.840.10008.1.2.1"
    assert uid.uid_keyword == "ExplicitVRLittleEndian"
    assert uid.uid_type == "Transfer Syntax"
    assert uid.part == "PS3.5"

    retired = result.uid_registry_entries[1]
    assert retired.retired is True
    assert retired.uid_name == "Explicit VR Big Endian"
    assert any("malformed UID" in warning.message for warning in result.warnings)


def test_normalize_tag_rejects_malformed_input() -> None:
    assert normalize_tag("(0008,0060)") == "(0008,0060)"
    assert normalize_tag("(60XX,3000)") == "(60xx,3000)"

    try:
        normalize_tag("0008,0060")
    except IdentifierValidationError as exc:
        assert "malformed DICOM tag" in str(exc)
    else:
        raise AssertionError("expected malformed tag to fail")
