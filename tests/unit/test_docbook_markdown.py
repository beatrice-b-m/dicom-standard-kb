from __future__ import annotations

from lxml import etree

from dicom_kb.docbook.markdown import plain_text
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.docbook.targets import TargetIndex

NS = (
    'xmlns="http://docbook.org/ns/docbook" '
    'xmlns:xml="http://www.w3.org/XML/1998/namespace"'
)

PS33 = f"""\
<book {NS} xml:id="PS3.3">
  <chapter label="C" xml:id="chapter_C">
    <title>Information Module Definitions (Normative)</title>
    <section label="C.7.3.1" xml:id="sect_C.7.3.1">
      <title>General Series Module</title>
      <para><xref linkend="table_C.7-5a" xrefstyle="select: label"/> specifies
        the Attributes of the
        <xref linkend="sect_C.7.3.1" xrefstyle="select: title"/>.</para>
      <table label="C.7-5a" xml:id="table_C.7-5a">
        <caption>General Series Module Attributes</caption>
        <thead><tr><th>Attribute Name</th><th>Tag</th><th>Type</th>
          <th>Attribute Description</th></tr></thead>
        <tbody>
          <tr><td>Modality</td><td>(0008,0060)</td><td>1</td>
            <td><para>Type of device.</para>
              <para>See <xref linkend="sect_C.7.3.1.1.1"
                xrefstyle="select: label"/> for Defined Terms.</para></td></tr>
          <tr><td>Laterality</td><td>(0020,0060)</td><td>2C</td>
            <td><para>Enumerated Values:</para>
              <variablelist><varlistentry><term>R</term>
                <listitem><para>right</para></listitem></varlistentry>
              <varlistentry><term>L</term>
                <listitem><para>left</para></listitem></varlistentry>
              </variablelist></td></tr>
          <tr><td><emphasis>&gt;Include <xref linkend="table_10-1"
            xrefstyle="select: label quotedtitle"/></emphasis></td>
            <td/><td/><td>D<olink targetdoc="PS3.16" targetptr="sect_CID_7210"
            xrefstyle="select: labelnumber quotedtitle"/>.</td></tr>
        </tbody>
      </table>
      <note><para>Anatomic Region uses
        B<olink targetdoc="PS3.16" targetptr="sect_CID_4"
        xrefstyle="select: labelnumber"/>; see
        <olink targetdoc="PS3.5" targetptr="sect_7.5.2"
        xrefstyle="select: labelnumber"/> and
        <xref linkend="sect_missing"/>.</para></note>
      <section label="C.7.3.1.1.1" xml:id="sect_C.7.3.1.1.1">
        <title>Modality</title>
        <para>Defined Terms:</para>
        <variablelist><varlistentry><term>CT</term>
          <listitem><para>Computed Tomography</para></listitem></varlistentry>
        </variablelist>
      </section>
    </section>
  </chapter>
  <chapter label="10" xml:id="chapter_10">
    <title>Macros</title>
    <table label="10-1" xml:id="table_10-1">
      <caption>Person Identification Macro Attributes</caption>
      <tbody><tr><td rowspan="2">Person</td><td>A</td></tr>
        <tr><td>B</td></tr>
        <tr><td colspan="2">spanning</td></tr></tbody>
    </table>
  </chapter>
</book>
"""

PS316 = f"""\
<book {NS} xml:id="PS3.16">
  <chapter label="B" xml:id="chapter_B"><title>Context Groups</title>
    <section label="CID 4" xml:id="sect_CID_4"><title>Anatomic Region</title>
    </section>
    <section label="CID 7210" xml:id="sect_CID_7210">
      <title>Related Series Purpose of Reference</title>
    </section>
  </chapter>
</book>
"""

PS35 = f"""\
<book {NS} xml:id="PS3.5">
  <chapter label="7" xml:id="chapter_7"><title>The Data Set</title>
    <section label="7.5.2" xml:id="sect_7.5.2">
      <title>Delimitation of The Sequence of Items</title>
    </section>
  </chapter>
</book>
"""


def _index() -> TargetIndex:
    targets = TargetIndex()
    for part, xml in (("PS3.3", PS33), ("PS3.16", PS316), ("PS3.5", PS35)):
        targets.add_document(etree.fromstring(xml.encode()), part=part)
    return targets


def test_section_body_resolves_every_reference_style() -> None:
    document = parse_docbook_xml(PS33, part="PS3.3", targets=_index())
    section = next(s for s in document.sections if s.xml_id == "sect_C.7.3.1")

    assert section.number == "C.7.3.1"
    assert section.informative is False
    assert section.markdown.splitlines()[0] == (
        "Table C.7-5a specifies the Attributes of the General Series Module "
        "(Section C.7.3.1)."
    )
    assert "[[table:table_C.7-5a]]" in section.markdown
    # CIDs need no part; other cross-part targets name theirs.
    assert (
        "> Note: Anatomic Region uses BCID 4; see PS3.5 Section 7.5.2 and "
        "Section missing."
    ) in section.markdown
    assert document.unresolved_references == ("PS3.3 sect_missing",)


def test_table_markdown_keeps_cell_lists_references_and_spans() -> None:
    document = parse_docbook_xml(PS33, part="PS3.3", targets=_index())
    tables = {table.xml_id: table for table in document.tables}

    series = tables["table_C.7-5a"].markdown.splitlines()
    assert series[0] == "**Table C.7-5a: General Series Module Attributes**"
    assert series[1] == "| Attribute Name | Tag | Type | Attribute Description |"
    assert series[3] == (
        "| Modality | (0008,0060) | 1 | Type of device.<br>"
        "See Section C.7.3.1.1.1 for Defined Terms. |"
    )
    assert series[4] == (
        "| Laterality | (0020,0060) | 2C | Enumerated Values:<br>R: right<br>L: left |"
    )
    assert series[5] == (
        "| >Include Table 10-1 “Person Identification Macro Attributes” |  |  | "
        "DCID 7210 “Related Series Purpose of Reference”. |"
    )

    macro = tables["table_10-1"].markdown.splitlines()
    assert macro[1:] == [
        "|  |  |",
        "|---|---|",
        "| Person | A |",
        "| Person | B |",
        "| spanning |  |",
    ]


def test_include_rows_keep_their_table_id_after_resolution() -> None:
    document = parse_docbook_xml(PS33, part="PS3.3", targets=_index())
    table = next(t for t in document.tables if t.xml_id == "table_C.7-5a")
    include = table.rows[-1]

    assert include.row_kind == "include"
    assert include.include_table_ref == "table_10-1"
    assert include.cells[0].text == (
        ">Include Table 10-1 “Person Identification Macro Attributes”"
    )


def test_title_and_template_styles_keep_the_target() -> None:
    xml = f"""\
<book {NS}>
  <chapter label="A" xml:id="chapter_A"><title>Composite IODs</title>
    <section label="A.3" xml:id="sect_A.3"><title>CT Image IOD</title>
      <para><olink targetdoc="PS3.4" targetptr="sect_B.5"
        xrefstyle="template:Section %n “%t” in PS3.4"/> and
        <xref linkend="sect_A.3" xrefstyle="template:%t"/> and
        <xref linkend="chapter_A" xrefstyle="select: label"/> and
        <olink targetdoc="PS3.4" targetptr="PS3.4"/>.</para>
    </section>
  </chapter>
</book>
"""
    ps34 = f"""\
<book {NS} xml:id="PS3.4"><chapter label="B" xml:id="chapter_B">
  <title>Storage</title><section label="B.5" xml:id="sect_B.5">
  <title>Standard SOP Classes</title></section></chapter></book>
"""
    targets = TargetIndex()
    targets.add_document(etree.fromstring(ps34.encode()), part="PS3.4")
    document = parse_docbook_xml(xml, part="PS3.3", targets=targets)
    section = next(s for s in document.sections if s.xml_id == "sect_A.3")

    assert section.markdown == (
        "Section B.5 “Standard SOP Classes” in PS3.4 and CT Image IOD "
        "(Section A.3) and Annex A and PS3.4."
    )


def test_code_lists_and_informative_annexes() -> None:
    xml = f"""\
<book {NS}>
  <chapter label="G" xml:id="chapter_G">
    <title>Examples of Encoding (Informative)</title>
    <section label="G.1" xml:id="sect_G.1"><title>Sample</title>
      <orderedlist>
        <listitem><para>First step.</para></listitem>
        <listitem><para>Second step.</para>
          <itemizedlist><listitem><para>nested</para></listitem>
          </itemizedlist></listitem>
      </orderedlist>
      <programlisting>a  =  1
b = 2</programlisting>
    </section>
  </chapter>
</book>
"""
    document = parse_docbook_xml(xml, part="PS3.5")
    section = next(s for s in document.sections if s.xml_id == "sect_G.1")

    assert section.informative is True
    assert section.markdown == (
        "1. First step.\n2. Second step.\n   - nested\n\n```\na  =  1\nb = 2\n```"
    )


def test_plain_text_flattens_markdown_for_parsers() -> None:
    markdown = (
        "- Type: Extensible\n- Version: 20260603\n\n[[table:table_X]]\n\n"
        "**Table 1: T**\n| a | b |\n|---|---|\n| >Item | 1.2.840<br>next |"
    )

    assert plain_text(markdown) == (
        "Type: Extensible Version: 20260603 Table 1: T a b >Item 1.2.840 next"
    )
