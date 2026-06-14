# Minimal Attributed Fixtures

This directory is reserved for tiny attributed excerpts from official sources
only when a parser behavior cannot be reproduced with synthetic fixtures.

Policy:

- Prefer `tests/fixtures_synthetic/` for every parser and query regression.
- Add no bulk official DICOM Standard artifacts, rendered pages, PDFs, generated
  SQLite databases, or broad parsed JSON.
- Keep each excerpt to the minimum text or XML needed to reproduce one behavior.
- Record the source edition, part, section/table anchor, retrieval date, and
  official URL beside the excerpt.
- Attribute DICOM Standard copyright ownership to NEMA and preserve the project
  legal notice.

The directory intentionally starts with policy only. No official excerpts are
needed for the current parser coverage.
