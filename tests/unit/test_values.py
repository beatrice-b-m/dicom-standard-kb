from __future__ import annotations

import sqlite3
from pathlib import Path

from dicom_kb.db.importers import (
    import_attribute_value_terms,
    import_coded_concepts,
    import_context_groups,
    import_part03,
    import_sr_templates,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part03_iods import parse_part03
from dicom_kb.parsers.part16_content_mapping import parse_part16
from dicom_kb.query.markdown import render_markdown
from dicom_kb.query.resolver import attribute_values, code_lookup

# Values in a section the module points at, in a table cell, and in a list
# item that says which Value it is for; CIDs on a Code Sequence Macro under
# the attribute and on a module's include of the macro holding it.
PS33 = """\
<book xmlns="http://docbook.org/ns/docbook" xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <chapter xml:id="chapter_C">
    <section xml:id="sect_C.1">
      <title>Thing Series Module</title>
      <table xml:id="table_C.1-1">
        <caption>Thing Series Module Attributes</caption>
        <thead><tr><th>Attribute Name</th><th>Tag</th><th>Type</th>
          <th>Attribute Description</th></tr></thead>
        <tbody>
          <tr><td>Modality</td><td>(0008,0060)</td><td>1</td>
            <td><para>Type of device.</para>
              <para>See Section C.1.1.1 for Defined Terms.</para></td></tr>
          <tr><td>Image Type</td><td>(0008,0008)</td><td>1</td>
            <td><para>Image identification characteristics.</para></td></tr>
        </tbody>
      </table>
      <section xml:id="sect_C.1.1.1">
        <title>Modality</title>
        <variablelist>
          <title>Defined Terms:</title>
          <varlistentry><term>CT</term>
            <listitem><para>Computed Tomography</para></listitem></varlistentry>
          <varlistentry><term>MR</term>
            <listitem><para>Magnetic Resonance, see <xref
              linkend="sect_C.2"/></para></listitem></varlistentry>
        </variablelist>
      </section>
      <section xml:id="sect_C.1.1.2">
        <title>Image Type</title>
        <orderedlist>
          <listitem>
            <para>Value 1 shall identify the Pixel Data Characteristics</para>
            <variablelist>
              <title>Enumerated Values:</title>
              <varlistentry><term>ORIGINAL</term>
                <listitem><para>original</para></listitem></varlistentry>
              <varlistentry><term>DERIVED</term>
                <listitem><para>derived</para></listitem></varlistentry>
            </variablelist>
          </listitem>
        </orderedlist>
      </section>
    </section>
    <section xml:id="sect_C.2">
      <title>Thing Image Module</title>
      <table xml:id="table_C.2-1">
        <caption>Thing Image Module Attributes</caption>
        <thead><tr><th>Attribute Name</th><th>Tag</th><th>Type</th>
          <th>Attribute Description</th></tr></thead>
        <tbody>
          <tr><td>Modality</td><td>(0008,0060)</td><td>1</td>
            <td><para>Type of device.</para>
              <variablelist>
                <title>Enumerated Values:</title>
                <varlistentry><term>CT</term><listitem><para/></listitem>
                </varlistentry>
              </variablelist></td></tr>
          <tr><td colspan="4">Include Table 10-7 “General Anatomy Macro
            Attributes” Anatomic Region Sequence DCID 4030 “CT Anatomy”.</td></tr>
        </tbody>
      </table>
    </section>
    <section xml:id="sect_10.7">
      <title>General Anatomy Macro</title>
      <table xml:id="table_10-7">
        <caption>General Anatomy Macro Attributes</caption>
        <thead><tr><th>Attribute Name</th><th>Tag</th><th>Type</th>
          <th>Attribute Description</th></tr></thead>
        <tbody>
          <tr><td>Anatomic Region Sequence</td><td>(0008,2218)</td><td>3</td>
            <td><para>Region.</para></td></tr>
          <tr><td colspan="4">&gt;Include <xref linkend="table_8.8-1"/> “Code
            Sequence Macro Attributes” CID may be defined in the Macro
            invocation.</td></tr>
        </tbody>
      </table>
    </section>
    <section xml:id="sect_8.8">
      <title>Code Sequence Macro</title>
      <table xml:id="table_8.8-1">
        <caption>Code Sequence Macro Attributes</caption>
        <thead><tr><th>Attribute Name</th><th>Tag</th><th>Type</th>
          <th>Attribute Description</th></tr></thead>
        <tbody>
          <tr><td>Code Value</td><td>(0008,0100)</td><td>1C</td>
            <td><para>The code.</para></td></tr>
        </tbody>
      </table>
    </section>
  </chapter>
</book>
"""

# Two context groups, one including the other, a template, and Table D-1.
PS316 = """\
<book xmlns="http://docbook.org/ns/docbook" xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <chapter xml:id="chapter_B">
    <section xml:id="sect_CID_4030">
      <title>CT Anatomy</title>
      <para>Type: Extensible</para>
      <para>Version: 20250101</para>
      <table xml:id="table_CID_4030">
        <caption>CT Anatomy</caption>
        <thead><tr><th>Coding Scheme Designator</th><th>Code Value</th>
          <th>Code Meaning</th></tr></thead>
        <tbody>
          <tr><td>SCT</td><td>818981001</td><td>Abdomen</td></tr>
          <tr><td colspan="3">Include <xref linkend="sect_CID_4031"/>
            "Common Anatomic Region"</td></tr>
        </tbody>
      </table>
    </section>
    <section xml:id="sect_CID_4031">
      <title>Common Anatomic Region</title>
      <para>Type: Extensible</para>
      <table xml:id="table_CID_4031">
        <caption>Common Anatomic Region</caption>
        <thead><tr><th>Coding Scheme Designator</th><th>Code Value</th>
          <th>Code Meaning</th></tr></thead>
        <tbody>
          <tr><td>SCT</td><td>76752008</td><td>Breast</td></tr>
          <tr><td>DCM</td><td>121071</td><td>Finding</td></tr>
        </tbody>
      </table>
    </section>
  </chapter>
  <chapter xml:id="chapter_D">
    <section xml:id="sect_D">
      <title>DICOM Controlled Terminology Definitions</title>
      <table xml:id="table_D-1">
        <caption>DICOM Controlled Terminology Definitions</caption>
        <thead><tr><th>Code Value</th><th>Code Meaning</th><th>Definition</th>
          <th>Notes</th></tr></thead>
        <tbody>
          <tr><td>121071</td><td>Finding</td>
            <td>An observation found on an imaging study.</td><td/></tr>
          <tr><td>AS</td><td>Angioscopy</td>
            <td>A device that records angioscopy.</td><td>Retired</td></tr>
        </tbody>
      </table>
    </section>
  </chapter>
</book>
"""


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    document = parse_docbook_xml(PS33, part="PS3.3")
    parsed = parse_part03(document, edition="2026d")
    import_part03(
        connection,
        edition="2026d",
        iods=parsed.iods,
        modules=parsed.modules,
        macros=parsed.macros,
        iod_module_uses=parsed.iod_module_uses,
        iod_functional_group_uses=parsed.iod_functional_group_uses,
        attribute_uses=parsed.attribute_uses,
        conditions=parsed.conditions,
    )
    connection.execute(
        "INSERT INTO source_ref (id, edition_id, part, table_id) "
        "VALUES ('ps36', '2026d', 'PS3.6', 'table_6-1')"
    )
    for tag, name, keyword, vr in [
        ("(0008,0008)", "Image Type", "ImageType", "CS"),
        ("(0008,0060)", "Modality", "Modality", "CS"),
        ("(0008,0100)", "Code Value", "CodeValue", "SH"),
        ("(0008,2218)", "Anatomic Region Sequence", "AnatomicRegionSequence", "SQ"),
    ]:
        connection.execute(
            """
            INSERT INTO data_element (id, edition_id, tag, group_pattern,
              element_pattern, is_range, name, keyword, vr, vm, retired,
              source_ref_id)
            VALUES (?, '2026d', ?, '', '', 0, ?, ?, ?, '1', 0, 'ps36')
            """,
            (f"2026d.{keyword}", tag, name, keyword, vr),
        )
    import_attribute_value_terms(connection, edition="2026d", document=document)
    part16 = parse_part16(parse_docbook_xml(PS316, part="PS3.16"), edition="2026d")
    import_sr_templates(
        connection,
        edition="2026d",
        templates=part16.sr_templates,
        rows=part16.sr_template_rows,
    )
    import_context_groups(
        connection,
        edition="2026d",
        context_groups=part16.context_groups,
        rows=part16.context_group_rows,
    )
    import_coded_concepts(
        connection, edition="2026d", coded_concepts=part16.coded_concepts
    )
    return connection


def _values(connection: sqlite3.Connection, name: str, **kwargs: object) -> str:
    return render_markdown(
        attribute_values(connection, name=name, edition="2026d", **kwargs)  # type: ignore[arg-type]
    )


def _code(connection: sqlite3.Connection, query: str, **kwargs: object) -> str:
    return render_markdown(
        code_lookup(connection, query=query, edition="2026d", **kwargs)  # type: ignore[arg-type]
    )


def test_values_join_section_lists_to_the_modules_that_point_at_them(
    tmp_path: Path,
) -> None:
    markdown = _values(_connection(tmp_path), "Modality")

    assert "**Defined Terms** (Section C.1.1.1), referenced by Thing Series Module" in (
        markdown
    )
    assert "| CT | Computed Tomography |" in markdown
    # The reference in a meaning keeps its target.
    assert "| MR | Magnetic Resonance, see Section C.2 |" in markdown
    assert "**Enumerated Values** in Thing Image Module: CT" in markdown
    assert markdown.rstrip().endswith("Source: PS3.6 Table 6-1; PS3.3 C.1.1.1 (2026d)")


def test_values_within_a_module_keep_only_what_applies_there(tmp_path: Path) -> None:
    markdown = _values(_connection(tmp_path), "(0008,0060)", within="Thing Image")

    assert "In the Thing Image Module." in markdown
    assert "**Enumerated Values** in Thing Image Module: CT" in markdown
    assert "Defined Terms" not in markdown


def test_values_name_the_value_a_list_item_is_for(tmp_path: Path) -> None:
    markdown = _values(_connection(tmp_path), "ImageType")

    assert (
        "**Value 1 shall identify the Pixel Data Characteristics. Enumerated "
        "Values** (Section C.1.1.2)"
    ) in markdown
    assert "| ORIGINAL | original |" in markdown


def test_values_name_the_cid_a_module_sets_for_a_code_sequence(
    tmp_path: Path,
) -> None:
    markdown = _values(_connection(tmp_path), "Anatomic Region Sequence")

    assert "| Where | Codes |" in markdown
    assert (
        "| General Anatomy Macro | CID may be defined in the Macro invocation. |"
    ) in markdown
    assert (
        "| Thing Image Module | Anatomic Region Sequence DCID 4030 “CT Anatomy”. "
        "(via General Anatomy Macro) |"
    ) in markdown
    assert 'dicom_code("CID <n>")' in markdown


def test_values_report_an_attribute_without_values(tmp_path: Path) -> None:
    markdown = _values(_connection(tmp_path), "Code Value")

    assert "No enumerated values, defined terms or context groups" in markdown


def test_values_suggest_close_names(tmp_path: Path) -> None:
    response = attribute_values(_connection(tmp_path), name="Modalty", edition="2026d")

    assert response.status == "not_found"
    assert response.result is not None
    assert "Modality" in response.result["message"]


def test_code_lists_a_group_with_its_includes_expanded(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    markdown = _code(connection, "DCID 4030")

    assert markdown.startswith(
        "**CID 4030 CT Anatomy** · Extensible · Version 20250101"
    )
    assert "| SCT | 818981001 | Abdomen |" in markdown
    assert "Includes CID 4031 Common Anatomic Region." in markdown
    assert "**From CID 4031 Common Anatomic Region**" in markdown
    assert "| SCT | 76752008 | Breast |" in markdown
    assert _code(connection, "CT Anatomy") == markdown


def test_code_gives_meaning_definition_and_groups(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    markdown = _code(connection, "(121071, DCM)")

    assert markdown.startswith('**(121071, DCM, "Finding")**')
    assert "Definition: An observation found on an imaging study." in markdown
    assert "In CID 4031 Common Anatomic Region." in markdown
    assert "Also through includes in CID 4030 CT Anatomy." in markdown
    assert _code(connection, "121071", scheme="DCM") == markdown
    assert _code(connection, "DCM 121071") == markdown


def test_code_knows_dcm_codes_no_group_lists(tmp_path: Path) -> None:
    markdown = _code(_connection(tmp_path), "AS")

    assert '**(AS, DCM, "Angioscopy")**' in markdown
    assert "Notes: Retired" in markdown
    assert "No context group lists it." in markdown


def test_code_not_found_suggests_names(tmp_path: Path) -> None:
    response = code_lookup(_connection(tmp_path), query="CT Anatomie", edition="2026d")

    assert response.status == "not_found"
    assert response.result is not None
    assert "CID 4030 CT Anatomy" in response.result["message"]
