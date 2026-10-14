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
  -- The node's own content as markdown with references resolved. A section
  -- keeps a [[table:<xml id>]] line where each of its tables sits.
  markdown TEXT,
  informative INTEGER NOT NULL DEFAULT 0,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, part, xml_id)
);

CREATE INDEX IF NOT EXISTS idx_doc_node_part_xml
  ON doc_node (edition_id, part, xml_id);

CREATE INDEX IF NOT EXISTS idx_doc_node_part_number
  ON doc_node (edition_id, part, number);

CREATE INDEX IF NOT EXISTS idx_doc_node_number
  ON doc_node (edition_id, number);

CREATE INDEX IF NOT EXISTS idx_doc_node_parent
  ON doc_node (parent_id, ordinal);

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
