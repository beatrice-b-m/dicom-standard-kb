from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from dicom_kb.build import gap_log_path
from dicom_kb.db.repositories._rows import _doc_node_from_row
from dicom_kb.query.markdown import render_markdown
from dicom_kb.query.resolver import (
    module_attributes,
    read_standard,
    search_standard,
)
from dicom_kb.query.resolver.standard import _reference

# A handful of references in the published source point at ids no part
# defines; anything more means the renderer lost track of a target.
MAX_UNRESOLVED_REFERENCES = 10


def test_real_kb_resolves_almost_every_reference(db_path: Path) -> None:
    gaps = gap_log_path(db_path).read_text(encoding="utf-8").splitlines()
    unresolved = [line for line in gaps if "has no target" in line]

    assert len(unresolved) <= MAX_UNRESOLVED_REFERENCES, unresolved


def test_real_kb_text_keeps_reference_targets(
    connection: sqlite3.Connection, edition: str
) -> None:
    holes = connection.execute(
        """
        SELECT count(*) FROM attribute_use
        WHERE edition_id = ? AND (description_text LIKE '%See .%'
            OR description_text LIKE '%see  %')
        """,
        (edition,),
    ).fetchone()[0]
    assert holes == 0

    series = render_markdown(
        module_attributes(connection, name="General Series", edition=edition)
    )
    assert re.search(r"See Section C\.[\d.]+ for Defined Terms\.", series)


def test_real_kb_reads_sequence_delimitation_in_one_page(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = read_standard(connection, reference="PS3.5 7.5.2", edition=edition)
    markdown = render_markdown(response)

    assert response.status == "ok"
    assert markdown.startswith("## Section 7.5.2 Delimitation of The Sequence")
    assert "(FFFE,E0DD)" in markdown
    assert "Page 1 of" not in markdown


def test_real_kb_search_ranks_the_normative_section_first(
    connection: sqlite3.Connection, edition: str
) -> None:
    response = search_standard(
        connection, query="undefined length sequence delimitation", edition=edition
    )

    assert response.status == "ok"
    assert response.result["hits"][0]["Ref"] == "PS3.5 Section 7.5.2"


def test_real_kb_reads_every_ps35_node_and_every_chapter_by_its_ref(
    connection: sqlite3.Connection, edition: str
) -> None:
    rows = connection.execute(
        """
        SELECT dn.*, sr.part source_part, sr.section source_section,
               sr.table_id source_table_id, sr.xml_id source_xml_id,
               sr.title source_title, sr.canonical_url source_url
        FROM doc_node dn JOIN source_ref sr ON sr.id = dn.source_ref_id
        WHERE dn.edition_id = ? AND (dn.node_type = 'chapter' OR (dn.part = 'PS3.5'
            AND (dn.node_type = 'section' OR dn.xml_id IS NOT NULL)))
        """,
        (edition,),
    ).fetchall()
    failures = []
    for row in rows:
        ref = _reference(_doc_node_from_row(row))
        response = read_standard(connection, reference=ref, edition=edition)
        if response.status != "ok" or "[[table:" in response.result["markdown"]:
            failures.append(ref)

    assert len(rows) > 500
    assert failures == []
