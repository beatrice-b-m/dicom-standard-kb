from __future__ import annotations

import os

import pytest

from dicom_kb.sources.downloader import resolve_official_current_edition
from dicom_kb.sources.edition_resolver import EDITION_RE

pytestmark = [
    pytest.mark.dicom_current,
    pytest.mark.skipif(
        os.environ.get("DICOM_KB_RUN_CURRENT") != "1",
        reason="live current-edition resolution is opt-in via make test-dicom-current",
    ),
]


def test_official_current_resolution_pins_concrete_edition() -> None:
    resolved = resolve_official_current_edition(edition="current")

    assert resolved.resolved_from == "current"
    assert resolved.edition != "current"
    assert EDITION_RE.fullmatch(resolved.edition)
