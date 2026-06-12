# Build a Local Knowledge Base

```bash
dicom-kb fetch --edition current
dicom-kb build --edition 2026b
dicom-kb lookup tag Modality --edition 2026b
```

Generated databases live in the local cache and are not committed.
