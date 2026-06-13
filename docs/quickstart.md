# Quickstart

Install dependencies and run the offline suite:

```bash
make install
make test
uv run dicom-kb doctor
```

The default cache directory is `~/.cache/dicom-standard-kb/`.

Build and query the synthetic fixture without network access:

```bash
uv run dicom-kb build-fixture \
  --edition 2026b \
  --db /tmp/dicom-kb-fixture.sqlite \
  --force

uv run dicom-kb lookup tag Modality \
  --edition 2026b \
  --db /tmp/dicom-kb-fixture.sqlite

uv run dicom-kb context attribute Modality \
  --edition 2026b \
  --iod "CT Image" \
  --db /tmp/dicom-kb-fixture.sqlite
```

Build a real local KB after fetching official artifacts:

```bash
uv run dicom-kb fetch --edition current
uv run dicom-kb build --edition <concrete-edition>
uv run dicom-kb verify --edition <concrete-edition>
```

Use `--config` for shared defaults:

```yaml
dicom_kb:
  edition: 2026b
  artifact_dir: /tmp/dicom-standard-kb
  database_url: sqlite:////tmp/dicom-kb.sqlite
  require_citations: true
```

```bash
uv run dicom-kb --config ./dicom-kb.yaml lookup tag Modality
```
