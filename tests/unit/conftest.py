from __future__ import annotations

from pathlib import Path

import pytest

from dicom_kb.build import build_sqlite_database
from dicom_kb.sources.downloader import (
    DOCBOOK_XML_FORMAT,
    ArtifactRequest,
    official_artifact_destination,
    register_local_artifacts,
)
from tests.fixtures_synthetic import EDITION, FIXTURE_DIR, SYNTHETIC_PARTS

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


@pytest.fixture(scope="session")
def fixture_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A KB built once from every synthetic fixture by the real build path.

    Tests only read it. Build it per test (`build_sqlite_database`) when a
    test needs to change what goes in.
    """
    cache_dir = tmp_path_factory.mktemp("fixture-cache")
    register_local_artifacts(
        edition=EDITION,
        cache_dir=cache_dir,
        artifacts=[
            ArtifactRequest(
                part=part,
                format=DOCBOOK_XML_FORMAT,
                source=FIXTURE_DIR / filename,
                destination=official_artifact_destination(
                    EDITION, part=part, artifact_format=DOCBOOK_XML_FORMAT
                ),
            )
            for part, filename in SYNTHETIC_PARTS.items()
        ],
    )
    return build_sqlite_database(edition=EDITION, cache_dir=cache_dir).db_path
