"""Official DICOM Standard URL derivation helpers."""

from __future__ import annotations

from urllib.parse import quote

OFFICIAL_DICOM_BASE_URL = "https://dicom.nema.org/medical/dicom/"


def official_standard_ref_url(
    *,
    edition: str,
    part: str,
    anchor: str | None,
    base_url: str = OFFICIAL_DICOM_BASE_URL,
) -> str | None:
    """Return the official CHTML URL for a concrete part/anchor pair."""
    normalized_edition = edition.strip()
    normalized_part = part.strip().upper()
    normalized_anchor = anchor.strip() if anchor is not None else ""
    if not normalized_edition or not normalized_anchor:
        return None
    if not normalized_part.startswith("PS3."):
        return None
    part_suffix = normalized_part.removeprefix("PS3.")
    if not part_suffix.isdecimal():
        return None
    part_number = part_suffix.zfill(2)
    encoded_anchor = quote(normalized_anchor, safe="-._~")
    return (
        f"{base_url.rstrip('/')}/{normalized_edition}/output/chtml/"
        f"part{part_number}/{encoded_anchor}.html"
    )
