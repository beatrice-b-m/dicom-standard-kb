from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.docbook.text_chunks import normalize_text

DOCBOOK = """\
<book xmlns="http://docbook.org/ns/docbook" xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <chapter xml:id="chapter_A">
    <label>A</label>
    <title>IODs</title>
    <section xml:id="sect_A.3">
      <label>A.3</label>
      <title>CT Image</title>
      <para>See <xref linkend="table_A.3-1"/> and <xref linkend="missing"/>.</para>
      <table xml:id="table_A.3-1">
        <title>CT Image IOD Modules</title>
        <tgroup cols="4">
          <thead>
            <row>
              <entry>Information Entity</entry>
              <entry>Module</entry>
              <entry>Reference</entry>
              <entry>Usage</entry>
            </row>
          </thead>
          <tbody>
            <row>
              <entry>Patient</entry>
              <entry>Patient</entry>
              <entry><xref linkend="sect_C.7.1.1"/></entry>
              <entry>M</entry>
            </row>
            <row>
              <entry namest="col1" nameend="col4">
                Include Table 10-7 "General Anatomy Optional Macro"
              </entry>
            </row>
            <row>
              <entry morerows="1">Image</entry>
              <entry>CT Image</entry>
              <entry>C.8.2.1</entry>
              <entry>M</entry>
            </row>
            <row>
              <entry>Contrast/Bolus</entry>
              <entry>C.7.6.4</entry>
              <entry>C</entry>
            </row>
          </tbody>
        </tgroup>
      </table>
      <variablelist xml:id="vl_A.3-1">
        <title>Defined Terms</title>
        <varlistentry xml:id="vl_entry_ct">
          <term xml:id="vl_term_ct">CT</term>
          <listitem xml:id="vl_def_ct">
            <para>
              Computed Tomography, as defined near <xref linkend="sect_A.3"/>.
            </para>
          </listitem>
        </varlistentry>
        <varlistentry>
          <term>MR</term>
          <term>MRI</term>
          <listitem>
            <para>Magnetic Resonance Imaging.</para>
          </listitem>
        </varlistentry>
      </variablelist>
    </section>
  </chapter>
</book>
"""


def test_docbook_parser_extracts_sections_tables_and_xrefs() -> None:
    parsed = parse_docbook_xml(DOCBOOK, part="PS3.3")

    assert parsed.part == "PS3.3"
    assert parsed.sections[0].xml_id == "chapter_A"
    assert parsed.sections[1].xml_id == "sect_A.3"
    assert parsed.sections[1].title == "CT Image"
    assert parsed.tables[0].xml_id == "table_A.3-1"
    assert parsed.tables[0].title == "CT Image IOD Modules"
    assert parsed.variablelists[0].xml_id == "vl_A.3-1"
    assert parsed.variablelists[0].title == "Defined Terms"
    assert "unresolved xref target: missing" in parsed.warnings


def test_table_parser_preserves_spans_and_include_rows() -> None:
    table = parse_docbook_xml(DOCBOOK, part="PS3.3").tables[0]

    include_row = table.rows[2]
    assert include_row.row_kind == "include"
    assert include_row.include_table_ref == "10-7"
    assert include_row.include_title == "General Anatomy Optional Macro"
    assert include_row.cells[0].colspan == 4

    row_with_span = table.rows[3]
    following_row = table.rows[4]
    assert row_with_span.cells[0].rowspan == 2
    assert following_row.cells[0].column == 1


def test_table_parser_accepts_html_table_vocabulary() -> None:
    xml = """\
<book xmlns="http://docbook.org/ns/docbook" xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <chapter xml:id="chapter_6">
    <title>Registry</title>
    <table xml:id="table_6-1">
      <caption>Registry of DICOM Data Elements</caption>
      <thead>
        <tr>
          <th>Tag</th>
          <th>Name</th>
          <th>Keyword</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td rowspan="2">(0008,0060)</td>
          <td>Modality</td>
          <td>Modality</td>
        </tr>
        <tr>
          <td colspan="2">continued</td>
        </tr>
      </tbody>
    </table>
  </chapter>
</book>
"""

    table = parse_docbook_xml(xml, part="PS3.6").tables[0]

    assert table.title == "Registry of DICOM Data Elements"
    assert [cell.text for cell in table.rows[0].cells] == ["Tag", "Name", "Keyword"]
    assert table.rows[1].cells[0].rowspan == 2
    assert table.rows[2].cells[0].column == 1
    assert table.rows[2].cells[0].colspan == 2


def test_variablelist_parser_preserves_terms_definitions_and_source_context() -> None:
    variablelist = parse_docbook_xml(DOCBOOK, part="PS3.3").variablelists[0]

    assert variablelist.parent_xml_id == "sect_A.3"
    assert variablelist.ordinal == 0

    ct_entry = variablelist.entries[0]
    assert ct_entry.entry_xml_id == "vl_entry_ct"
    assert ct_entry.terms == ("CT",)
    assert ct_entry.term_xml_ids == ("vl_term_ct",)
    assert ct_entry.definition_xml_id == "vl_def_ct"
    assert ct_entry.definition == "Computed Tomography, as defined near ."
    assert ct_entry.xrefs == ("sect_A.3",)

    multi_term_entry = variablelist.entries[1]
    assert multi_term_entry.terms == ("MR", "MRI")
    assert multi_term_entry.definition == "Magnetic Resonance Imaging."


def test_zero_width_characters_are_removed_from_normalized_text() -> None:
    assert normalize_text("Explicit\u200bVRLittleEndian") == "ExplicitVRLittleEndian"


def test_section_body_ignores_processing_instructions() -> None:
    xml = """\
<book xmlns="http://docbook.org/ns/docbook" xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <chapter xml:id="chapter_with_pi">
    <label>1</label>
    <title>Chapter</title>
    <?dbhtml filename="chapter.html"?>
    <para>Body text survives.</para>
  </chapter>
</book>
"""

    parsed = parse_docbook_xml(xml, part="PS3.3")

    assert parsed.sections[0].plain_text == "Body text survives."
