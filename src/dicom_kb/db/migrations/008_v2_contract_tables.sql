PRAGMA foreign_keys = ON;

-- One row per transfer syntax that PS3.5 Annex A defines in this edition.
-- section_xml_id is the defining PS3.5 section; see_also_json lists the other
-- PS3.5 sections and tables that name the UID.
CREATE TABLE IF NOT EXISTS transfer_syntax_detail (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  uid_value TEXT NOT NULL,
  vr_encoding TEXT NOT NULL,
  byte_order TEXT NOT NULL,
  pixel_data TEXT NOT NULL,
  deflate TEXT,
  section_xml_id TEXT NOT NULL,
  see_also_json TEXT NOT NULL DEFAULT '[]',
  UNIQUE (edition_id, uid_value)
);

CREATE TABLE IF NOT EXISTS sr_template (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  tid TEXT NOT NULL,
  name TEXT NOT NULL,
  extensibility TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, tid)
);

CREATE INDEX IF NOT EXISTS idx_sr_template_tid
  ON sr_template (edition_id, tid);

CREATE TABLE IF NOT EXISTS sr_template_row (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  sr_template_id TEXT NOT NULL REFERENCES sr_template(id),
  row_order INTEGER NOT NULL,
  relationship_type TEXT,
  value_type TEXT,
  concept_name TEXT,
  cardinality TEXT,
  condition_text TEXT,
  condition_id TEXT REFERENCES condition(id),
  include_tid TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (sr_template_id, row_order)
);

CREATE INDEX IF NOT EXISTS idx_sr_template_row_template
  ON sr_template_row (edition_id, sr_template_id, row_order);

CREATE TABLE IF NOT EXISTS context_group (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  cid TEXT NOT NULL,
  name TEXT NOT NULL,
  extensibility TEXT,
  version TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, cid)
);

CREATE INDEX IF NOT EXISTS idx_context_group_cid
  ON context_group (edition_id, cid);

CREATE TABLE IF NOT EXISTS context_group_row (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  context_group_id TEXT NOT NULL REFERENCES context_group(id),
  row_order INTEGER NOT NULL,
  coding_scheme_designator TEXT,
  coding_scheme_version TEXT,
  code_value TEXT,
  code_meaning TEXT,
  include_cid TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (context_group_id, row_order)
);

CREATE INDEX IF NOT EXISTS idx_context_group_row_group
  ON context_group_row (edition_id, context_group_id, row_order);

CREATE TABLE IF NOT EXISTS coded_concept (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  code_value TEXT NOT NULL,
  coding_scheme_designator TEXT NOT NULL,
  coding_scheme_version TEXT NOT NULL DEFAULT '',
  code_meaning TEXT NOT NULL,
  definition TEXT,
  notes TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (
    edition_id,
    code_value,
    coding_scheme_designator,
    coding_scheme_version
  )
);

CREATE INDEX IF NOT EXISTS idx_coded_concept_lookup
  ON coded_concept (
    edition_id,
    code_value,
    coding_scheme_designator,
    coding_scheme_version
  );
