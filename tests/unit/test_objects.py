from __future__ import annotations

import sqlite3
from pathlib import Path

from dicom_kb.db.importers import import_part03
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part03_iods import parse_part03
from dicom_kb.query.markdown import render_markdown
from dicom_kb.query.resolver import element_usage, iod_modules, module_attributes

# A module that includes a coded-entry macro twice, a macro that includes
# itself, heading rows, a module with no Type column, an IOD whose row names
# one module but references another, and functional group macros.
PS33 = """\
<book xmlns="http://docbook.org/ns/docbook" xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <chapter xml:id="chapter_A">
    <section xml:id="sect_A.1">
      <title>Thing IOD</title>
      <table xml:id="table_A.1-1">
        <caption>Thing IOD Modules</caption>
        <thead><tr><th>IE</th><th>Module</th><th>Reference</th><th>Usage</th></tr></thead>
        <tbody>
          <tr><td>Series</td><td>Thing Series</td>
              <td><xref linkend="sect_C.1"/></td><td>M</td></tr>
          <tr><td>Image</td><td>Enhanced Thing</td>
              <td><xref linkend="sect_C.1"/></td>
              <td>C - Required if enhanced.</td></tr>
          <tr><td>Image</td><td>Worklist</td>
              <td><xref linkend="sect_C.3"/></td><td>U</td></tr>
        </tbody>
      </table>
      <table xml:id="table_A.1-2">
        <caption>Thing Functional Group Macros</caption>
        <thead><tr><th>Functional Group Macro</th><th>Section</th>
          <th>Usage</th></tr></thead>
        <tbody>
          <tr><td>Code Sequence Macro</td><td><xref linkend="table_8.8-1"/></td>
              <td>M</td></tr>
        </tbody>
      </table>
    </section>
  </chapter>
  <chapter xml:id="chapter_8">
    <section xml:id="sect_8.8">
      <table xml:id="table_8.8-1">
        <caption>Code Sequence Macro Attributes</caption>
        <thead><tr><th>Attribute Name</th><th>Tag</th><th>Type</th>
          <th>Attribute Description</th></tr></thead>
        <tbody>
          <tr><td colspan="4"><para><emphasis>BASIC CODED ENTRY ATTRIBUTES</emphasis>
            </para></td></tr>
          <tr><td>Code Value</td><td>(0008,0100)</td><td>1C</td>
              <td><para>The code.</para><para>Required if short.</para></td></tr>
          <tr><td>Equivalent Code Sequence</td><td>(0008,0121)</td><td>3</td>
              <td>Equivalents.</td></tr>
          <tr><td>&gt;Include <xref linkend="table_8.8-1"/></td><td/><td/><td/></tr>
        </tbody>
      </table>
    </section>
  </chapter>
  <chapter xml:id="chapter_C">
    <section xml:id="sect_C.1">
      <table xml:id="table_C.1-1">
        <caption>Thing Series Module Attributes</caption>
        <thead><tr><th>Attribute Name</th><th>Tag</th><th>Type</th>
          <th>Attribute Description</th></tr></thead>
        <tbody>
          <tr><td>Modality</td><td>(0008,0060)</td><td>1</td><td>Kind.</td></tr>
          <tr><td>Anatomic Region Sequence</td><td>(0008,2218)</td><td>3</td>
              <td>Region.</td></tr>
          <tr><td>&gt;Include <xref linkend="table_8.8-1"/>
              DCID 4 "Anatomic Region"</td>
              <td/><td/><td/></tr>
          <tr><td>Series Type Code Sequence</td><td>(0008,2219)</td><td>3</td>
              <td>Type.</td></tr>
          <tr><td>&gt;Include <xref linkend="table_8.8-1"/></td><td/><td/><td/></tr>
        </tbody>
      </table>
    </section>
    <section xml:id="sect_C.2">
      <table xml:id="table_C.2-1">
        <caption>Enhanced Thing Module Attributes</caption>
        <thead><tr><th>Attribute Name</th><th>Tag</th><th>Type</th>
          <th>Attribute Description</th></tr></thead>
        <tbody>
          <tr><td>Image Type</td><td>(0008,0008)</td><td>1</td><td>Type.</td></tr>
          <tr><td>Purpose of Reference Code Sequence</td><td>(0040,A170)</td>
              <td>1</td><td>Purpose.</td></tr>
          <tr><td>&gt;Include <xref linkend="table_8.8-1"/></td><td/><td/><td/></tr>
        </tbody>
      </table>
    </section>
    <section xml:id="sect_C.3">
      <table xml:id="table_C.3-1">
        <caption>Worklist Module Attributes</caption>
        <thead><tr><th>Attribute Name</th><th>Tag</th>
          <th>Attribute Description</th></tr></thead>
        <tbody>
          <tr><td>Modality</td><td>(0008,0060)</td><td>Kind of worklist.</td></tr>
        </tbody>
      </table>
    </section>
  </chapter>
</book>
"""


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    parsed = parse_part03(parse_docbook_xml(PS33, part="PS3.3"), edition="2026d")
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
        ("(0008,0060)", "Modality", "Modality", "CS"),
        ("(0008,0100)", "Code Value", "CodeValue", "SH"),
        ("(0008,0121)", "Equivalent Code Sequence", "EquivalentCodeSequence", "SQ"),
    ]:
        connection.execute(
            """
            INSERT INTO data_element (id, edition_id, tag, group_pattern,
              element_pattern, is_range, name, keyword, vr, vm, retired,
              source_ref_id)
            VALUES (?, '2026d', ?, '', '', 0, ?, ?, ?, '1', 0, 'ps36')
            """,
            (tag, tag, name, keyword, vr),
        )
    return connection


def _markdown(response: object) -> str:
    return render_markdown(response)  # type: ignore[arg-type]


def test_module_expands_each_macro_once_and_keeps_headings(tmp_path: Path) -> None:
    text = _markdown(
        module_attributes(
            _connection(tmp_path), name="Thing Series", detail="full", edition="2026d"
        )
    )

    assert text.startswith("**Thing Series Module** (C.1, Table C.1-1)")
    lines = text.splitlines()
    assert "| >*BASIC CODED ENTRY ATTRIBUTES* |" in lines
    assert (
        "| >CodeValue | (0008,0100) | SH | 1 | 1C | The code.<br>Required if short. |"
        in lines
    )
    # The macro includes itself: the second include is not expanded again.
    assert "| >>Include Table 8.8-1 (Code Sequence Macro) (listed above) |" in lines
    assert (
        '| >Include Table 8.8-1 DCID 4 "Anatomic Region" (Code Sequence Macro) |'
        in lines
    )
    assert "| >Include Table 8.8-1 (Code Sequence Macro) (listed above) |" in lines
    assert sum("| >CodeValue |" in line for line in lines) == 1
    assert lines[-1] == "Source: PS3.3 Table C.1-1 (2026d)"


def test_module_is_found_by_table_and_macro_name(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    for name in ("Table 8.8-1", "8.8-1", "Code Sequence Macro", "code sequence"):
        text = _markdown(module_attributes(connection, name=name, edition="2026d"))
        assert text.startswith("**Code Sequence Macro** (Table 8.8-1)"), name


def test_module_not_found_names_the_closest(tmp_path: Path) -> None:
    response = module_attributes(_connection(tmp_path), name="Thing", edition="2026d")

    assert response.status == "not_found"
    assert _markdown(response) == (
        "No module or macro is named 'Thing'. Closest: Thing Series Module; "
        "Enhanced Thing Module.\n"
    )


def test_module_without_type_column_keeps_its_rows(tmp_path: Path) -> None:
    text = _markdown(
        module_attributes(_connection(tmp_path), name="Worklist", edition="2026d")
    )

    assert "| Modality | (0008,0060) | CS | 1 |  | Kind of worklist. |" in text


def test_iod_follows_the_row_name_when_its_reference_points_elsewhere(
    tmp_path: Path,
) -> None:
    text = _markdown(iod_modules(_connection(tmp_path), name="Thing", edition="2026d"))

    assert "| Series | Thing Series | C.1, Table C.1-1 | M |" in text
    assert (
        "| Image | Enhanced Thing | C.2, Table C.2-1 | C: Required if enhanced. |"
        in text
    )
    assert "| Code Sequence Macro | Table 8.8-1 | M |" in text
    assert 'dicom_iod("Thing", expand=true)' in text


def test_iod_checklist_lists_modules_then_functional_groups(tmp_path: Path) -> None:
    text = _markdown(
        iod_modules(
            _connection(tmp_path),
            name="Thing IOD",
            expand=True,
            usage="M,C,U",
            edition="2026d",
        )
    )

    assert "### Thing Series Module: M (C.1, Table C.1-1)" in text
    assert (
        "### Enhanced Thing Module: C: Required if enhanced. (C.2, Table C.2-1)" in text
    )
    # Only conditional attributes keep a description: their condition.
    assert "| Modality | (0008,0060) | CS | 1 | 1 |  |" in text
    assert "| >CodeValue | (0008,0100) | SH | 1 | 1C | Required if short. |" in text
    assert text.index("## Functional group macros") > text.index("### Worklist")
    assert "### Code Sequence Macro: M (Table 8.8-1)\n\nListed above." in text


def test_module_outline_keeps_macros_as_one_line(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    text = _markdown(
        module_attributes(connection, name="Thing Series", edition="2026d")
    )
    lines = text.splitlines()

    assert (
        '| >Include Table 8.8-1 DCID 4 "Anatomic Region" (Code Sequence Macro) '
        "(2 attributes) |"
    ) in lines
    assert "CodeValue" not in text
    assert lines[-3] == (
        '2 macro includes not expanded; open one with dicom_module("<macro>"). '
        "Descriptions cut to their first sentence and condition. Everything: "
        'dicom_module("Thing Series", detail="full").'
    )
    macro = _markdown(
        module_attributes(connection, name="Code Sequence Macro", edition="2026d")
    )
    assert (
        "| CodeValue | (0008,0100) | SH | 1 | 1C | The code. Required if short. |"
        in macro
    )


def test_module_type_filter_leaves_out_optional_sequences(tmp_path: Path) -> None:
    text = _markdown(
        module_attributes(
            _connection(tmp_path), name="Thing Series", types="1,1C", edition="2026d"
        )
    )

    assert "| Modality | (0008,0060) | CS | 1 | 1 | Kind. |" in text
    assert "AnatomicRegionSequence" not in text.split("\n\n")[1]
    assert (
        "Kept Type 1/1C, in sequences of those Types. Not shown: 2 attributes of "
        "other Types. 2 Type 1/1C attributes sit inside sequences of other Types: "
        "Anatomic Region Sequence (1), Series Type Code Sequence (1)."
    ) in text


def test_module_type_filter_expands_macros_in_kept_sequences(
    tmp_path: Path,
) -> None:
    text = _markdown(
        module_attributes(
            _connection(tmp_path),
            name="Enhanced Thing",
            types="required",
            edition="2026d",
        )
    )
    lines = text.splitlines()

    assert (
        "| Purpose of Reference Code Sequence | (0040,A170) |  |  | 1 | Purpose. |"
        in lines
    )
    assert "| >Include Table 8.8-1 (Code Sequence Macro) |" in lines
    assert (
        "| >CodeValue | (0008,0100) | SH | 1 | 1C | The code. Required if short. |"
        in lines
    )
    assert "EquivalentCodeSequence" not in text.split("\n\n")[1]


def test_module_rejects_an_unknown_type(tmp_path: Path) -> None:
    response = module_attributes(
        _connection(tmp_path), name="Thing Series", types="1,4", edition="2026d"
    )

    assert response.status == "validation_error"


def test_iod_checklist_leaves_out_u_modules_and_names_them(tmp_path: Path) -> None:
    text = _markdown(
        iod_modules(_connection(tmp_path), name="Thing", expand=True, edition="2026d")
    )

    assert "### Worklist" not in text
    assert (
        'Modules not shown: Worklist (U). Add them with usage="M,C,U", or name '
        'one with module="<module>".'
    ) in text


def test_iod_module_filter_lists_only_that_module(tmp_path: Path) -> None:
    text = _markdown(
        iod_modules(
            _connection(tmp_path), name="Thing", module="Worklist", edition="2026d"
        )
    )

    assert "### Worklist Module: U (C.3, Table C.3-1)" in text
    assert "### Thing Series" not in text
    assert "Modules not shown" not in text


def test_iod_type_filter_lists_a_macro_where_it_is_first_shown(
    tmp_path: Path,
) -> None:
    # The Code Sequence Macro first sits in Thing Series' optional sequences,
    # which the filter leaves out, so it is listed under Enhanced Thing.
    text = _markdown(
        iod_modules(_connection(tmp_path), name="Thing", types="1,1C", edition="2026d")
    )

    enhanced = text.index("### Enhanced Thing")
    assert text.index("| >Include Table 8.8-1 (Code Sequence Macro) |") > enhanced
    assert "(listed above)" not in text
    assert "### Code Sequence Macro: M (Table 8.8-1)\n\nListed above." in text


def test_iod_checklist_pages(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    connection.executemany(
        """
        INSERT INTO attribute_use (id, edition_id, owner_type, owner_id, row_kind,
          attribute_tag, attribute_name, type_designation, description_text,
          sequence_depth, row_order, source_ref_id)
        SELECT 'filler.' || ?, '2026d', 'module', id, 'attribute', '(0008,0008)',
               'Image Type', '1C', ?, 0, 100 + ?, source_ref_id
        FROM module WHERE name = 'Enhanced Thing'
        """,
        [(index, "Required if " + "x" * 400, index) for index in range(60)],
    )

    first = _markdown(
        iod_modules(connection, name="Thing", expand=True, edition="2026d")
    )
    assert 'Next: dicom_iod("Thing", expand=true, page=2).' in first
    second = _markdown(
        iod_modules(connection, name="Thing", expand=True, page=2, edition="2026d")
    )
    assert second.startswith("| Attribute | Tag | VR | VM | Type | Description |")


def test_element_lists_its_modules_and_iods(tmp_path: Path) -> None:
    text = _markdown(
        element_usage(_connection(tmp_path), name="modality", edition="2026d")
    )

    assert text.splitlines()[0] == "**(0008,0060) Modality** `Modality` · VR CS · VM 1"
    assert "| Thing Series Module | C.1, Table C.1-1 | 1 |  |" in text
    assert "| Worklist Module | C.3, Table C.3-1 |  |  |" in text
    assert "In IODs: Thing." in text


def test_element_in_an_iod_shows_nesting_and_macro(tmp_path: Path) -> None:
    text = _markdown(
        element_usage(
            _connection(tmp_path), name="(0008,0100)", iod="Thing", edition="2026d"
        )
    )

    assert "In the Thing IOD:" in text
    assert (
        "| Thing Series Module | M | 1C | Anatomic Region Sequence "
        "| Code Sequence Macro | The code.<br>Required if short. |"
    ) in text
    assert "| Series Type Code Sequence | Code Sequence Macro |" in text
    assert (
        "| Code Sequence Macro (functional group) | M | 1C |  |  "
        "| The code.<br>Required if short. |"
    ) in text
