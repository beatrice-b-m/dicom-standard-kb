"""Look up one DICOM data element through the public Python resolver API."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from dicom_kb.query.resolver import lookup_data_element


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--edition", required=True)
    parser.add_argument("--tag", default="(0008,0060)")
    args = parser.parse_args()

    with _connect_db(args.db) as connection:
        response = lookup_data_element(
            connection,
            tag_or_keyword=args.tag,
            edition=args.edition,
        )
    print(json.dumps(response.model_dump(mode="json"), indent=2, sort_keys=True))


def _connect_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


if __name__ == "__main__":
    main()
