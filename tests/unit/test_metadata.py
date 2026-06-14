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
