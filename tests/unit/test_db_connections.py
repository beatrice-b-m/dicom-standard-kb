"""Connection ownership and filesystem-path handling at query boundaries."""

import sqlite3
from pathlib import Path

import pytest

from dicom_kb.db.models import connect_sqlite, read_sqlite


def test_read_sqlite_handles_uri_characters_and_enforces_read_only(
    tmp_path: Path,
) -> None:
    path = tmp_path / "knowledge #1?mode=rw%.sqlite"
    connection = connect_sqlite(path)
    connection.execute("CREATE TABLE sample (value TEXT)")
    connection.execute("INSERT INTO sample VALUES ('expected')")
    connection.commit()
    connection.close()

    with read_sqlite(path) as reader:
        assert (
            reader.execute("SELECT value FROM sample").fetchone()["value"] == "expected"
        )
        assert reader.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            reader.execute("INSERT INTO sample VALUES ('unexpected')")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        reader.execute("SELECT 1")


def test_read_sqlite_closes_when_query_raises(tmp_path: Path) -> None:
    path = tmp_path / "kb.sqlite"
    connect_sqlite(path).close()
    with pytest.raises(RuntimeError, match="query failed"), read_sqlite(path) as reader:
        raise RuntimeError("query failed")
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        reader.execute("SELECT 1")


def test_read_sqlite_never_creates_missing_database(tmp_path: Path) -> None:
    path = tmp_path / "missing" / "kb.sqlite"
    with pytest.raises(FileNotFoundError), read_sqlite(path):
        pytest.fail("missing database opened")
    assert not path.parent.exists()
