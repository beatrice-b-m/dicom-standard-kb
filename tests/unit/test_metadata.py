from pathlib import Path

from dicom_kb import LEGAL_NOTICE, __version__


def test_package_metadata_exports_notice() -> None:
    assert __version__ == "0.1.0"
    assert "not affiliated with, sponsored by, or endorsed by NEMA" in LEGAL_NOTICE
    assert "does not provide official DICOM conformance certification" in LEGAL_NOTICE


def test_ps316_terminology_distribution_policy_is_documented() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    legal = (repo_root / "docs" / "legal.md").read_text(encoding="utf-8")
    distribution = (
        repo_root / "docs" / "public_distribution_policy.md"
    ).read_text(encoding="utf-8")
    notices = (repo_root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    for text in (legal, distribution, notices):
        assert "PS3.16" in text
        assert "terminology" in text

    assert "standalone terminology" in legal
    assert "bulk context-group/code exports" in distribution
    assert "does not vendor" in notices


def test_attribute_value_term_coverage_audit_is_documented() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    architecture = (repo_root / "docs" / "architecture.md").read_text(
        encoding="utf-8"
    )
    architecture_words = " ".join(architecture.split())

    assert "attribute_value_term" in architecture
    assert "Enumerated Values" in architecture
    assert "Defined Terms" in architecture
    assert "term_kind" in architecture
    assert "data_element" in architecture
    assert "attribute_use" in architecture
    assert "PS3.3 module names" in architecture
    assert "PS3.3 macro names" in architecture
    assert "PS3.3 IOD names or keywords" in architecture
    assert "PS3.4 SOP Class names, keywords, or UIDs" in architecture
    assert "returns candidates rather than merging" in architecture
    assert (
        "TID, CID, and DICOMweb contexts are not attribute-use contexts"
        in architecture_words
    )


def test_architecture_documents_v2_entities() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    architecture = (repo_root / "docs" / "architecture.md").read_text(
        encoding="utf-8"
    )
    architecture_words = " ".join(architecture.split())

    for entity in (
        "vr_definition",
        "transfer_syntax_detail",
        "file_meta_requirement",
        "dicom_media_type",
        "dicomweb_transaction",
        "sr_template",
        "sr_template_row",
        "context_group",
        "context_group_row",
        "coded_concept",
    ):
        assert entity in architecture

    assert "edition_id" in architecture
    assert "source_ref_id" in architecture
    assert "standalone terminology export" in architecture
    assert "ambiguous route matches return candidates" in architecture_words


def test_phase8_eval_harness_progress_is_recorded() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    progress = (repo_root / "IMPLEMENTATION_PROGRESS.md").read_text(
        encoding="utf-8"
    )

    assert (
        "| Phase 7 - Selected PS3.7/PS3.8 semantics | Complete |" in progress
    )
    assert (
        "| 5 | Fallback text retrieval covers prose-only rules. | Complete |"
        in progress
    )
    assert (
        "| d1615de | Added the first focused v2 public-tool prompt batch"
        in progress
    )
    assert (
        "| b5ee0e2 | Added the second focused v2 prompt batch"
        in progress
    )
    assert "| Phase 8 - Evaluation harness expansion | Complete |" in progress
    assert (
        "| 6 | At least 100 coding-task regression prompts pass through "
        "deterministic tool calls before answer synthesis. | Complete |"
        in progress
    )
    assert "`docs/release_checklist.md`" in progress
    assert "101 prompt cases" in progress
    assert "Unsupported normative claim checks cover v2 topics." in progress
    assert "final Phase 8 v2 workflow prompt batch" in progress


def test_v2_public_docs_cover_build_and_tool_surfaces() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    agent_tools = (repo_root / "docs" / "agent_tools.md").read_text(
        encoding="utf-8"
    )

    for part in (
        "PS3.5",
        "PS3.7",
        "PS3.8",
        "PS3.10",
        "PS3.16",
        "PS3.18",
    ):
        assert part in readme

    for command in (
        "dicom-kb lookup vr <vr>",
        "dicom-kb lookup transfer-syntax <uid-or-keyword>",
        "dicom-kb explain encoding <topic>",
        "dicom-kb lookup dicomweb <name-or-route>",
        "dicom-kb lookup media-type <media-type-or-context>",
        "dicom-kb lookup sr-template <tid-or-name>",
        "dicom-kb lookup context-group <cid-or-name>",
        "dicom-kb lookup code <code-value> [--scheme <scheme>]",
    ):
        assert command in agent_tools

    for tool in (
        "dicom_lookup_vr",
        "dicom_lookup_transfer_syntax",
        "dicom_explain_encoding_rule",
        "dicom_lookup_dicomweb_transaction",
        "dicom_lookup_media_type",
        "dicom_lookup_sr_template",
        "dicom_lookup_context_group",
        "dicom_lookup_code_meaning",
    ):
        assert tool in readme
        assert tool in agent_tools
