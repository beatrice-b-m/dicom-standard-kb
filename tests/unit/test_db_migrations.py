from __future__ import annotations

from pathlib import Path

from dicom_kb.db.models import apply_migrations, connect_sqlite, read_sqlite


def test_migrations_can_run_twice(tmp_path: Path) -> None:
    connection = connect_sqlite(tmp_path / "kb.sqlite")

    apply_migrations(connection)
    apply_migrations(connection)

    tables = connection.execute(
        "SELECT count(*) FROM sqlite_master WHERE type = 'table'"
    ).fetchone()[0]
    assert tables > 0


def test_built_kb_has_no_dangling_foreign_keys(fixture_db: Path) -> None:
    with read_sqlite(fixture_db) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
