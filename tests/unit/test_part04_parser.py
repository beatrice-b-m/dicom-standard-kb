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
