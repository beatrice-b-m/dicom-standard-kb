PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS attribute_value_term (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  attribute_use_id TEXT REFERENCES attribute_use(id),
  data_element_id TEXT REFERENCES data_element(id),
  context_label TEXT,
  term_kind TEXT NOT NULL,
  value TEXT NOT NULL,
  meaning TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id)
);

CREATE INDEX IF NOT EXISTS idx_attribute_value_term_data_element
  ON attribute_value_term (edition_id, data_element_id, term_kind);

CREATE INDEX IF NOT EXISTS idx_attribute_value_term_attribute_use
  ON attribute_value_term (edition_id, attribute_use_id, term_kind);
