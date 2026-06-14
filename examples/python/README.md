# Python Example

Runs a direct Python resolver call against a local SQLite KB.

```bash
python examples/python/lookup_modality.py \
  --db /tmp/dicom-kb-fixture.sqlite \
  --edition 2026b
```

The default tag is present in the synthetic fixture KB. Use a real local build
by changing `--db`, `--edition`, and optionally `--tag`.
