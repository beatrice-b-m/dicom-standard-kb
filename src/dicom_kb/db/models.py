"""SQLite connection and migration helpers."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def connect_sqlite(path: Path, *, read_only: bool = False) -> sqlite3.Connection:
    """Open a configured connection; the caller owns closing it."""
    if read_only:
        if not path.is_file():
            raise FileNotFoundError(f"SQLite KB does not exist: {path}")
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def read_sqlite(path: Path) -> Iterator[sqlite3.Connection]:
    """Open an existing KB read-only and close it even when a query fails.

    SQLite's own connection context manager manages transactions, not lifetime.
    Use this helper at query entrypoints that own the connection.
    """
    connection = connect_sqlite(path, read_only=True)
    try:
        yield connection
    finally:
        connection.close()


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply bundled SQL migrations idempotently."""
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
        connection.executescript(migration.read_text(encoding="utf-8"))
