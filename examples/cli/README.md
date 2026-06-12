# CLI Example

Build the synthetic fixture KB, then run a query through the installed
`dicom-kb` command:

```bash
dicom-kb build-fixture --edition 2026b --db /tmp/dicom-kb-fixture.sqlite --force
dicom-kb lookup tag '(0008,0060)' \
  --edition 2026b \
  --db /tmp/dicom-kb-fixture.sqlite
```

For a real local build, use the concrete edition and SQLite DB path produced by
`dicom-kb fetch --edition current` followed by `dicom-kb build --edition <edition>`.
