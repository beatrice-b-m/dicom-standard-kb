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

    assert "attribute_value_term" in architecture
    assert "Enumerated Values" in architecture
    assert "Defined Terms" in architecture
    assert "term_kind" in architecture
    assert "data_element" in architecture
    assert "attribute_use" in architecture
    assert "module or macro names" in architecture
    assert "IOD, SOP Class, TID, CID, and DICOMweb" in architecture
    assert "contexts are not yet resolved" in architecture


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
    assert (
        "| Next recommended action | Start Phase 9 by updating user-facing docs"
        in progress
    )
    assert "101 prompt cases" in progress
    assert "Unsupported normative claim checks cover v2 topics." in progress
    assert "final Phase 8 v2 workflow prompt batch" in progress
