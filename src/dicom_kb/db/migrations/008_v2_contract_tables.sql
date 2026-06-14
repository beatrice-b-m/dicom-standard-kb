PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vr_definition (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  vr TEXT NOT NULL,
  name TEXT NOT NULL,
  value_representation_class TEXT,
  length_notes_json TEXT NOT NULL DEFAULT '[]',
  padding_behavior TEXT,
  character_repertoire_notes_json TEXT NOT NULL DEFAULT '[]',
  binary_or_text TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, vr)
);

CREATE INDEX IF NOT EXISTS idx_vr_definition_vr
  ON vr_definition (edition_id, vr);

CREATE TABLE IF NOT EXISTS transfer_syntax_detail (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  uid_registry_entry_id TEXT NOT NULL REFERENCES uid_registry_entry(id),
  uid_value TEXT NOT NULL,
  explicit_vr INTEGER,
  endian TEXT,
  encapsulated INTEGER,
  compression_family TEXT,
  encoding_notes_json TEXT NOT NULL DEFAULT '[]',
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, uid_value)
);

CREATE INDEX IF NOT EXISTS idx_transfer_syntax_detail_uid
  ON transfer_syntax_detail (edition_id, uid_value);

CREATE TABLE IF NOT EXISTS file_meta_requirement (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  data_element_id TEXT REFERENCES data_element(id),
  attribute_tag TEXT NOT NULL,
  attribute_keyword TEXT,
  type_designation TEXT NOT NULL,
  rule_context TEXT,
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, attribute_tag, rule_context)
);

CREATE INDEX IF NOT EXISTS idx_file_meta_requirement_tag
  ON file_meta_requirement (edition_id, attribute_tag);

CREATE TABLE IF NOT EXISTS dicom_media_type (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  media_type TEXT NOT NULL,
  service_context TEXT,
  transfer_syntax_constraints_json TEXT NOT NULL DEFAULT '[]',
  directions_json TEXT NOT NULL DEFAULT '[]',
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, media_type, service_context)
);

CREATE INDEX IF NOT EXISTS idx_dicom_media_type_media_type
  ON dicom_media_type (edition_id, media_type);

CREATE TABLE IF NOT EXISTS dicomweb_transaction (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL,
  transaction_name TEXT NOT NULL,
  resource_category TEXT,
  http_method TEXT NOT NULL,
  route_template TEXT NOT NULL,
  request_constraints_json TEXT NOT NULL DEFAULT '[]',
  response_constraints_json TEXT NOT NULL DEFAULT '[]',
  status_codes_json TEXT NOT NULL DEFAULT '[]',
  media_type_refs_json TEXT NOT NULL DEFAULT '[]',
  source_ref_id TEXT NOT NULL REFERENCES source_ref(id),
  UNIQUE (edition_id, transaction_name, http_method, route_template)
);

CREATE INDEX IF NOT EXISTS idx_dicomweb_transaction_name
  ON dicomweb_transaction (edition_id, transaction_name);

CREATE INDEX IF NOT EXISTS idx_dicomweb_transaction_route
  ON dicomweb_transaction (edition_id, route_template);

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
