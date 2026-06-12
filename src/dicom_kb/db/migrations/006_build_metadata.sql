PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS build_metadata (
  edition_id TEXT PRIMARY KEY REFERENCES standard_edition(id),
  built_at TEXT NOT NULL,
  parser_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  source_manifest_sha256 TEXT NOT NULL,
  repository_commit TEXT,
  metadata_json TEXT NOT NULL
);
