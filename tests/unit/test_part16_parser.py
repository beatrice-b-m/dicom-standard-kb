from __future__ import annotations

import sqlite3
from pathlib import Path

from dicom_kb.db.importers import (
    import_coded_concepts,
    import_context_groups,
    import_sr_templates,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part16_content_mapping import Part16ParseResult, parse_part16
from tests.fixtures_synthetic import EDITION, PS316_CONTENT_MAPPING_DOCBOOK

NS = (
    'xmlns="http://docbook.org/ns/docbook" '
    'xmlns:xml="http://www.w3.org/XML/1998/namespace"'
)


def _parse(xml: str = PS316_CONTENT_MAPPING_DOCBOOK) -> Part16ParseResult:
    return parse_part16(parse_docbook_xml(xml, part="PS3.16"), edition=EDITION)


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    return connection


def _cid_table(xml_id: str | None, rows: str) -> str:
    id_attribute = f'xml:id="{xml_id}"' if xml_id else ""
    return f"""
    <table {id_attribute}><caption>Acquisition Modality</caption>
      <tgroup cols="3">
        <thead><row><entry>Coding Scheme Designator</entry>
          <entry>Code Value</entry><entry>Code Meaning</entry></row></thead>
        <tbody>{rows}</tbody>
      </tgroup>
    </table>"""


def _cid_section(*tables: str) -> str:
    return f"""<book {NS} xml:id="PS3.16"><chapter xml:id="chapter_CID">
      <section xml:id="sect_CID_29"><title>Acquisition Modality</title>
        <para>Type: Extensible</para>{"".join(tables)}
      </section></chapter></book>"""


def _code_row(value: str, meaning: str) -> str:
    return (
        f"<row><entry>DCM</entry><entry>{value}</entry><entry>{meaning}</entry></row>"
    )


def test_parse_part16_reads_template_and_context_group_tables() -> None:
    result = _parse()

    assert [(t.tid, t.name, t.extensibility) for t in result.sr_templates] == [
        ("TID 1500", "Measurement Report", "Extensible")
    ]
    assert [
        (
            row.row_order,
            row.relationship_type,
            row.value_type,
            row.concept_name,
            row.cardinality,
            row.include_tid,
        )
        for row in result.sr_template_rows
    ] == [
        (1, None, "CONTAINER", "DCID 7021", "1", None),
        (2, "> HAS OBS CONTEXT", "INCLUDE", "DTID 1001", "1", "TID 1001"),
        (3, "> CONTAINS", "INCLUDE", "DTID 1501", "1-n", "TID 1501"),
        (4, "> CONTAINS", "TEXT", None, "0-1", None),
    ]
    assert [
        (g.cid, g.name, g.extensibility, g.version) for g in result.context_groups
    ] == [("CID 29", "Acquisition Modality", "Extensible", "20231115")]
    assert [
        (
            row.coding_scheme_designator,
            row.code_value,
            row.code_meaning,
            row.include_cid,
        )
        for row in result.context_group_rows
    ] == [
        ("DCM", "CT", "Computed Tomography", None),
        (None, None, None, "CID 34"),
    ]
    assert [
        (c.code_value, c.coding_scheme_designator, c.code_meaning)
        for c in result.coded_concepts
    ] == [("CT", "DCM", "Computed Tomography")]


def test_code_row_that_mentions_a_cid_stays_a_code() -> None:
    xml = _cid_section(
        _cid_table("table_CID_29", _code_row("X1", "Modality listed in CID 30"))
    )

    (row,) = _parse(xml).context_group_rows

    assert row.code_value == "X1"
    assert row.include_cid is None


def test_group_split_over_two_tables_keeps_counting_rows() -> None:
    xml = _cid_section(
        _cid_table("table_CID_29", _code_row("CT", "Computed Tomography")),
        # A continuation table often has no id of its own.
        _cid_table(None, _code_row("MR", "Magnetic Resonance")),
    )

    result = _parse(xml)

    assert [row.row_order for row in result.context_group_rows] == [1, 2]
    assert len({row.id for row in result.context_group_rows}) == 2
    assert len(result.context_groups) == 1


def test_dcm_definitions_are_found_by_their_columns() -> None:
    xml = f"""<book {NS} xml:id="PS3.16"><appendix xml:id="chapter_D">
      <title>DICOM Controlled Terminology Definitions</title>
      <table xml:id="table_renumbered"><caption>DCM definitions</caption>
        <tgroup cols="4">
          <thead><row><entry>Code Value</entry><entry>Code Meaning</entry>
            <entry>Definition</entry><entry>Notes</entry></row></thead>
          <tbody><row><entry>121071</entry><entry>Finding</entry>
            <entry>Something seen.</entry><entry></entry></row></tbody>
        </tgroup>
      </table></appendix></book>"""

    (concept,) = _parse(xml).coded_concepts

    assert (concept.code_value, concept.coding_scheme_designator) == (
        "121071",
        "DCM",
    )
    assert concept.definition == "Something seen."


def test_import_part16_records_keep_their_source_tables(tmp_path: Path) -> None:
    connection = _connection(tmp_path)
    parsed = _parse()

    templates = import_sr_templates(
        connection,
        edition=EDITION,
        templates=parsed.sr_templates,
        rows=parsed.sr_template_rows,
    )
    groups = import_context_groups(
        connection,
        edition=EDITION,
        context_groups=parsed.context_groups,
        rows=parsed.context_group_rows,
    )
    concepts = import_coded_concepts(
        connection, edition=EDITION, coded_concepts=parsed.coded_concepts
    )

    assert (templates.sr_templates, templates.sr_template_rows) == (1, 4)
    assert (groups.context_groups, groups.context_group_rows) == (1, 2)
    assert concepts.coded_concepts == 1
    tables = connection.execute(
        """
        SELECT DISTINCT ref.table_id FROM source_ref ref
        WHERE ref.id IN (
            SELECT source_ref_id FROM sr_template_row
            UNION SELECT source_ref_id FROM context_group_row
            UNION SELECT source_ref_id FROM coded_concept
        )
        ORDER BY ref.table_id
        """
    ).fetchall()
    assert [row["table_id"] for row in tables] == ["table_CID_29", "table_TID_1500"]
