"""Merge the screened historic public extract into the existing public database.

The CSV and document manifest are public aggregates. Raw PDFs and name lists are
not read. A missing or empty hand-quarantine file changes nothing.
"""

from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sqlite3
from pathlib import Path

from pipeline.documents import AMOUNT_SEMANTICS

ROOT = Path(__file__).resolve().parents[1]
HISTORIC = ROOT / "registry" / "historic"
LINES_GZ = HISTORIC / "historic_lines_public.csv.gz"
DOCUMENTS_JSON = HISTORIC / "documents.json"

DOCUMENT_COLUMNS = (
    "withheld_cents",
    "revenue_excluded_cents",
    "name_screen_quarantined_count",
    "name_screen_quarantined_cents",
    "public_plus_withheld_equals_printed",
)

SOURCE_CLASS = {
    "susd_diligent_ap_report": "paid_ap_ledger_report",
    "husd_diligent_voucher_summary": "voucher_account_summary",
    "qcusd_diligent_voucher_summary": "voucher_account_summary",
    "chandler_highbond_voucher_supplement": "voucher_account_summary",
    "pvusd_diligent_voucher_summary": "voucher_account_summary",
}

_FORBIDDEN = (
    re.compile(r"authorized\s+user", re.I),
    re.compile(r"authoriezed\s+user", re.I),
    re.compile(r"\bIEP\b", re.I),
    re.compile(r"\bESY\b"),
    re.compile(r"\bmedicaid\b", re.I),
    re.compile(r"\bdiagnosis\b", re.I),
    re.compile(r"\bprescription\b", re.I),
)


class HistoricLoadError(ValueError):
    """The public extract failed a reconcile or privacy check."""


def load_historic(connection: sqlite3.Connection, *, commit: bool = True) -> dict[str, int]:
    """Insert historic documents that are not already in the public database."""
    _ensure_document_columns(connection)
    documents = json.loads(DOCUMENTS_JSON.read_text(encoding="utf-8"))["documents"]
    quarantine = _hand_quarantine_keys()
    existing_ids = {row[0] for row in connection.execute("SELECT document_id FROM documents")}
    existing_sha = {row[0] for row in connection.execute("SELECT sha256 FROM documents")}
    existing_lines = {row[0] for row in connection.execute("SELECT line_id FROM lines")}
    skipped = [row for row in documents if row["document_id"] in existing_ids or row.get("sha256") in existing_sha]
    incoming = [row for row in documents if row not in skipped]
    by_id = {row["document_id"]: row for row in incoming}
    lines = _read_lines(by_id, existing_lines, quarantine)
    _assert_gate(incoming, lines)
    _insert_sources(connection, incoming)
    _insert_documents(connection, incoming)
    _insert_lines(connection, lines, by_id)
    _insert_gap_notes(connection, incoming)
    _link_new_chandler_source(connection)
    if commit:
        connection.commit()
    return {
        "documents_added": len(incoming),
        "documents_already_present": len(skipped),
        "public_lines_added": len(lines),
        "hand_quarantine_keys": len(quarantine),
    }


def _ensure_document_columns(connection: sqlite3.Connection) -> None:
    present = {row[1] for row in connection.execute("PRAGMA table_info(documents)")}
    for column in DOCUMENT_COLUMNS:
        if column not in present:
            connection.execute(f"ALTER TABLE documents ADD COLUMN {column} INTEGER")
    connection.execute("CREATE INDEX IF NOT EXISTS lines_document_id ON lines(document_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS lines_vendor_key ON lines(vendor_key)")
    connection.execute("CREATE INDEX IF NOT EXISTS lines_check_date ON lines(check_date)")
    connection.execute("CREATE INDEX IF NOT EXISTS lines_voucher_batch_date ON lines(voucher_batch_date)")


def _hand_quarantine_keys() -> set[str]:
    candidates = []
    override = os.environ.get("HISTORIC_HAND_QUARANTINE")
    if override:
        candidates.append(Path(override))
    candidates.append(HISTORIC / "hand_quarantine.json")
    for path in candidates:
        if not path.exists() or path.stat().st_size == 0:
            continue
        payload = json.loads(path.read_text(encoding="utf-8") or "null")
        if not payload:
            return set()
        keys = payload.get("quarantine_vendor_keys") if isinstance(payload, dict) else payload
        if not keys:
            return set()
        return {str(item).strip() for item in keys if str(item).strip()}
    return set()


def _read_lines(documents: dict[str, dict], existing_lines: set[str], quarantine: set[str]) -> list[dict[str, str]]:
    kept: list[dict[str, str]] = []
    seen: set[str] = set()
    with gzip.open(LINES_GZ, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("amount_semantics") != AMOUNT_SEMANTICS:
                raise HistoricLoadError(f"line {row.get('line_id')} has unexpected amount semantics")
            if row.get("privacy_class") != "safe_business_vendor":
                raise HistoricLoadError(f"line {row.get('line_id')} is not a screened business vendor")
            if row.get("in_default_aggregate") not in {"1", "1.0"}:
                raise HistoricLoadError(f"line {row.get('line_id')} is not in the default aggregate")
            _reject_private_text(row)
            document_id = row["document_id"]
            if document_id not in documents:
                continue
            if not documents[document_id].get("in_public_index"):
                raise HistoricLoadError(f"public line {row['line_id']} belongs to unindexed {document_id}")
            if row["vendor_key"] in quarantine:
                continue
            line_id = row["line_id"]
            if line_id in existing_lines or line_id in seen:
                raise HistoricLoadError(f"duplicate public line id {line_id}")
            seen.add(line_id)
            kept.append(row)
    return kept


def _reject_private_text(row: dict[str, str]) -> None:
    blob = f"{row.get('vendor_raw') or ''} {row.get('description_public') or ''}"
    for pattern in _FORBIDDEN:
        if pattern.search(blob):
            raise HistoricLoadError(f"line {row.get('line_id')} matches a privacy pattern")


def _assert_gate(documents: list[dict], lines: list[dict[str, str]]) -> None:
    sums: dict[str, int] = {}
    counts: dict[str, int] = {}
    for row in lines:
        document_id = row["document_id"]
        sums[document_id] = sums.get(document_id, 0) + int(row["amount_cents"])
        counts[document_id] = counts.get(document_id, 0) + 1
    for document in documents:
        if not document.get("in_public_index"):
            if counts.get(document["document_id"]):
                raise HistoricLoadError(f"unindexed {document['document_id']} has public lines")
            continue
        document_id = document["document_id"]
        public = sums.get(document_id, 0)
        withheld = int(document.get("withheld_cents") or 0)
        revenue = int(document.get("revenue_excluded_cents") or 0)
        printed = document.get("printed_total_cents")
        if printed is None or public + withheld + revenue != int(printed):
            raise HistoricLoadError(
                f"{document_id} reconcile failed: public {public} + withheld {withheld} + non-spending {revenue} != printed {printed}"
            )
        if counts.get(document_id, 0) != int(document.get("public_default_aggregate_lines") or 0):
            raise HistoricLoadError(f"{document_id} public line count does not match the manifest")
        if public != int(document.get("public_default_aggregate_cents") or 0):
            raise HistoricLoadError(f"{document_id} public cents do not match the manifest")


def _insert_sources(connection: sqlite3.Connection, documents: list[dict]) -> None:
    present = {row[0] for row in connection.execute("SELECT source_id FROM sources")}
    for document in documents:
        source_id = document["source_id"]
        if source_id in present:
            continue
        present.add(source_id)
        connection.execute(
            """INSERT INTO sources (
                source_id, entity_name, entity_type, source_status, access_status, line_item_confirmed,
                admin_county, lea_ctds, service_counties, service_counties_null_reason, document_class,
                adapter_family, discovery_state, ingestion_status, evidence_level
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                source_id,
                document["entity_name"],
                "public_district",
                "historic_public_extract",
                "public_document",
                1,
                document.get("admin_county"),
                document.get("lea_ctds"),
                None,
                "service geography is not in this historic extract",
                SOURCE_CLASS.get(source_id, "voucher_account_summary"),
                document.get("source_family"),
                "historic_extract",
                "indexed_reconciled" if document.get("in_public_index") else "parsed_not_indexed",
                "screened_public_lines",
            ),
        )


def _insert_documents(connection: sqlite3.Connection, documents: list[dict]) -> None:
    for document in documents:
        indexed = 1 if document.get("in_public_index") else 0
        note = document.get("coverage_note") or "Observed document window only. Not continuous coverage."
        if not indexed:
            note = f"{note} This document is not in the spending index. It is not zero spending."
        if indexed and int(document.get("public_line_count") or 0) == 0:
            note = f"{note} Indexed because the lines reconcile to the printed total. Every line on this document was withheld, so the public line count is 0."
        connection.execute(
            """INSERT INTO documents (
                document_id, source_id, url, sha256, content_type, parser_id, parser_version,
                period_label_native, period_start, period_end, reconciliation_status,
                printed_total_cents, printed_total_null_reason, parsed_total_cents, parsed_total_null_reason,
                parsed_outcome, delta_cents, delta_null_reason, parsed_line_count, public_line_count,
                withheld_count, withheld_cents, revenue_excluded_count, revenue_excluded_cents,
                name_screen_quarantined_count, name_screen_quarantined_cents, public_plus_withheld_equals_printed,
                warning_count, indexed, amount_semantics, manifest_membership, coverage_note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                document["document_id"],
                document["source_id"],
                document.get("source_url"),
                document.get("sha256"),
                "application/pdf",
                document.get("parser_id"),
                document.get("parser_version"),
                document.get("official_label_native") or document.get("fiscal_year_label_native"),
                document.get("period_start"),
                document.get("period_end"),
                document.get("reconcile_status"),
                document.get("printed_total_cents"),
                document.get("printed_total_null_reason"),
                document.get("parsed_total_cents"),
                None,
                "parsed_lines" if indexed else "parsed_unreconciled",
                document.get("delta_cents"),
                None if document.get("delta_cents") is not None else "no printed total to compare",
                document.get("parsed_line_count"),
                document.get("public_line_count") or 0,
                document.get("withheld_count") or 0,
                document.get("withheld_cents") or 0,
                document.get("revenue_excluded_count") or 0,
                document.get("revenue_excluded_cents") or 0,
                document.get("name_screen_quarantined_count") or 0,
                document.get("name_screen_quarantined_cents") or 0,
                1 if document.get("public_plus_withheld_equals_printed") else 0,
                0,
                indexed,
                AMOUNT_SEMANTICS,
                "historic_screened_2026-11-11",
                note,
            ),
        )


def _insert_lines(connection: sqlite3.Connection, lines: list[dict[str, str]], documents: dict[str, dict]) -> None:
    line_sql = """INSERT INTO lines (
        line_id, document_id, source_id, entity_name, entity_type, admin_county, lea_ctds,
        amount_cents, currency, vendor_raw, vendor_key, description_public, dac_raw, account_code_raw, po_raw,
        check_date, check_date_null_reason, voucher_batch_date, voucher_batch_date_raw, voucher_batch_number,
        fiscal_year_label_native, period_label_native, period_start, period_end, document_class, amount_semantics,
        category, category_confidence, category_ruleset, category_evidence, privacy_class, source_url,
        source_page, source_row, source_locator, flags, date_conflict, in_default_aggregate,
        item_label, item_evidence, item_method, item_confidence
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""
    fts_sql = """INSERT INTO lines_fts (line_id, vendor_raw, description_public, dac_raw, account_code_raw, entity_name)
                 VALUES (?,?,?,?,?,?)"""
    line_rows = []
    fts_rows = []
    for row in lines:
        document = documents[row["document_id"]]
        line_rows.append((
            row["line_id"], row["document_id"], row["source_id"], row["entity_name"], "public_district",
            _blank(row.get("admin_county")), _blank(row.get("lea_ctds")), int(row["amount_cents"]), row.get("currency") or "USD",
            row["vendor_raw"], row["vendor_key"], row.get("description_public") or "", _blank(row.get("dac_raw")),
            _blank(row.get("account_code_raw")), _blank(row.get("po_raw")), _blank(row.get("check_date")),
            _blank(row.get("check_date_null_reason")), _blank(row.get("voucher_batch_date")), _blank(row.get("voucher_batch_date_raw")),
            _blank(row.get("voucher_batch_number")), _blank(row.get("fiscal_year_label_native")), _blank(row.get("period_label_native")),
            document.get("period_start"), document.get("period_end"), row.get("document_class"), AMOUNT_SEMANTICS,
            row.get("category") or "unclassified", _float(row.get("category_confidence")), row.get("category_ruleset"),
            row.get("category_evidence"), row.get("privacy_class"), row.get("source_url"), _int(row.get("source_page")),
            _int(row.get("source_row")), _blank(row.get("source_locator")), _blank(row.get("flags")), 0, 1,
            None, None, None, None,
        ))
        fts_rows.append((
            row["line_id"], row["vendor_raw"], row.get("description_public") or "", row.get("dac_raw") or "",
            row.get("account_code_raw") or "", row["entity_name"],
        ))
    connection.executemany(line_sql, line_rows)
    connection.executemany(fts_sql, fts_rows)


def _insert_gap_notes(connection: sqlite3.Connection, documents: list[dict]) -> None:
    for document in documents:
        if document.get("in_public_index"):
            continue
        connection.execute(
            "INSERT INTO coverage_notes (source_id, note) VALUES (?, ?)",
            (
                document["source_id"],
                f"{document['document_id']} is {document.get('reconcile_status')} and is not in the spending index. It is not zero spending.",
            ),
        )


def _link_new_chandler_source(connection: sqlite3.Connection) -> None:
    present = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'october1_index_leas'"
    ).fetchone()
    if present is None:
        return
    if connection.execute(
        "SELECT 1 FROM october1_index_leas WHERE source_id = ?",
        ("chandler_highbond_voucher_supplement",),
    ).fetchone():
        return
    order = connection.execute("SELECT COALESCE(MAX(display_order), -1) + 1 FROM october1_index_leas").fetchone()[0]
    connection.execute(
        """INSERT INTO october1_index_leas (source_id, entity_name, focus_district, lea_entity_id, display_order)
           VALUES (?, ?, ?, ?, ?)""",
        ("chandler_highbond_voucher_supplement", "Chandler Unified School District #80", "Chandler Unified", "4242", order),
    )


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: str | None) -> int | None:
    text = _blank(value)
    return int(text) if text is not None else None


def _float(value: str | None) -> float | None:
    text = _blank(value)
    return float(text) if text is not None else None
