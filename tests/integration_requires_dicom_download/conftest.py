from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from dicom_kb.build import default_db_path
from dicom_kb.sources.downloader import DEFAULT_CACHE_DIR
from dicom_kb.sources.manifest import manifest_path, read_manifest


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
        pytest.skip(
            "no built DICOM KB found; run `dicom-kb fetch --edition current` "
            "and `dicom-kb build --edition <resolved>`"
        )
    return discovered


@pytest.fixture(scope="session")
def db_path(cache_dir: Path, edition: str) -> Path:
    path = default_db_path(cache_dir, edition)
    if not path.exists():
        pytest.skip(
            f"no built SQLite KB for edition {edition!r} at {path}; run "
            f"`dicom-kb build --edition {edition}`"
        )
    return path


@pytest.fixture(scope="session")
def connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture(scope="session")
def manifest(cache_dir: Path, edition: str) -> object:
    path = manifest_path(cache_dir, edition)
    if not path.exists():
        pytest.skip(f"no source manifest for edition {edition!r} at {path}")
    return read_manifest(path)
