from dicom_kb import LEGAL_NOTICE


def test_package_metadata_exports_notice() -> None:
    assert "not affiliated with, sponsored by, or endorsed by NEMA" in LEGAL_NOTICE
    assert "does not provide official DICOM conformance certification" in LEGAL_NOTICE
