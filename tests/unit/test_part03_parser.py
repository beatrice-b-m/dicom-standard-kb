from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part03_iods import parse_part03
from tests.fixtures_synthetic import EDITION, PS33_CT_IMAGE_DOCBOOK


def test_parse_part03_ct_iod_modules_and_usage() -> None:
    result = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"), edition=EDITION
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
    assert contrast_use.condition_id == f"{EDITION}.iod.ct_image.module_use.1.condition"
    assert contrast_use.source_ref.table_id == "table_A.3-1"

    assert [condition.id for condition in result.conditions] == [
        f"{EDITION}.iod.ct_image.module_use.1.condition",
        f"{EDITION}.iod.enhanced_ct_image.functional_group_use.0.condition",
    ]
    assert result.conditions[0].raw_text == "Required if contrast media was used"
    assert result.conditions[0].condition_kind == "required_if"
    assert result.conditions[0].machine_status == "raw_text"

    patient_module = result.modules[0]
    assert patient_module.name == "Patient"
    assert patient_module.source_ref.table_id == "table_C.7-1"


def test_parse_part03_accepts_ie_header_alias() -> None:
    xml = """\
<book xmlns="http://docbook.org/ns/docbook" xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <chapter xml:id="chapter_A">
    <table xml:id="table_A.3-1">
      <caption>CT Image IOD Modules</caption>
      <thead>
        <tr>
          <th>IE</th>
          <th>Module</th>
          <th>Reference</th>
          <th>Usage</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Patient</td>
          <td>Patient</td>
          <td>C.7.1.1</td>
          <td>M</td>
        </tr>
      </tbody>
    </table>
  </chapter>
</book>
"""

    result = parse_part03(parse_docbook_xml(xml, part="PS3.3"), edition=EDITION)

    assert [iod.name for iod in result.iods] == ["CT Image"]
    assert result.iod_module_uses[0].information_entity == "Patient"


def test_parse_part03_registers_iod_table_without_ie_or_usage() -> None:
    xml = """\
<book xmlns="http://docbook.org/ns/docbook" xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <chapter xml:id="chapter_B">
    <section xml:id="sect_B.30">
      <table xml:id="table_B.30.2-1">
        <caption>Inventory Creation IOD Modules</caption>
        <thead>
          <tr>
            <th>Module</th>
            <th>Reference</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Inventory Creation</td>
            <td>C.38.3</td>
            <td>Request and response attributes.</td>
          </tr>
        </tbody>
      </table>
    </section>
  </chapter>
</book>
"""

    result = parse_part03(parse_docbook_xml(xml, part="PS3.3"), edition=EDITION)

    assert [iod.name for iod in result.iods] == ["Inventory Creation"]
    assert result.iod_module_uses[0].usage == ""


def test_parse_part03_module_macro_attributes_and_include_rows() -> None:
    result = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"), edition=EDITION
    )

    patient_attrs = [
        row
        for row in result.attribute_uses
        if row.owner_id == f"{EDITION}.module.patient"
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
    assert include.included_macro_id == f"{EDITION}.macro.table_10_7"
    assert include.include_target_text == (
        'Include Table 10-7 "General Anatomy Optional Macro"'
    )

    macro_attrs = [
        row
        for row in result.attribute_uses
        if row.owner_id == f"{EDITION}.macro.table_10_7"
    ]
    assert macro_attrs[0].attribute_name == "Anatomic Region Sequence"
    assert macro_attrs[0].source_ref.part == "PS3.3"


def test_parse_part03_creates_conditions_for_conditional_attribute_rows() -> None:
    xml = PS33_CT_IMAGE_DOCBOOK.replace(
        "<entry>2</entry><entry>Patient name.</entry>",
        "<entry>1C</entry><entry>Required if patient identity is known.</entry>",
    )

    result = parse_part03(parse_docbook_xml(xml, part="PS3.3"), edition=EDITION)

    patient_name = result.attribute_uses[0]
    assert patient_name.type_designation == "1C"
    assert (
        patient_name.condition_id
        == f"{EDITION}.module.patient.attribute_use.0.condition"
    )
    condition = next(
        item
        for item in result.conditions
        if item.id == f"{EDITION}.module.patient.attribute_use.0.condition"
    )
    assert condition.raw_text == "Required if patient identity is known."
    assert condition.condition_kind == "required_if"
    assert condition.source_ref.table_id == "table_C.7-1"


def test_parse_part03_functional_group_usage() -> None:
    result = parse_part03(
        parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3"), edition=EDITION
    )

    assert len(result.iod_functional_group_uses) == 1
    use = result.iod_functional_group_uses[0]
    assert use.macro_id == f"{EDITION}.macro.table_10_7"
    assert use.usage == "C"
    assert use.usage_condition_text == "Required if anatomy is known"
    assert (
        use.condition_id
        == f"{EDITION}.iod.enhanced_ct_image.functional_group_use.0.condition"
    )
    # The fixture defines tables for Patient and CT Image only.
    assert [warning.message for warning in result.warnings] == [
        "module 'Contrast/Bolus' has no attribute table",
        "module 'CT Image' has no attribute table",
    ]


def test_parse_part03_resolves_functional_group_usage_by_section_anchor() -> None:
    xml = PS33_CT_IMAGE_DOCBOOK.replace(
        '<entry><xref linkend="table_10-7"/>General Anatomy Optional Macro</entry>',
        "<entry>General Anatomy</entry>",
    ).replace(
        "<entry>10-7</entry><entry>C - Required if anatomy is known</entry>",
        '<entry><xref linkend="sect_10.7"/></entry>'
        "<entry>C - Required if anatomy is known</entry>",
    )

    result = parse_part03(parse_docbook_xml(xml, part="PS3.3"), edition=EDITION)

    assert len(result.iod_functional_group_uses) == 1
    assert result.iod_functional_group_uses[0].macro_id == f"{EDITION}.macro.table_10_7"
    assert not [w for w in result.warnings if "functional group" in w.message]
