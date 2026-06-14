# Third-Party Notices

This repository contains original source code licensed under Apache-2.0.
It does not vendor official DICOM standard artifacts, generated standard
databases, or third-party terminology dumps.

## DICOM Standard

The DICOM Standard is copyright owned by NEMA. Users should obtain official
artifacts from:

- https://www.dicomstandard.org/current
- https://dicom.nema.org/medical/dicom/current/

Locally downloaded standard artifacts and generated knowledge bases are
outside the scope of this repository's Apache-2.0 license.

PS3.16 content mapping resources may reference third-party terminology
systems. This repository does not vendor those terminology systems, generated
PS3.16 terminology dumps, or standalone context-group/code databases.

## Differential Testing References

The following projects may be used for parser comparison only and are not
sources of truth for generated facts:

- Innolitics dicom-standard: https://github.com/innolitics/dicom-standard
- pydicom dicom-validator: https://github.com/pydicom/dicom-validator
