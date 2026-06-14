"""Validate local DICOM identifier syntax helpers."""

from __future__ import annotations

import argparse
import json

from dicom_kb.ir.validators import normalize_tag, normalize_uid


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag")
    parser.add_argument("--uid")
    args = parser.parse_args()

    if bool(args.tag) == bool(args.uid):
        parser.error("pass exactly one of --tag or --uid")

    if args.tag:
        payload = {"kind": "tag", "normalized": normalize_tag(args.tag)}
    else:
        payload = {"kind": "uid", "normalized": normalize_uid(args.uid)}
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
