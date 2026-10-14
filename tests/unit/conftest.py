from __future__ import annotations

import pytest

_DICOM_KB_ENV = ("DICOM_KB_EDITION", "DICOM_KB_CACHE_DIR", "DICOM_KB_DATABASE_URL")


@pytest.fixture(autouse=True)
def _isolate_from_the_user_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's real KB settings and the network out of unit tests.

    The documented real-source workflow exports these variables, and the CLI
    lets them beat a --config profile, so a leaked value would redirect a
    `build-fixture --force` onto the developer's real KB.
    """
    for name in _DICOM_KB_ENV:
        monkeypatch.delenv(name, raising=False)

    def no_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("unit tests must not reach the network")

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", no_network)
