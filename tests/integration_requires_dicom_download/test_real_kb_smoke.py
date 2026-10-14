from __future__ import annotations

import sqlite3
from pathlib import Path

from dicom_kb.build import gap_log_path
from dicom_kb.query.markdown import render_markdown
from dicom_kb.query.resolver import (
    element_usage,
    iod_modules,
    lookup_uid,
    module_attributes,
)
from dicom_kb.sources.manifest import SourceManifest


def test_real_build_outputs_exist(
    db_path: Path, edition: str, manifest: SourceManifest
) -> None:
    assert db_path.exists()
    assert gap_log_path(db_path).exists()
    assert manifest.edition == edition
    assert len(manifest.artifacts) >= 3


def test_real_kb_sanity_counts(connection: sqlite3.Connection, edition: str) -> None:
    assert _count(connection, "data_element", edition) > 4000
    assert _count(connection, "uid_registry_entry", edition) > 400
    assert _count(connection, "iod", edition) > 100
    assert _count(connection, "module", edition) > 200


def test_real_kb_resolves_well_known_data_elements_and_uids(
    connection: sqlite3.Connection, edition: str
) -> None:
    modality = render_markdown(
        element_usage(connection, name="(0008,0060)", edition=edition)
    )
    assert modality.startswith("**(0008,0060) Modality** `Modality` · VR CS · VM 1")
    assert "| CT Series Module | C.8.15.1, Table C.8-113 | 1 |  |" in modality

    little_endian = lookup_uid(
        connection, uid_or_keyword="1.2.840.10008.1.2.1", edition=edition
    )
    assert little_endian.status == "ok"
    assert little_endian.result is not None
    assert little_endian.result["uid_name"] == "Explicit VR Little Endian"
    assert little_endian.result["retired"] is False

    big_endian = lookup_uid(
        connection, uid_or_keyword="1.2.840.10008.1.2.2", edition=edition
    )
    assert big_endian.status == "ok"
    assert big_endian.result is not None
    assert big_endian.result["uid_name"] == "Explicit VR Big Endian"
    assert big_endian.result["retired"] is True


def test_real_kb_resolves_ct_modules_from_the_sop_class(
    connection: sqlite3.Connection, edition: str
) -> None:
    text = render_markdown(
        iod_modules(connection, name="1.2.840.10008.5.1.4.1.1.2", edition=edition)
    )

    assert text.startswith("**CT Image IOD**")
    assert "SOP Class: CT Image Storage `1.2.840.10008.5.1.4.1.1.2`" in text
    assert "| Patient | Patient | C.7.1.1, Table C.7-1 | M |" in text
    assert "|  | Contrast/Bolus | C.7.6.4, Table C.7-12 | C: " in text


def test_real_kb_links_every_sop_class_to_an_iod(
    connection: sqlite3.Connection, edition: str
) -> None:
    unlinked = connection.execute(
        """
        SELECT name FROM sop_class
        WHERE edition_id = ?
          AND id NOT IN (SELECT sop_class_id FROM sop_class_iod)
        """,
        (edition,),
    ).fetchall()

    assert [row["name"] for row in unlinked] == []


def test_real_kb_iod_modules_all_have_attributes(
    connection: sqlite3.Connection, edition: str
) -> None:
    empty = connection.execute(
        """
        SELECT DISTINCT module.name FROM iod_module_use
        JOIN module ON module.id = iod_module_use.module_id
        WHERE iod_module_use.edition_id = ?
          AND module.id NOT IN (SELECT owner_id FROM attribute_use)
        """,
        (edition,),
    ).fetchall()
    unresolved = connection.execute(
        """
        SELECT COUNT(*) AS count FROM attribute_use
        WHERE edition_id = ? AND row_kind = 'include'
          AND included_macro_id IS NULL
        """,
        (edition,),
    ).fetchone()

    assert [row["name"] for row in empty] == []
    assert unresolved["count"] == 0


def test_real_kb_expands_each_macro_once(
    connection: sqlite3.Connection, edition: str
) -> None:
    # The Code Sequence macros include one another; expanding every include
    # made General Series 205 KB.
    text = render_markdown(
        module_attributes(connection, name="General Series", edition=edition)
    )

    assert text.startswith("**General Series Module** (C.7.3.1, Table C.7-5a)")
    assert "(listed above)" in text
    assert len(text) < 20_000


def test_real_kb_range_tag_lookup_matches_the_range_row(
    connection: sqlite3.Connection, edition: str
) -> None:
    text = render_markdown(
        element_usage(connection, name="(6002,3000)", edition=edition)
    )

    assert text.startswith("**(60xx,3000) Overlay Data** `OverlayData`")


def _count(connection: sqlite3.Connection, table: str, edition: str) -> int:
    row = connection.execute(
        f"SELECT COUNT(*) AS count FROM {table} WHERE edition_id = ?",
        (edition,),
    ).fetchone()
    return int(row["count"])
