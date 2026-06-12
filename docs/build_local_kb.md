# Build a Local Knowledge Base

```bash
dicom-kb fetch --edition current
dicom-kb build --edition 2026b
dicom-kb lookup tag Modality --edition 2026b
```

`fetch` resolves `current` from the official DICOM current release metadata
before writing a manifest. In v1, official fetch downloads the DocBook XML
parts used by the implemented parsers: PS3.3, PS3.4, and PS3.6.

To restrict the official fetch to one or more parts:

```bash
dicom-kb fetch --edition current --part PS3.6
```

Local fixture or pre-downloaded XML registration is still available:

```bash
dicom-kb fetch --edition 2026b --docbook-xml PS3.6=/path/to/part06.xml
```

Generated databases live in the local cache and are not committed.
