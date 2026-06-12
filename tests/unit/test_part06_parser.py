from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.ir.validators import IdentifierValidationError, normalize_tag, tag_matches
from dicom_kb.parsers.part06_data_dictionary import parse_part06

PS36_FIXTURE = """\
<book xmlns="http://docbook.org/ns/docbook" xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <chapter>
    <table xml:id="table_6-1">
      <title>Registry of DICOM Data Elements</title>
      <tgroup cols="6">
        <thead>
          <row>
            <entry>Tag</entry><entry>Name</entry><entry>Keyword</entry>
            <entry>VR</entry><entry>VM</entry><entry>Retired</entry>
          </row>
        </thead>
        <tbody>
          <row>
            <entry>(0008,0060)</entry><entry>Modality</entry>
            <entry>Modality</entry><entry>CS</entry><entry>1</entry><entry></entry>
          </row>
          <row>
            <entry>(60xx,3000)</entry><entry>Overlay Data</entry>
            <entry>OverlayData</entry><entry>OW</entry><entry>1</entry><entry></entry>
          </row>
          <row>
            <entry>(50xx,xxxx)</entry><entry>Curve Data (Retired)</entry>
            <entry>CurveData</entry><entry>OB</entry><entry>1</entry><entry>RET</entry>
          </row>
          <row>
            <entry>not-a-tag</entry><entry>Bad</entry>
            <entry>Bad</entry><entry>CS</entry><entry>1</entry><entry></entry>
          </row>
        </tbody>
      </tgroup>
    </table>
    <table xml:id="table_A-1">
      <title>UID Registry</title>
      <tgroup cols="6">
        <thead>
          <row>
            <entry>UID Value</entry><entry>UID Name</entry>
            <entry>UID Keyword</entry><entry>UID Type</entry>
            <entry>Part</entry><entry>Retired</entry>
          </row>
        </thead>
        <tbody>
          <row>
            <entry>1.2.840.10008.1.2.1</entry>
            <entry>Explicit VR Little Endian</entry>
            <entry>Explicit\u200bVRLittleEndian</entry>
            <entry>Transfer Syntax</entry><entry>PS3.5</entry><entry></entry>
          </row>
          <row>
            <entry>1.2.840.10008.1.2.2</entry>
            <entry>Explicit VR Big Endian (Retired)</entry>
            <entry>ExplicitVRBigEndian</entry>
            <entry>Transfer Syntax</entry><entry>PS3.5</entry><entry>RET</entry>
          </row>
          <row>
            <entry>1.2.840.bad</entry><entry>Bad UID</entry>
            <entry>BadUID</entry><entry>SOP Class</entry>
            <entry>PS3.4</entry><entry></entry>
          </row>
        </tbody>
      </tgroup>
    </table>
  </chapter>
</book>
"""


def test_parse_part06_data_elements_and_range_tags() -> None:
    result = parse_part06(
        parse_docbook_xml(PS36_FIXTURE, part="PS3.6"), edition="2026b"
    )

    modality = result.data_elements[0]
    assert modality.tag == "(0008,0060)"
    assert modality.group_pattern == "0008"
    assert modality.element_pattern == "0060"
    assert modality.vr == "CS"
    assert modality.vm == "1"
    assert modality.source_ref.part == "PS3.6"

    overlay = result.data_elements[1]
    assert overlay.tag == "(60xx,3000)"
    assert overlay.is_range is True
    assert tag_matches(overlay.tag, "(6002,3000)")

    retired = result.data_elements[2]
    assert retired.retired is True
    assert retired.name == "Curve Data"
    assert any("malformed tag" in warning.message for warning in result.warnings)


def test_parse_part06_uid_registry_and_zero_width_keywords() -> None:
    result = parse_part06(
        parse_docbook_xml(PS36_FIXTURE, part="PS3.6"), edition="2026b"
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
