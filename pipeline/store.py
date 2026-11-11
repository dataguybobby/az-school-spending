"""SQLite layers. The web app opens only the public database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

PUBLIC_SCHEMA = """
CREATE TABLE sources (
  source_id TEXT PRIMARY KEY,
  entity_name TEXT,
  entity_type TEXT,
  source_status TEXT,
  access_status TEXT,
  line_item_confirmed INTEGER,
  admin_county TEXT,
  lea_ctds TEXT,
  service_counties TEXT,
  service_counties_null_reason TEXT,
  document_class TEXT,
  adapter_family TEXT,
  discovery_state TEXT,
  ingestion_status TEXT,
  evidence_level TEXT
);
CREATE TABLE documents (
  document_id TEXT PRIMARY KEY,
  source_id TEXT,
  url TEXT,
  sha256 TEXT,
  content_type TEXT,
  parser_id TEXT,
  parser_version TEXT,
  period_label_native TEXT,
  period_start TEXT,
  period_end TEXT,
  reconciliation_status TEXT,
  printed_total_cents INTEGER,
  printed_total_null_reason TEXT,
  parsed_total_cents INTEGER,
  parsed_total_null_reason TEXT,
  parsed_outcome TEXT,
  delta_cents INTEGER,
  delta_null_reason TEXT,
  parsed_line_count INTEGER,
  public_line_count INTEGER,
  withheld_count INTEGER,
  revenue_excluded_count INTEGER,
  warning_count INTEGER,
  indexed INTEGER,
  amount_semantics TEXT,
  manifest_membership TEXT,
  coverage_note TEXT
);
CREATE TABLE lines (
  line_id TEXT PRIMARY KEY,
  document_id TEXT,
  source_id TEXT,
  entity_name TEXT,
  entity_type TEXT,
  admin_county TEXT,
  lea_ctds TEXT,
  amount_cents INTEGER,
  currency TEXT,
  vendor_raw TEXT,
  vendor_key TEXT,
  description_public TEXT,
  dac_raw TEXT,
  account_code_raw TEXT,
  po_raw TEXT,
  check_date TEXT,
  check_date_null_reason TEXT,
  voucher_batch_date TEXT,
  voucher_batch_date_raw TEXT,
  voucher_batch_number TEXT,
  fiscal_year_label_native TEXT,
  period_label_native TEXT,
  period_start TEXT,
  period_end TEXT,
  document_class TEXT,
  amount_semantics TEXT,
  category TEXT,
  category_confidence REAL,
  category_ruleset TEXT,
  category_evidence TEXT,
  privacy_class TEXT,
  source_url TEXT,
  source_page INTEGER,
  source_row INTEGER,
  source_locator TEXT,
  flags TEXT,
  date_conflict INTEGER,
  in_default_aggregate INTEGER,
  item_label TEXT,
  item_evidence TEXT,
  item_method TEXT,
  item_confidence REAL
);
CREATE VIRTUAL TABLE lines_fts USING fts5(
  line_id UNINDEXED,
  vendor_raw,
  description_public,
  dac_raw,
  account_code_raw,
  entity_name,
  tokenize='unicode61'
);
CREATE TABLE coverage_notes (
  note_id INTEGER PRIMARY KEY,
  source_id TEXT,
  note TEXT
);
CREATE TABLE overlap_findings (
  finding_id INTEGER PRIMARY KEY,
  left_document_id TEXT,
  right_document_id TEXT,
  source_id TEXT,
  header_shared_dates TEXT,
  shared_check_date_count INTEGER,
  rows_on_shared_header_dates INTEGER,
  rows_on_shared_header_cents INTEGER,
  verdict TEXT,
  recurring_different_date_keys INTEGER,
  recurring_different_date_line_count INTEGER,
  recurring_different_date_cents INTEGER,
  included_in_default_total INTEGER,
  note TEXT
);
"""

PRIVATE_SCHEMA = """
CREATE TABLE artifacts (
  sha256 TEXT PRIMARY KEY,
  document_id TEXT,
  source_id TEXT,
  url TEXT,
  content_type TEXT,
  byte_length INTEGER,
  retrieved_at TEXT,
  parser_id TEXT,
  parser_version TEXT,
  active INTEGER
);
CREATE TABLE silver_lines (
  line_id TEXT PRIMARY KEY,
  sha256 TEXT,
  document_id TEXT,
  active INTEGER,
  vendor_raw TEXT,
  description_raw TEXT,
  amount_cents INTEGER,
  check_number_raw TEXT,
  privacy_class TEXT,
  privacy_reasons TEXT,
  line_kind TEXT,
  payload_json TEXT
);
"""


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def rebuild(path: Path, schema: str) -> sqlite3.Connection:
    if path.exists():
        path.unlink()
    connection = connect(path)
    connection.executescript(schema)
    return connection
