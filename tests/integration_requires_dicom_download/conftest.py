from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn

import pytest

from dicom_kb.build import default_db_path
from dicom_kb.db.models import read_sqlite
from dicom_kb.sources.downloader import DEFAULT_CACHE_DIR
from dicom_kb.sources.manifest import SourceManifest, manifest_path, read_manifest


def _cache_dir() -> Path:
    configured = os.environ.get("DICOM_KB_CACHE_DIR")
    return Path(configured).expanduser() if configured else DEFAULT_CACHE_DIR


def _discover_edition(cache_dir: Path) -> str | None:
    configured = os.environ.get("DICOM_KB_TEST_EDITION")
    if configured:
        return configured
    db_dir = cache_dir / "db"
    if not db_dir.exists():
        return None
    candidates = [
        path
        for path in db_dir.glob("*.sqlite")
        if manifest_path(cache_dir, path.stem).exists()
    ]
    if not candidates:
        return None
    newest = max(candidates, key=lambda path: path.stat().st_mtime)
    return newest.stem


@pytest.fixture(scope="session")
def cache_dir() -> Path:
    return _cache_dir()


@pytest.fixture(scope="session")
def edition(cache_dir: Path) -> str:
    discovered = _discover_edition(cache_dir)
    if discovered is None:
        _missing_prerequisite(
            "no built DICOM KB found; run `dicom-kb fetch --edition current` "
            "and `dicom-kb build --edition <resolved>`"
        )
    return discovered


@pytest.fixture(scope="session")
def db_path(cache_dir: Path, edition: str) -> Path:
    path = default_db_path(cache_dir, edition)
    if not path.exists():
        _missing_prerequisite(
            f"no built SQLite KB for edition {edition!r} at {path}; run "
            f"`dicom-kb build --edition {edition}`"
        )
    return path


@pytest.fixture(scope="session")
def connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    with read_sqlite(db_path) as reader:
        yield reader


@pytest.fixture(scope="session")
def manifest(cache_dir: Path, edition: str) -> SourceManifest:
    path = manifest_path(cache_dir, edition)
    if not path.exists():
        _missing_prerequisite(f"no source manifest for edition {edition!r} at {path}")
    return read_manifest(path)


def _missing_prerequisite(message: str) -> NoReturn:
    """Only optional smoke checks may skip unavailable local artifacts."""
    if os.environ.get("DICOM_KB_RUN_RELEASE") == "1":
        pytest.fail(f"strict release prerequisite missing: {message}", pytrace=False)
    pytest.skip(message)
