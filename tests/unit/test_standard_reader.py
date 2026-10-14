from __future__ import annotations

import sqlite3
from pathlib import Path

from lxml import etree

from dicom_kb.db.importers import import_docbook_structure
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.docbook.targets import TargetIndex
from dicom_kb.query.markdown import render_markdown
from dicom_kb.query.resolver import read_standard, search_standard
from dicom_kb.query.resolver.standard import paginate
from tests.fixtures_synthetic import EDITION

NS = (
    'xmlns="http://docbook.org/ns/docbook" '
    'xmlns:xml="http://www.w3.org/XML/1998/namespace"'
)


def _rows(count: int) -> str:
    return "".join(
        f"<tr><td>({index:04X},0010)</td><td>Element number {index} with a "
        f"long enough name to fill the page</td></tr>"
        for index in range(count)
    )


PS35 = f"""\
<book {NS} xml:id="PS3.5">
  <chapter label="7" xml:id="chapter_7"><title>The Data Set</title>
    <section label="7.5" xml:id="sect_7.5"><title>Nesting of Data Sets</title>
      <para>Items nest.</para>
      <section label="7.5.2" xml:id="sect_7.5.2">
        <title>Delimitation of The Sequence of Items</title>
        <para>A Sequence Delimitation Item shall be included after the last
          Item of a sequence of undefined length. See
          <xref linkend="table_7.5-1" xrefstyle="select: label"/>.</para>
        <table label="7.5-1" xml:id="table_7.5-1">
          <caption>Sequence of Undefined Length</caption>
          <thead><tr><th>Tag</th><th>Meaning</th></tr></thead>
          <tbody><tr><td>(FFFE,E0DD)</td><td>Sequence Delimitation Item</td>
          </tr></tbody>
        </table>
      </section>
    </section>
  </chapter>
  <chapter label="D" xml:id="chapter_D">
    <title>Examples of Encoding (Informative)</title>
    <section label="D.1" xml:id="sect_D.1"><title>Delimitation example</title>
      <para>An undefined length sequence ends with a delimitation item.</para>
    </section>
  </chapter>
  <chapter label="E" xml:id="chapter_E"><title>Large Registry</title>
    <table label="E-1" xml:id="table_E-1"><caption>Registry</caption>
      <thead><tr><th>Tag</th><th>Name</th></tr></thead>
      <tbody>{_rows(400)}</tbody>
    </table>
  </chapter>
</book>
"""

PS37 = f"""\
<book {NS} xml:id="PS3.7">
  <chapter label="7" xml:id="chapter_7"><title>DIMSE</title>
    <section label="7.5" xml:id="sect_7.5"><title>Services</title>
      <section label="7.5.2" xml:id="sect_7.5.2"><title>DIMSE-N Services</title>
        <para>Normalized operations.</para>
      </section>
    </section>
  </chapter>
</book>
"""

PS316 = f"""\
<book {NS} xml:id="PS3.16">
  <chapter label="B" xml:id="chapter_B"><title>Context Groups</title>
    <section label="CID 7010" xml:id="sect_CID_7010">
      <title>Key Object Selection Document Title</title>
      <table label="CID 7010" xml:id="table_CID_7010">
        <caption>Key Object Selection Document Title</caption>
        <thead><tr><th>Code Value</th><th>Code Meaning</th></tr></thead>
        <tbody><tr><td>113000</td><td>Of Interest</td></tr></tbody>
      </table>
    </section>
  </chapter>
  <chapter label="A" xml:id="chapter_A"><title>Templates</title>
    <section label="TID 300" xml:id="sect_TID_300"><title>Measurement</title>
      <table label="TID 300" xml:id="table_TID_300_Parameters">
        <caption>Parameters</caption>
        <tbody><tr><td>$Measurement</td><td>Coded term</td></tr></tbody>
      </table>
      <table label="TID 300" xml:id="table_TID_300">
        <caption>Measurement</caption>
        <tbody><tr><td>NUM</td><td>$Measurement</td></tr></tbody>
      </table>
    </section>
  </chapter>
  <section><title>Annexes</title>
    <para>Template annexes follow.</para>
  </section>
</book>
"""


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    sources = {"PS3.5": PS35, "PS3.7": PS37, "PS3.16": PS316}
    targets = TargetIndex()
    for part, xml in sources.items():
        targets.add_document(etree.fromstring(xml.encode()), part=part)
    for part, xml in sources.items():
        import_docbook_structure(
            connection,
            edition=EDITION,
            document=parse_docbook_xml(xml, part=part, targets=targets),
        )
    return connection


def _read(connection: sqlite3.Connection, ref: str, page: int = 1) -> str:
    return render_markdown(
        read_standard(connection, reference=ref, edition=EDITION, page=page)
    )


def test_read_section_includes_tables_and_subsections_that_fit(
    tmp_path: Path,
) -> None:
    markdown = _read(_connection(tmp_path), "PS3.5 7.5")

    assert markdown == (
        "## Section 7.5 Nesting of Data Sets\n\n"
        "Items nest.\n\n"
        "### Section 7.5.2 Delimitation of The Sequence of Items\n\n"
        "A Sequence Delimitation Item shall be included after the last Item of "
        "a sequence of undefined length. See Table 7.5-1.\n\n"
        "**Table 7.5-1: Sequence of Undefined Length**\n"
        "| Tag | Meaning |\n|---|---|\n"
        "| (FFFE,E0DD) | Sequence Delimitation Item |\n\n"
        f"Source: PS3.5 Section 7.5 ({EDITION})\n"
    )


def test_read_accepts_the_ways_references_are_written(tmp_path: Path) -> None:
    connection = _connection(tmp_path)

    for ref in ("Table 7.5-1", "PS3.5 Table 7.5-1", "ps3.5 7.5-1", "table_7.5-1"):
        assert _read(connection, ref).startswith(
            "**Table 7.5-1: Sequence of Undefined Length**"
        ), ref
    assert _read(connection, "cid7010").startswith(
        "## CID 7010 Key Object Selection Document Title"
    )
    assert _read(connection, "PS3.5 Annex D").startswith(
        "## Annex D Examples of Encoding (Informative)"
    )
    assert "- PS3.5 Section 7 The Data Set" in _read(connection, "PS3.5")


def test_read_asks_for_a_part_when_a_label_repeats(tmp_path: Path) -> None:
    markdown = _read(_connection(tmp_path), "7.5.2")

    assert markdown.splitlines()[0] == (
        "Section 7.5.2 is in several parts; name one, e.g. `PS3.5 Section 7.5.2`."
    )
    assert "| PS3.7 Section 7.5.2 | DIMSE-N Services |" in markdown


def test_read_not_found_points_at_the_nearest_section(tmp_path: Path) -> None:
    markdown = _read(_connection(tmp_path), "PS3.5 7.5.2.9")

    assert markdown.startswith("No Section 7.5.2.9 in PS3.5.")
    assert "| PS3.5 Section 7.5.2 | Delimitation of The Sequence of Items |" in (
        markdown
    )


def test_read_pages_a_long_table_and_repeats_its_header(tmp_path: Path) -> None:
    connection = _connection(tmp_path)

    first = _read(connection, "PS3.5 Table E-1")
    second = _read(connection, "PS3.5 Table E-1", page=2)

    assert first.startswith("**Table E-1: Registry**\n| Tag | Name |\n|---|---|\n")
    assert 'Next: dicom_read("PS3.5 Table E-1", page=2).' in first
    assert second.startswith("**Table E-1: Registry**\n| Tag | Name |\n|---|---|\n")
    assert len(first) < 17_000
    pages = int(first.split("Page 1 of ")[1].split(".")[0])
    rows = [
        line
        for page in range(1, pages + 1)
        for line in _read(connection, "PS3.5 Table E-1", page=page).splitlines()
        if line.startswith("| (")
    ]
    assert len(rows) == 400
    assert "has " in _read(connection, "PS3.5 Table E-1", page=pages + 1)


def test_search_ranks_normative_text_before_informative(tmp_path: Path) -> None:
    markdown = render_markdown(
        search_standard(
            _connection(tmp_path),
            query="undefined length delimitation",
            edition=EDITION,
        )
    )
    lines = markdown.splitlines()

    assert lines[0] == "| Ref | Title | Context |"
    refs = [line.split(" | ")[0].removeprefix("| ") for line in lines[2:5]]
    assert refs == [
        "PS3.5 Table 7.5-1",
        "PS3.5 Section 7.5.2",
        "PS3.5 Section D.1 (informative)",
    ]
    assert lines[-1].startswith("Source: PS3.5")


def test_search_falls_back_to_any_word_and_filters_by_part(tmp_path: Path) -> None:
    connection = _connection(tmp_path)

    markdown = render_markdown(
        search_standard(connection, query="normalized zebra", edition=EDITION)
    )
    assert markdown.startswith(
        "No section or table contains every word; closest matches:"
    )
    assert "| PS3.7 Section 7.5.2 | DIMSE-N Services |" in markdown

    filtered = search_standard(
        connection, query="delimitation", edition=EDITION, part="PS3.7"
    )
    assert filtered.status == "not_found"
    invalid = search_standard(connection, query="x", edition=EDITION, part="3.7x")
    assert invalid.status == "validation_error"


def test_paginate_splits_only_between_blocks_and_rows() -> None:
    text = "\n\n".join(f"paragraph {index} " + "x" * 50 for index in range(10))

    pages = paginate(text, page_chars=200)

    assert all(len(page) <= 200 for page in pages)
    assert "\n\n".join(pages) == text


def test_read_picks_the_node_whose_id_spells_a_repeated_label(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)

    assert _read(connection, "Table TID 300").startswith(
        "**Table TID 300: Measurement**"
    )
    # The parameter table shares the label, so its handle is its id.
    parameters = _read(connection, "PS3.16 table_TID_300_Parameters")
    assert parameters.startswith("**Table TID 300: Parameters**")
    assert f"Source: PS3.16 table_TID_300_Parameters ({EDITION})" in parameters


def test_read_falls_back_to_an_exact_title(tmp_path: Path) -> None:
    connection = _connection(tmp_path)

    assert _read(connection, "PS3.16 Annexes").startswith(
        "## Annexes\n\nTemplate annexes follow."
    )
    assert _read(connection, "PS3.5 Nesting of Data Sets").startswith(
        "## Section 7.5 Nesting of Data Sets"
    )
