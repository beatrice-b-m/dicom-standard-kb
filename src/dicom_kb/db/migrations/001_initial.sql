PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS standard_edition (
  id TEXT PRIMARY KEY,
  source_label TEXT NOT NULL,
  resolved_from TEXT,
  acquired_at TEXT NOT NULL,
  is_default INTEGER NOT NULL,
  manifest_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_artifact (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL REFERENCES standard_edition(id),
  part TEXT NOT NULL,
  format TEXT NOT NULL,
  local_path TEXT NOT NULL,
  source_url TEXT,
  sha256 TEXT NOT NULL,
  byte_size INTEGER,
  acquired_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_ref (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  part TEXT NOT NULL,
  chapter TEXT,
  section TEXT,
  table_id TEXT,
  figure_id TEXT,
  xml_id TEXT,
  anchor TEXT,
  title TEXT,
  source_artifact_id TEXT REFERENCES source_artifact(id),
  canonical_url TEXT,
  text_excerpt TEXT,
  excerpt_hash TEXT
);

CREATE TABLE IF NOT EXISTS data_element (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  tag TEXT NOT NULL,
  group_pattern TEXT NOT NULL,
  element_pattern TEXT NOT NULL,
  is_range INTEGER NOT NULL,
  name TEXT NOT NULL,
  keyword TEXT,
  vr TEXT,
  vm TEXT,
  retired INTEGER NOT NULL,
  retired_in_or_last_seen TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_data_element_keyword
  ON data_element (edition_id, keyword);

CREATE TABLE IF NOT EXISTS uid_registry_entry (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  uid_value TEXT NOT NULL,
  uid_name TEXT NOT NULL,
  uid_keyword TEXT,
  uid_type TEXT NOT NULL,
  part TEXT,
  retired INTEGER NOT NULL,
  retired_in_or_last_seen TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, uid_value)
);

CREATE INDEX IF NOT EXISTS idx_uid_registry_keyword
  ON uid_registry_entry (edition_id, uid_keyword);
