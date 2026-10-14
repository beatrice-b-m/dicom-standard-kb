from __future__ import annotations

import sqlite3
from pathlib import Path

from dicom_kb.build import gap_log_path
from dicom_kb.query.markdown import render_markdown
from dicom_kb.query.resolver import (
    attribute_values,
    code_lookup,
    element_usage,
    iod_modules,
    module_attributes,
    read_standard,
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

    little_endian = render_markdown(
        read_standard(connection, reference="1.2.840.10008.1.2.1", edition=edition)
    )
    big_endian = render_markdown(
        read_standard(connection, reference="ExplicitVRBigEndian", edition=edition)
    )

    assert little_endian.startswith("**1.2.840.10008.1.2.1** Explicit VR Little Endian")
    assert "| Explicit VR | Little Endian | Native | No |" in little_endian
    assert big_endian.startswith("**1.2.840.10008.1.2.2** Explicit VR Big Endian")
    assert "Retired: PS3.5" in big_endian


def test_real_kb_every_current_transfer_syntax_has_its_encoding(
    connection: sqlite3.Connection, edition: str
) -> None:
    # Phase 5's bar: VR style, byte order and Pixel Data encoding for every
    # transfer syntax PS3.5 still specifies, read from Annex A.
    missing = connection.execute(
        """
        SELECT uid.uid_value FROM uid_registry_entry uid
        LEFT JOIN transfer_syntax_detail ts
          ON ts.edition_id = uid.edition_id AND ts.uid_value = uid.uid_value
        WHERE uid.edition_id = ? AND uid.uid_type = 'Transfer Syntax'
          AND uid.retired = 0
          AND (ts.vr_encoding IS NULL OR ts.byte_order IS NULL
               OR ts.pixel_data IS NULL)
        """,
        (edition,),
    ).fetchall()
    facts = {
        row["uid_value"]: (row["vr_encoding"], row["byte_order"], row["pixel_data"])
        for row in connection.execute(
            "SELECT * FROM transfer_syntax_detail WHERE edition_id = ?", (edition,)
        )
    }

    assert [row["uid_value"] for row in missing] == []
    assert facts["1.2.840.10008.1.2"] == ("Implicit VR", "Little Endian", "Native")
    assert facts["1.2.840.10008.1.2.4.50"][2] == "Encapsulated"
    assert facts["1.2.840.10008.1.2.4.94"][2].startswith("Not in the Data Set")
    assert facts["1.2.840.10008.1.2.7.1"][:2] == ("Explicit VR", "Little Endian")


def test_real_kb_reads_every_vr(connection: sqlite3.Connection, edition: str) -> None:
    vrs = "AE AS AT CS DA DS DT FD FL IS LO LT OB OD OF OL OV OW PN SH SL SQ SS ST SV"
    for vr in [*vrs.split(), "TM", "UC", "UI", "UL", "UN", "UR", "US", "UT", "UV"]:
        text = render_markdown(read_standard(connection, reference=vr, edition=edition))
        assert text.startswith(f"**{vr}** "), text
        assert "**Explicit VR header:**" in text

    ob = render_markdown(read_standard(connection, reference="OB", edition=edition))
    us = render_markdown(read_standard(connection, reference="US", edition=edition))
    assert "2 reserved bytes (0000H), then a 32-bit Value Length" in ob
    assert "VR, then a 16-bit Value Length" in us


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
        module_attributes(
            connection, name="General Series", detail="full", edition=edition
        )
    )

    assert text.startswith("**General Series Module** (C.7.3.1, Table C.7-5a)")
    assert "(listed above)" in text
    assert len(text) < 20_000


def test_real_kb_module_outline_is_small(
    connection: sqlite3.Connection, edition: str
) -> None:
    text = render_markdown(
        module_attributes(connection, name="General Series", edition=edition)
    )

    assert "| Modality | (0008,0060) | CS | 1 | 1 |" in text
    assert "Person Identification Macro Attributes” (25 attributes) |" in text
    assert "| >>CodeValue |" not in text
    assert len(text) < 6_000


def test_real_kb_required_ct_checklist(
    connection: sqlite3.Connection, edition: str
) -> None:
    pages = []
    page = 1
    while True:
        response = iod_modules(
            connection, name="CT Image", types="1,1C", page=page, edition=edition
        )
        assert response.status == "ok"
        pages.append(render_markdown(response))
        if f"page={page + 1})" not in pages[-1]:
            break
        page += 1
    text = "\n".join(pages)

    for row in (
        "| StudyInstanceUID | (0020,000D) | UI | 1 | 1 |",
        "| SOPClassUID | (0008,0016) | UI | 1 | 1 |",
        "| RescaleType | (0028,1054) | LO | 1 | 1C | Required if",
    ):
        assert row in text
    # Type 2 and 3 rows, and the U modules, are named in the closing line only.
    assert "| PatientName |" not in text
    assert "### Clinical Trial Subject Module" not in text
    assert "Modules not shown: Clinical Trial Subject (U)" in text
    assert "sit inside sequences of other Types" in text
    assert len(text) < 30_000


def test_real_kb_range_tag_lookup_matches_the_range_row(
    connection: sqlite3.Connection, edition: str
) -> None:
    text = render_markdown(
        element_usage(connection, name="(6002,3000)", edition=edition)
    )

    assert text.startswith("**(60xx,3000) Overlay Data** `OverlayData`")


def test_real_kb_values_cover_sections_and_table_cells(
    connection: sqlite3.Connection, edition: str
) -> None:
    sex = render_markdown(
        attribute_values(connection, name="Patient's Sex", edition=edition)
    )
    source = render_markdown(
        attribute_values(connection, name="Respiratory Signal Source", edition=edition)
    )
    photometric = render_markdown(
        attribute_values(
            connection,
            name="Photometric Interpretation",
            within="CT Image",
            edition=edition,
        )
    )

    assert "| M | male |" in sex
    assert "| BELT |" in source
    assert "MONOCHROME2" in photometric


def test_real_kb_coded_attribute_names_its_context_group(
    connection: sqlite3.Connection, edition: str
) -> None:
    values = render_markdown(
        attribute_values(
            connection, name="Gender Identity Code Sequence", edition=edition
        )
    )
    group = render_markdown(code_lookup(connection, query="CID 7458", edition=edition))
    code = render_markdown(code_lookup(connection, query="121071", edition=edition))

    assert "BCID 7458" in values
    assert group.startswith("**CID 7458 Person Gender Identity**")
    assert "Definition: An observation found on an imaging study." in code


def _count(connection: sqlite3.Connection, table: str, edition: str) -> int:
    row = connection.execute(
        f"SELECT COUNT(*) AS count FROM {table} WHERE edition_id = ?",
        (edition,),
    ).fetchone()
    return int(row["count"])
