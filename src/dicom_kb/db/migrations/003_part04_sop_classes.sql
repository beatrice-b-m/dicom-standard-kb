PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS service_class (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  name TEXT NOT NULL,
  section TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, name)
);

CREATE TABLE IF NOT EXISTS sop_class (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  name TEXT NOT NULL,
  uid_value TEXT NOT NULL,
  service_class_id TEXT REFERENCES service_class(id),
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, uid_value)
);

CREATE TABLE IF NOT EXISTS sop_class_iod (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  sop_class_id TEXT NOT NULL REFERENCES sop_class(id),
  iod_id TEXT NOT NULL REFERENCES iod(id),
  resolution TEXT NOT NULL,
  resolution_warning TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id)
);

CREATE INDEX IF NOT EXISTS idx_service_class_name
  ON service_class (edition_id, name);

CREATE INDEX IF NOT EXISTS idx_sop_class_name
  ON sop_class (edition_id, name);

CREATE INDEX IF NOT EXISTS idx_sop_class_uid
  ON sop_class (edition_id, uid_value);

CREATE INDEX IF NOT EXISTS idx_sop_class_iod_sop_class
  ON sop_class_iod (edition_id, sop_class_id);
