"""Look up one DICOM data element through the public Python resolver API."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dicom_kb.db.models import read_sqlite
from dicom_kb.query.resolver import lookup_data_element


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--edition", required=True)
    parser.add_argument("--tag", default="(0008,0060)")
    args = parser.parse_args()

    with read_sqlite(args.db) as connection:
        response = lookup_data_element(
            connection,
            tag_or_keyword=args.tag,
            edition=args.edition,
        )
    print(json.dumps(response.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
