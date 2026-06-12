"""SQLite connection and migration helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def connect_sqlite(path: Path) -> sqlite3.Connection:
    """Open a SQLite connection with required pragmas."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply bundled SQL migrations idempotently."""
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
        connection.executescript(migration.read_text(encoding="utf-8"))
