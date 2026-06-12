from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part03_iods import parse_part03
from tests.fixtures_synthetic import PS33_CT_IMAGE_DOCBOOK


def test_parse_part03_ct_iod_modules_and_usage() -> None:
    result = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"), edition="2026b"
    )

    assert [iod.name for iod in result.iods] == [
        "CT Image",
        "Enhanced CT Image",
    ]
    assert [module.name for module in result.modules] == [
        "Patient",
        "Contrast/Bolus",
        "CT Image",
    ]

    contrast_use = result.iod_module_uses[1]
    assert contrast_use.information_entity == "Image"
    assert contrast_use.usage == "C"
    assert contrast_use.usage_condition_text == "Required if contrast media was used"
    assert contrast_use.source_ref.table_id == "table_A.3-1"

    patient_module = result.modules[0]
    assert patient_module.name == "Patient"
    assert patient_module.source_ref.table_id == "table_C.7-1"


def test_parse_part03_module_macro_attributes_and_include_rows() -> None:
    result = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"), edition="2026b"
    )

    patient_attrs = [
        row
        for row in result.attribute_uses
        if row.owner_id == "2026b.module.patient"
    ]
    assert [row.row_kind for row in patient_attrs] == [
        "attribute",
        "attribute",
        "attribute",
        "include",
    ]
    assert patient_attrs[0].attribute_tag == "(0010,0010)"
    assert patient_attrs[2].parent_attribute_use_id == patient_attrs[1].id
    assert patient_attrs[2].sequence_depth == 1

    include = patient_attrs[3]
    assert include.included_macro_id == "2026b.macro.table_10_7"
    assert include.include_target_text == (
        'Include Table 10-7 "General Anatomy Optional Macro"'
    )

    macro_attrs = [
        row
        for row in result.attribute_uses
        if row.owner_id == "2026b.macro.table_10_7"
    ]
    assert macro_attrs[0].attribute_name == "Anatomic Region Sequence"
    assert macro_attrs[0].source_ref.part == "PS3.3"


def test_parse_part03_functional_group_usage() -> None:
    result = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"), edition="2026b"
    )

    assert len(result.iod_functional_group_uses) == 1
    use = result.iod_functional_group_uses[0]
    assert use.macro_id == "2026b.macro.table_10_7"
    assert use.usage == "C"
    assert use.usage_condition_text == "Required if anatomy is known"
    assert result.warnings == ()
