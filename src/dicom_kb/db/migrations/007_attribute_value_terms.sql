PRAGMA foreign_keys = ON;

-- Enumerated values and defined terms, one row per value. Rows sharing a
-- list_index come from one list; its title says which kind it is and any
-- qualifier ("Enumerated Values if Segmentation Type (0062,0001) is ...").
CREATE TABLE IF NOT EXISTS attribute_value_term (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  attribute_tag TEXT NOT NULL,
  attribute_use_id TEXT REFERENCES attribute_use(id),
  table_id TEXT,
  section_id TEXT,
  list_index INTEGER NOT NULL,
  list_title TEXT NOT NULL,
  term_kind TEXT NOT NULL,
  term_order INTEGER NOT NULL,
  value TEXT NOT NULL,
  meaning TEXT
);

CREATE INDEX IF NOT EXISTS idx_attribute_value_term_tag
  ON attribute_value_term (edition_id, attribute_tag);
