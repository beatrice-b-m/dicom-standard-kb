from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part04_sop_classes import parse_part04
from tests.fixtures_synthetic import PS34_SOP_CLASSES_DOCBOOK


def test_parse_part04_sop_classes_and_iod_edges() -> None:
    result = parse_part04(
        parse_docbook_xml(PS34_SOP_CLASSES_DOCBOOK, part="PS3.4"), edition="2026b"
    )

    assert [service.name for service in result.service_classes] == [
        "Storage Service Class"
    ]
    assert [sop.name for sop in result.sop_classes] == [
        "CT Image Storage",
        "Enhanced CT Image Storage",
    ]
    assert [sop.uid_value for sop in result.sop_classes] == [
        "1.2.840.10008.5.1.4.1.1.2",
        "1.2.840.10008.5.1.4.1.1.2.1",
    ]
    assert [edge.iod_id for edge in result.sop_class_iods] == [
        "2026b.iod.ct_image",
        "2026b.iod.enhanced_ct_image",
    ]
    assert result.sop_class_iods[0].resolution == "parsed"
    assert result.sop_class_iods[0].source_ref.part == "PS3.4"
    assert result.warnings[0].message.startswith("skipped malformed SOP Class UID")


def test_parse_part04_derives_storage_iod_when_xref_text_is_empty() -> None:
    xml = """\
<book xmlns="http://docbook.org/ns/docbook" xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <chapter xml:id="chapter_B">
    <table xml:id="table_B.5-1">
      <caption>Standard SOP Classes</caption>
      <thead>
        <tr>
          <th>SOP Class Name</th>
          <th>SOP Class UID</th>
          <th>
            IOD Specification (defined in
            <olink targetdoc="PS3.3" targetptr="PS3.3"/>)
          </th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>CT Image Storage</td>
          <td>1.2.840.10008.5.1.4.1.1.2</td>
          <td>
            <olink targetdoc="PS3.3" targetptr="sect_A.3" xrefstyle="select: title"/>
          </td>
        </tr>
      </tbody>
    </table>
  </chapter>
</book>
"""

    result = parse_part04(parse_docbook_xml(xml, part="PS3.4"), edition="2026b")

    assert [sop.name for sop in result.sop_classes] == ["CT Image Storage"]
    assert [edge.iod_id for edge in result.sop_class_iods] == [
        "2026b.iod.ct_image"
    ]


def test_parse_part04_prefers_iod_reference_map() -> None:
    xml = """\
<book xmlns="http://docbook.org/ns/docbook" xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <chapter xml:id="chapter_B">
    <table xml:id="table_B.5-1">
      <caption>Standard SOP Classes</caption>
      <thead>
        <tr>
          <th>SOP Class Name</th>
          <th>SOP Class UID</th>
          <th>IOD Specification</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Digital X-Ray Image Storage - For Presentation</td>
          <td>1.2.840.10008.5.1.4.1.1.1.1</td>
          <td>
            <olink targetdoc="PS3.3" targetptr="sect_A.26" xrefstyle="select: title"/>
          </td>
        </tr>
      </tbody>
    </table>
  </chapter>
</book>
"""

    result = parse_part04(
        parse_docbook_xml(xml, part="PS3.4"),
        edition="2026b",
        iod_id_by_ref={"sect_A.26": "2026b.iod.digital_x_ray_image"},
    )

    assert [edge.iod_id for edge in result.sop_class_iods] == [
        "2026b.iod.digital_x_ray_image"
    ]
