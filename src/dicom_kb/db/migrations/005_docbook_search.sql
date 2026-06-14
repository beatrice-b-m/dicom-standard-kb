PRAGMA foreign_keys = ON;

CREATE VIRTUAL TABLE IF NOT EXISTS doc_node_fts USING fts5(
  node_id UNINDEXED,
  edition_id UNINDEXED,
  part UNINDEXED,
  title,
  plain_text
);
