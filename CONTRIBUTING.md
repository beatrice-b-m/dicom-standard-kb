# Contributing

Contributions should preserve the repository's builder-not-mirror posture:
do not commit official DICOM XML, PDF, HTML, generated full-text indexes, or
generated full standard databases.

Run the offline quality gate before submitting changes:

```bash
make lint
make typecheck
make test
```

Parser fixtures should be synthetic unless a small attributed excerpt is
necessary to reproduce a specific parser behavior.
