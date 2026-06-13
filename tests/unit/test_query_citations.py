from dicom_kb.ir.models import SourceRef
from dicom_kb.query.answer_contracts import StandardRef
from dicom_kb.query.citations import CitationBuilder, citation_refs


def test_citation_builder_flattens_groups_and_deduplicates_refs() -> None:
    source = SourceRef(
        id="2026b.PS3.3.table_A.3-1",
        edition_id="2026b",
        part="PS3.3",
        section="sect_A.3",
        table_id="table_A.3-1",
        xml_id="table_A.3-1",
        title="CT Image IOD Modules",
        canonical_url=None,
    )
    registry_ref = StandardRef(
        part="PS3.6",
        section="Registry of DICOM Data Elements",
        table="Registry of DICOM Data Elements",
        anchor="sect_6",
        official_url=None,
        edition="2026b",
    )

    builder = (
        CitationBuilder()
        .add_group("iod", (source, None))
        .add_group("attribute", (registry_ref, source))
    )

    assert [group.label for group in builder.groups()] == ["iod", "attribute"]
    assert builder.refs() == [
        StandardRef(
            part="PS3.3",
            section="sect_A.3",
            table="CT Image IOD Modules",
            anchor="table_A.3-1",
            official_url=None,
            edition="2026b",
        ),
        registry_ref,
    ]


def test_citation_refs_accepts_mixed_evidence_groups() -> None:
    module_ref = SourceRef(
        id="2026b.PS3.3.table_C.7-1",
        edition_id="2026b",
        part="PS3.3",
        section="sect_C.7.1.1",
        table_id="table_C.7-1",
        xml_id="table_C.7-1",
        title="Patient Module Attributes",
        canonical_url=None,
    )
    uid_ref = StandardRef(
        part="PS3.6",
        section=None,
        table="UID Values",
        anchor="uid_table",
        official_url=None,
        edition="2026b",
    )

    refs = citation_refs((module_ref,), (uid_ref, None, module_ref))

    assert [ref.part for ref in refs] == ["PS3.3", "PS3.6"]
    assert refs[0].table == "Patient Module Attributes"
