# Build a Local Knowledge Base

```bash
dicom-kb fetch --edition current
dicom-kb build --edition 2026b
dicom-kb lookup tag Modality --edition 2026b
```

`fetch` resolves `current` from the official DICOM current release metadata
before writing a manifest. By default, official fetch downloads the DocBook
XML parts used by the implemented v1 parsers: PS3.3, PS3.4, and PS3.6.

Concrete historical editions are fetched from the official DICOM archive
directory instead of the mutable current-release directory:

```bash
dicom-kb fetch --edition 2025e --part PS3.6
```

To restrict the official fetch to one or more parts:

```bash
dicom-kb fetch --edition current --part PS3.6
```

To cache additional official formats for citation verification or local
inspection, repeat `--format`:

```bash
dicom-kb fetch --edition current --part PS3.6 --format docbook_xml --format pdf
dicom-kb fetch --edition current --part PS3.6 --format html --format targetdb
```

Supported official formats are `docbook_xml`, `pdf`, `html`, `chtml`, and
`targetdb`. The SQLite build reads the `docbook_xml` artifacts and preserves
the other artifact checksums in the manifest/build metadata.

By default, `--format chtml` downloads the part entry page. To mirror the full
per-part CHTML directory for local inspection, add `--mirror-chtml-tree`:

```bash
dicom-kb fetch --edition current --part PS3.6 --format chtml --mirror-chtml-tree
```

Local fixture or pre-downloaded XML registration is still available:

```bash
dicom-kb fetch --edition 2026b --docbook-xml PS3.6=/path/to/part06.xml
```

Generated databases live in the local cache and are not committed.
