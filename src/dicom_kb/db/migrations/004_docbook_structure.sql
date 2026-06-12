PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS doc_node (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  part TEXT NOT NULL,
  node_type TEXT NOT NULL,
  parent_id TEXT REFERENCES doc_node(id),
  xml_id TEXT,
  anchor TEXT,
  number TEXT,
  title TEXT,
  ordinal INTEGER NOT NULL,
  plain_text TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, part, xml_id)
);

CREATE INDEX IF NOT EXISTS idx_doc_node_part_xml
  ON doc_node (edition_id, part, xml_id);

CREATE INDEX IF NOT EXISTS idx_doc_node_part_number
  ON doc_node (edition_id, part, number);

CREATE TABLE IF NOT EXISTS xref (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  source_node_id TEXT NOT NULL REFERENCES doc_node(id),
  target_ref TEXT NOT NULL,
  target_node_id TEXT REFERENCES doc_node(id),
  link_type TEXT NOT NULL,
  resolved INTEGER NOT NULL,
  resolution_warning TEXT,
  text TEXT
);

CREATE INDEX IF NOT EXISTS idx_xref_source
  ON xref (edition_id, source_node_id);

CREATE TABLE IF NOT EXISTS raw_table_ir (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  part TEXT NOT NULL,
  table_id TEXT,
  title TEXT,
  ordinal INTEGER NOT NULL,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  ir_json TEXT NOT NULL,
  ir_sha256 TEXT NOT NULL,
  UNIQUE (edition_id, part, table_id)
);

CREATE INDEX IF NOT EXISTS idx_raw_table_ir_part_table
  ON raw_table_ir (edition_id, part, table_id);
