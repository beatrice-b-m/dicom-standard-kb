PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS condition (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  condition_kind TEXT,
  raw_text TEXT NOT NULL,
  normalized_text TEXT,
  machine_status TEXT NOT NULL,
  expression_json TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id)
);

CREATE TABLE IF NOT EXISTS iod (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  name TEXT NOT NULL,
  keyword TEXT,
  iod_type TEXT,
  part TEXT NOT NULL DEFAULT 'PS3.3',
  section TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, name)
);

CREATE TABLE IF NOT EXISTS module (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  name TEXT NOT NULL,
  section TEXT,
  description TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, name, section)
);

CREATE TABLE IF NOT EXISTS macro (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  name TEXT NOT NULL,
  table_id TEXT,
  section TEXT,
  macro_kind TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, table_id)
);

CREATE TABLE IF NOT EXISTS iod_module_use (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  iod_id TEXT NOT NULL REFERENCES iod(id),
  information_entity TEXT,
  module_id TEXT NOT NULL REFERENCES module(id),
  usage TEXT NOT NULL,
  usage_condition_text TEXT,
  condition_id TEXT REFERENCES condition(id),
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id)
);

CREATE TABLE IF NOT EXISTS iod_functional_group_use (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  iod_id TEXT NOT NULL REFERENCES iod(id),
  macro_id TEXT NOT NULL REFERENCES macro(id),
  usage TEXT NOT NULL,
  usage_condition_text TEXT,
  condition_id TEXT REFERENCES condition(id),
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id)
);

CREATE TABLE IF NOT EXISTS attribute_use (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  owner_type TEXT NOT NULL,
  owner_id TEXT NOT NULL,
  parent_attribute_use_id TEXT REFERENCES attribute_use(id),
  row_kind TEXT NOT NULL,
  attribute_tag TEXT,
  attribute_keyword TEXT,
  attribute_name TEXT,
  type_designation TEXT,
  description_text TEXT,
  condition_id TEXT REFERENCES condition(id),
  included_macro_id TEXT REFERENCES macro(id),
  include_target_text TEXT,
  sequence_depth INTEGER NOT NULL DEFAULT 0,
  row_order INTEGER NOT NULL,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id)
);

CREATE INDEX IF NOT EXISTS idx_iod_name
  ON iod (edition_id, name);

CREATE INDEX IF NOT EXISTS idx_module_name
  ON module (edition_id, name);

CREATE INDEX IF NOT EXISTS idx_macro_table_id
  ON macro (edition_id, table_id);

CREATE INDEX IF NOT EXISTS idx_iod_module_use_iod
  ON iod_module_use (edition_id, iod_id);

CREATE INDEX IF NOT EXISTS idx_attribute_use_owner
  ON attribute_use (edition_id, owner_type, owner_id, row_order);
