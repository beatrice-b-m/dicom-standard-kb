# dicom-standard-kb

`dicom-standard-kb` is an open-source parser and local query service for
building an edition-pinned knowledge base from the official DICOM standard.
It is a builder, not a redistribution of the standard or a prebuilt knowledge
base.

## Status

This repository is implementing v1 from `SYSTEM_SPECS.md`: local source
acquisition, DocBook parsing, SQLite import, deterministic query tools, CLI,
and MCP surfaces for coding agents.

## Legal Notice

This project is not affiliated with, sponsored by, or endorsed by NEMA,
MITA, or the DICOM Standards Committee.
DICOM® is a registered trademark of the National Electrical Manufacturers
Association (NEMA). The DICOM Standard is copyright owned by NEMA.
Users should obtain the official current standard from dicomstandard.org.
This project does not provide official DICOM conformance certification.

The Apache-2.0 license applies to this repository's original source code.
It does not apply to the DICOM Standard or to third-party terminology
content referenced by the DICOM Standard.

## Quickstart

```bash
make install
make test
dicom-kb --help
```

Local DICOM artifacts and generated databases are stored outside the
repository, under `~/.cache/dicom-standard-kb/` by default.
