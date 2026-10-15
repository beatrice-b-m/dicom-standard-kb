from __future__ import annotations

from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part05_encoding import (
    ENCAPSULATED,
    NATIVE,
    RTV_FLOW,
    TransferSyntaxUID,
    parse_transfer_syntaxes,
)
from tests.fixtures_synthetic import EDITION, PS35_ENCODING_DOCBOOK

_UIDS = (
    TransferSyntaxUID("1.2.840.10008.1.2", retired=False),
    TransferSyntaxUID("1.2.840.10008.1.2.1", retired=False),
    TransferSyntaxUID("1.2.840.10008.1.2.1.99", retired=False),
    TransferSyntaxUID("1.2.840.10008.1.2.2", retired=True),
    TransferSyntaxUID("1.2.840.10008.1.2.4.50", retired=False),
)

_RTV_PS35 = """<book xmlns="http://docbook.org/ns/docbook"
  xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <chapter xml:id="chapter_A" label="A"><title>Transfer Syntaxes</title>
    <section xml:id="sect_A.8" label="A.8">
      <title>SMPTE ST 2110-20 Uncompressed Progressive Active Video</title>
      <para>This Transfer Syntax is used in a DICOM-RTV Metadata Flow in order to
      describe the accompanying Video Flow.</para>
      <para>It shall be identified by a UID of 1.2.840.10008.1.2.7.1.</para>
    </section>
  </chapter>
</book>"""

_RTV_PS322 = """<book xmlns="http://docbook.org/ns/docbook"
  xmlns:xml="http://www.w3.org/XML/1998/namespace">
  <chapter xml:id="chapter_7" label="7"><title>Metadata</title>
    <section xml:id="sect_7.1" label="7.1"><title>Transfer Syntax UID</title>
      <para>This Transfer Syntax does not apply to the RTV Metadata which is
      encoded using the Explicit VR Little Endian Transfer Syntax.</para>
    </section>
  </chapter>
</book>"""


def _parse() -> dict[str, tuple[str, str, str, str | None, str]]:
    result = parse_transfer_syntaxes(
        parse_docbook_xml(PS35_ENCODING_DOCBOOK, part="PS3.5"),
        edition=EDITION,
        transfer_syntaxes=_UIDS,
    )
    assert result.warnings == ()
    return {
        detail.uid_value: (
            detail.vr_encoding,
            detail.byte_order,
            detail.pixel_data,
            detail.deflate,
            detail.section_xml_id,
        )
        for detail in result.details
    }


def test_reads_vr_and_byte_order_from_the_defining_section() -> None:
    facts = _parse()

    assert facts["1.2.840.10008.1.2"] == (
        "Implicit VR",
        "Little Endian",
        NATIVE,
        None,
        "sect_A.1",
    )
    assert facts["1.2.840.10008.1.2.1"][:3] == ("Explicit VR", "Little Endian", NATIVE)


def test_encapsulated_syntaxes_inherit_the_annex_a4_rules() -> None:
    # A.4.1 names the UID only in its table; A.4 sets VR, byte order and
    # the Encapsulated Format, and a note naming another UID is ignored.
    assert _parse()["1.2.840.10008.1.2.4.50"] == (
        "Explicit VR",
        "Little Endian",
        ENCAPSULATED,
        None,
        "sect_A.4.1",
    )


def test_deflated_syntax_builds_on_the_section_it_names() -> None:
    assert _parse()["1.2.840.10008.1.2.1.99"] == (
        "Explicit VR",
        "Little Endian",
        NATIVE,
        "Whole Data Set",
        "sect_A.5",
    )


def test_retired_syntax_without_a_section_is_skipped_silently() -> None:
    assert "1.2.840.10008.1.2.2" not in _parse()


def test_current_syntax_without_a_section_is_a_warning() -> None:
    result = parse_transfer_syntaxes(
        parse_docbook_xml(PS35_ENCODING_DOCBOOK, part="PS3.5"),
        edition=EDITION,
        transfer_syntaxes=[TransferSyntaxUID("1.2.840.10008.1.2.9", retired=False)],
    )

    assert result.details == ()
    assert [w.message for w in result.warnings] == [
        "no Annex A section defines 1.2.840.10008.1.2.9"
    ]


def test_rtv_syntax_takes_the_metadata_encoding_from_ps322() -> None:
    uids = [TransferSyntaxUID("1.2.840.10008.1.2.7.1", retired=False)]
    document = parse_docbook_xml(_RTV_PS35, part="PS3.5")

    without = parse_transfer_syntaxes(document, edition=EDITION, transfer_syntaxes=uids)
    with_ps322 = parse_transfer_syntaxes(
        document,
        edition=EDITION,
        transfer_syntaxes=uids,
        rtv_document=parse_docbook_xml(_RTV_PS322, part="PS3.22"),
    )

    assert without.details == ()
    assert "gives no VR, byte order" in without.warnings[0].message
    (detail,) = with_ps322.details
    assert (detail.vr_encoding, detail.byte_order, detail.pixel_data) == (
        "Explicit VR",
        "Little Endian",
        RTV_FLOW,
    )
