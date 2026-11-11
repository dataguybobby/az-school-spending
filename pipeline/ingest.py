"""Fetch, parse, classify, and index. Re-running the same bytes is idempotent."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.adapters import ADAPTERS
from pipeline.classify import apply_override, classify_text, load_overrides
from pipeline.documents import AMOUNT_SEMANTICS, DOCUMENTS
from pipeline.fetch import fetch_url, sha256_file, write_sidecar
from pipeline.overlap import analyze_documents
from pipeline.paths import log_dir, private_db, public_db, raw_dir
from pipeline.store import connect
from pipeline.privacy import assess_row, public_allowed
from pipeline.store import PRIVATE_SCHEMA, PUBLIC_SCHEMA, rebuild

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "v2" / "sources.json"
OVERRIDES = ROOT / "registry" / "category_overrides.json"

logger = logging.getLogger("ledger")


def _vendor_key(vendor: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", vendor.upper())


def _line_id(sha: str, ordinal: int, raw: str) -> str:
    return hashlib.sha256(f"{sha}|{ordinal}|{raw}".encode()).hexdigest()[:24]


def _load_sources() -> list[dict[str, Any]]:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return list(payload["sources"])


def _ensure_raw(document: dict[str, Any]) -> dict[str, Any]:
    dest = raw_dir() / f"{document['sha256']}.pdf"
    sidecar = raw_dir() / f"{document['sha256']}.json"
    if dest.exists() and sha256_file(dest) == document["sha256"]:
        meta = {
            "ok": True,
            "status": 200,
            "content_type": "application/pdf",
            "byte_length": dest.stat().st_size,
            "sha256": document["sha256"],
            "cache": "reused",
        }
    else:
        logger.info("fetch %s", document["document_id"])
        meta = fetch_url(document["url"], dest)
        if not meta.get("ok"):
            return meta
        if meta["sha256"] != document["sha256"]:
            # Keep the new bytes under their own hash and do not index them as this document.
            actual = raw_dir() / f"{meta['sha256']}.pdf"
            if actual != dest:
                dest.replace(actual)
            meta["ok"] = False
            meta["error"] = "sha256_mismatch"
            meta["expected_sha256"] = document["sha256"]
            return meta
    meta["retrieved_at"] = datetime.now(timezone.utc).isoformat()
    write_sidecar(sidecar, {"document_id": document["document_id"], "url": document["url"], **meta})
    meta["path"] = str(dest)
    return meta


def _flags(row_flags: list[str]) -> str:
    return ",".join(row_flags)


def run_ingest(documents: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    documents = documents if documents is not None else DOCUMENTS
    sources = _load_sources()
    source_by_id = {row["source_id"]: row for row in sources}
    overrides = load_overrides(OVERRIDES if OVERRIDES.exists() else None)
    private = _open_private()
    public = rebuild(public_db(), PUBLIC_SCHEMA)
    summaries: list[dict[str, Any]] = []
    indexed_source_ids: set[str] = set()
    pending: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    for document in documents:
        source = source_by_id.get(document["source_id"], {})
        fetched = _ensure_raw(document)
        if not fetched.get("ok"):
            summaries.append({
                "document_id": document["document_id"],
                "source_id": document["source_id"],
                "ingestion_status": "fetch_failed",
                "error": fetched.get("error"),
                "http_status": fetched.get("status"),
                "indexed": False,
            })
            logger.info("fetch failed %s %s", document["document_id"], fetched.get("error"))
            continue
        adapter = ADAPTERS[document["adapter"]]
        try:
            parsed = adapter(fetched["path"])
        except Exception as error:  # noqa: BLE001 — quarantine one document, keep the run going
            logger.info("parse failed %s %s", document["document_id"], type(error).__name__)
            summaries.append({
                "document_id": document["document_id"],
                "source_id": document["source_id"],
                "ingestion_status": "parse_failed",
                "error": type(error).__name__,
                "indexed": False,
                "sha256": document["sha256"],
            })
            continue
        sha = document["sha256"]
        private.execute("DELETE FROM silver_lines WHERE sha256 = ?", (sha,))
        private.execute("DELETE FROM artifacts WHERE sha256 = ?", (sha,))
        private.execute(
            """INSERT INTO artifacts (sha256, document_id, source_id, url, content_type, byte_length, retrieved_at, parser_id, parser_version, active)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (sha, document["document_id"], document["source_id"], document["url"], fetched.get("content_type"),
             fetched.get("byte_length"), now, parsed.parser_id, parsed.parser_version),
        )
        private.execute(
            "UPDATE artifacts SET active = 0 WHERE document_id = ? AND sha256 != ?",
            (document["document_id"], sha),
        )
        private.execute(
            "UPDATE silver_lines SET active = 0 WHERE document_id = ? AND sha256 != ?",
            (document["document_id"], sha),
        )
        built = _build_rows(document, source, parsed, sha, overrides)
        pending.append({"document": document, "source": source, "fetched": fetched, "parsed": parsed, "sha": sha, "built": built})
        continue

    overlap = analyze_documents(_overlap_inputs(pending))
    for item in pending:
        built = item["built"]
        document = item["document"]
        sha = item["sha"]
        parsed = item["parsed"]
        fetched = item["fetched"]
        unresolved = overlap["unresolved_dates_by_doc"].get(document["document_id"], set())
        for row in built["silver"]:
            payload = row["public_payload"]
            if payload.get("check_date") in unresolved:
                payload["in_default_aggregate"] = 0
                flags = payload.get("flags") or ""
                payload["flags"] = ",".join(part for part in [flags, "overlap_unresolved"] if part)
            private.execute(
                """INSERT INTO silver_lines (line_id, sha256, document_id, active, vendor_raw, description_raw, amount_cents, check_number_raw, privacy_class, privacy_reasons, line_kind, payload_json)
                   VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["line_id"], sha, document["document_id"], row["vendor_raw"], row["description_raw"],
                 row["amount_cents"], row.get("check_number_raw"), row["privacy_class"],
                 ",".join(row["privacy_reasons"]), row["line_kind"], json.dumps(payload)),
            )
        indexed = built["reconciled"]
        default_rows = [row for row in built["public_rows"] if row.get("check_date") not in unresolved]
        held_rows = [row for row in built["public_rows"] if row.get("check_date") in unresolved]
        if indexed:
            indexed_source_ids.add(document["source_id"])
            for payload in default_rows:
                payload["in_default_aggregate"] = 1
                _insert_public_line(public, payload, fts=True)
            for payload in held_rows:
                payload["in_default_aggregate"] = 0
                _insert_public_line(public, payload, fts=False)
        summary = {
            "document_id": document["document_id"],
            "source_id": document["source_id"],
            "url": document["url"],
            "sha256": sha,
            "content_type": fetched.get("content_type"),
            "parser_id": parsed.parser_id,
            "parser_version": parsed.parser_version,
            "period_label_native": built["period_label_native"],
            "period_start": built["period_start"],
            "period_end": built["period_end"],
            "reconciliation_status": built["reconciliation_status"],
            "printed_total_cents": built["printed_total_cents"],
            "parsed_total_cents": built["parsed_total_cents"],
            "delta_cents": built["delta_cents"],
            "parsed_line_count": built["parsed_line_count"],
            "public_line_count": len(default_rows) if indexed else 0,
            "unresolved_overlap_count": len(held_rows) if indexed else 0,
            "printed_total_null_reason": built["printed_total_null_reason"],
            "parsed_total_null_reason": built["parsed_total_null_reason"],
            "parsed_outcome": built["parsed_outcome"],
            "delta_null_reason": built["delta_null_reason"],
            "withheld_count": built["withheld_count"],
            "revenue_excluded_count": built["revenue_excluded_count"],
            "warning_count": len(parsed.warnings),
            "indexed": indexed,
            "ingestion_status": "indexed_reconciled" if indexed else "parsed_not_indexed",
            "amount_semantics": AMOUNT_SEMANTICS,
            "manifest_membership": document.get("manifest"),
            "ocr_paper_capture": getattr(parsed, "ocr_paper_capture", False),
            "coverage_note": built["coverage_note"],
        }
        summaries.append(summary)
        public.execute(
            """INSERT INTO documents (
                document_id, source_id, url, sha256, content_type, parser_id, parser_version,
                period_label_native, period_start, period_end, reconciliation_status,
                printed_total_cents, printed_total_null_reason, parsed_total_cents, parsed_total_null_reason,
                parsed_outcome, delta_cents, delta_null_reason, parsed_line_count, public_line_count,
                withheld_count, revenue_excluded_count, warning_count, indexed, amount_semantics,
                manifest_membership, coverage_note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (summary["document_id"], summary["source_id"], summary["url"], sha, summary["content_type"],
             summary["parser_id"], summary["parser_version"], summary["period_label_native"], summary["period_start"],
             summary["period_end"], summary["reconciliation_status"], summary["printed_total_cents"],
             summary["printed_total_null_reason"], summary["parsed_total_cents"], summary["parsed_total_null_reason"],
             summary["parsed_outcome"], summary["delta_cents"], summary["delta_null_reason"], summary["parsed_line_count"],
             summary["public_line_count"], summary["withheld_count"], summary["revenue_excluded_count"],
             summary["warning_count"], 1 if indexed else 0, AMOUNT_SEMANTICS, summary["manifest_membership"],
             summary["coverage_note"]),
        )
        logger.info(
            "%s indexed=%s lines=%s public=%s delta=%s",
            document["document_id"], indexed, summary["parsed_line_count"], summary["public_line_count"], summary["delta_cents"],
        )

    _write_sources(public, sources, indexed_source_ids, summaries)
    _write_overlap_notes(public, summaries)
    for finding in overlap["findings"]:
        public.execute(
            """INSERT INTO overlap_findings (
                left_document_id, right_document_id, source_id, header_shared_dates, shared_check_date_count,
                rows_on_shared_header_dates, rows_on_shared_header_cents, verdict, recurring_different_date_keys,
                recurring_different_date_line_count, recurring_different_date_cents, included_in_default_total, note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (finding["left_document_id"], finding["right_document_id"], finding["source_id"], finding["header_shared_dates"],
             finding["shared_check_date_count"], finding["rows_on_shared_header_dates"], finding["rows_on_shared_header_cents"],
             finding["verdict"], finding["recurring_different_date_keys"], finding["recurring_different_date_line_count"],
             finding["recurring_different_date_cents"], finding["included_in_default_total"], finding["note"]),
        )
    private.commit()
    public.commit()
    private.close()
    public.close()
    report = {
        "generated_at": now,
        "amount_semantics": AMOUNT_SEMANTICS,
        "documents": summaries,
        "indexed_documents": sum(1 for row in summaries if row.get("indexed")),
        "public_lines": sum(int(row.get("public_line_count") or 0) for row in summaries),
        "public_amount_cents": _public_sum(),
        "overlap": overlap["findings"],
        "note": "public_amount_cents is the sum of screened lines in the default aggregate. It is not unique spend, not the printed report total, and not a metro census. Withheld rows and unresolved shared check dates are excluded. Reported AP or voucher amounts are not settlement proof.",
    }
    out = log_dir() / "ingest_summary.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _open_private():
    path = private_db()
    if not path.exists():
        return rebuild(path, PRIVATE_SCHEMA)
    connection = connect(path)
    row = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifacts'").fetchone()
    if row is None:
        connection.close()
        return rebuild(path, PRIVATE_SCHEMA)
    return connection


def _insert_public_line(public, payload: dict[str, Any], fts: bool) -> None:
    columns = list(payload.keys())
    public.execute(
        f"INSERT INTO lines ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
        [payload[column] for column in columns],
    )
    if fts:
        public.execute(
            """INSERT INTO lines_fts (line_id, vendor_raw, description_public, dac_raw, account_code_raw, entity_name)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (payload["line_id"], payload["vendor_raw"], payload["description_public"],
             payload.get("dac_raw") or "", payload.get("account_code_raw") or "", payload["entity_name"]),
        )


def _overlap_inputs(pending: list[dict[str, Any]]) -> list[dict[str, Any]]:
    documents = []
    for item in pending:
        rows = []
        for silver in item["built"]["silver"]:
            payload = silver["public_payload"]
            rows.append({
                "document_id": item["document"]["document_id"],
                "check_date": payload.get("check_date"),
                "amount_cents": payload.get("amount_cents"),
                "vendor": payload.get("vendor_raw"),
                "description": silver["description_raw"],
                "po": payload.get("po_raw"),
                "dac": payload.get("dac_raw"),
            })
        documents.append({
            "document_id": item["document"]["document_id"],
            "source_id": item["document"]["source_id"],
            "period_start": item["built"]["period_start"],
            "period_end": item["built"]["period_end"],
            "rows": rows,
        })
    return documents


def _adapter_family(source_id: str | None) -> str:
    families = {
        "susd_diligent_ap_report": "susd_ap_report_pdf",
        "husd_diligent_voucher_summary": "diligent_voucher_account_summary",
        "qcusd_diligent_voucher_summary": "diligent_voucher_account_summary",
        "pvusd_diligent_voucher_summary": "diligent_voucher_account_summary",
        "chandler_highbond_voucher_unverified": "diligent_voucher_account_summary",
        "gilbert_boarddocs_ap_voucher_detail": "boarddocs_pdf_attachment",
        "mesa_boarddocs_expense_warrant_summary": "boarddocs_pdf_attachment",
        "dysart_diligent_voucher_fund_totals": "diligent_voucher_fund_totals",
        "govly_susd_po_awards_secondary": "govly_public_award_html",
        "ade_active_leas_universe": "ade_xlsx_download",
        "azdor_2026_directory": "azdor_pdf_directory",
        "maricopa_county_board_directory": "county_directory_html",
        "pinal_county_school_directory": "county_directory_html",
    }
    return families.get(source_id or "", "not_assigned")


def _public_sum() -> int:
    import sqlite3
    connection = sqlite3.connect(public_db())
    row = connection.execute("SELECT COALESCE(SUM(amount_cents),0) FROM lines WHERE in_default_aggregate = 1").fetchone()
    connection.close()
    return int(row[0])


def _build_rows(document, source, parsed, sha: str, overrides) -> dict[str, Any]:
    entity = source.get("entity_name") or document["source_id"]
    entity_type = source.get("entity_type") or "public_district"
    admin_county = source.get("county_admin_legacy_unverified") or ""
    ctds = source.get("lea_ctds") or ""
    silver: list[dict[str, Any]] = []
    public_rows: list[dict[str, Any]] = []
    withheld = 0
    revenue = 0
    if document["adapter"] == "susd_ap_report_pdf":
        printed = parsed.report_total_cents
        printed_reason = None if printed is not None else "printed_total_not_found"
        if parsed.lines:
            parsed_total = sum(line.amount_cents or 0 for line in parsed.lines)
            parsed_reason = None
            parsed_outcome = "parsed_lines"
        else:
            parsed_total = None
            parsed_reason = "parser_emitted_no_lines"
            parsed_outcome = "parsed_zero"
        if printed is None or parsed_total is None:
            delta = None
            delta_reason = printed_reason or parsed_reason
        else:
            delta = parsed_total - printed
            delta_reason = None
        reconciled = delta == 0 and printed is not None
        period_label = parsed.period_label_native
        period_start = parsed.period_start
        period_end = parsed.period_end
        document_class = "paid_ap_ledger_report"
        for line in parsed.lines:
            privacy, reasons = assess_row(line.vendor_raw, line.description_raw)
            kind = "expenditure"
            if not public_allowed(privacy):
                withheld += 1
            payload = _public_payload(
                document, source, sha, line.ordinal, line.raw_line, entity, entity_type, admin_county, ctds,
                line.amount_cents or 0, line.vendor_raw, line.description_raw, line.dac_raw, None, line.po_raw,
                line.check_date, "explicit_check_date_on_ap_row" if line.check_date else "check_date_unparsed",
                None, None, None, None, period_label, period_start, period_end, document_class,
                line.flags, privacy, line.page, line.y, False, overrides,
            )
            silver.append({
                "line_id": payload["line_id"], "vendor_raw": line.vendor_raw, "description_raw": line.description_raw,
                "amount_cents": line.amount_cents, "check_number_raw": None, "privacy_class": privacy,
                "privacy_reasons": reasons, "line_kind": kind, "public_payload": payload,
            })
            if reconciled and public_allowed(privacy):
                public_rows.append(payload)
        status = "matched_printed_total" if reconciled else "discrepancy_not_indexed"
    else:
        batch_totals = [batch.printed_total_cents for batch in parsed.batches]
        if not parsed.batches:
            printed = None
            printed_reason = "no_printed_total_extracted" if getattr(parsed, "ocr_paper_capture", False) else "no_grand_total_found"
        elif any(item is None for item in batch_totals):
            printed = None
            printed_reason = "a_batch_total_was_not_extracted"
        else:
            printed = sum(batch_totals)
            printed_reason = None
        if parsed.lines:
            parsed_total = sum(line.amount_cents for line in parsed.lines)
            parsed_reason = None
            parsed_outcome = "parsed_lines"
        else:
            parsed_total = None
            parsed_reason = "parser_emitted_no_lines"
            parsed_outcome = "parsed_zero"
        deltas = [batch.delta_cents for batch in parsed.batches]
        reconciled = bool(parsed.batches) and all(delta == 0 for delta in deltas) and printed is not None and not parsed.ocr_paper_capture
        if parsed.ocr_paper_capture:
            reconciled = False
            status = "ocr_paper_capture_not_indexed"
            if parsed_outcome == "parsed_lines":
                parsed_outcome = "parsed_unreconciled"
        elif reconciled:
            status = "matched_printed_batch_totals"
        else:
            status = "discrepancy_or_incomplete_not_indexed"
            if parsed_outcome == "parsed_lines":
                parsed_outcome = "parsed_unreconciled"
        period_label = None
        period_start = None
        period_end = None
        document_class = "voucher_account_summary"
        if printed is None or parsed_total is None:
            delta = None
            delta_reason = printed_reason or parsed_reason
        else:
            delta = parsed_total - printed
            delta_reason = None
        if parsed.ocr_paper_capture and not parsed.lines and printed is None:
            printed_reason = "no_printed_total_extracted_from_ocr_scan"
            delta_reason = printed_reason
            parsed_outcome = "parsed_zero"
        for line in parsed.lines:
            privacy, reasons = assess_row(line.vendor_raw, line.description_raw)
            kind = "non_spending_revenue" if "non_spending_revenue_label" in line.flags else "expenditure"
            if kind != "expenditure":
                revenue += 1
            elif not public_allowed(privacy):
                withheld += 1
            check_reason = "voucher_batch_date_is_not_a_check_date"
            batch_date = None if line.date_conflict else line.voucher_batch_date
            payload = _public_payload(
                document, source, sha, line.ordinal, line.raw_line, entity, entity_type, admin_county, ctds,
                line.amount_cents, line.vendor_raw, line.description_raw, None, line.account_code_raw, None,
                None, check_reason, batch_date, line.voucher_batch_date_raw, line.voucher_batch_number,
                line.fiscal_year_label_native, line.fiscal_year_label_native, None, None, document_class,
                line.flags, privacy, line.page, line.y, line.date_conflict, overrides,
            )
            silver.append({
                "line_id": payload["line_id"], "vendor_raw": line.vendor_raw, "description_raw": line.description_raw,
                "amount_cents": line.amount_cents, "check_number_raw": line.check_number_raw,
                "privacy_class": privacy, "privacy_reasons": reasons, "line_kind": kind, "public_payload": payload,
            })
            if reconciled and kind == "expenditure" and public_allowed(privacy):
                public_rows.append(payload)
    return {
        "silver": silver,
        "public_rows": public_rows,
        "reconciled": reconciled,
        "reconciliation_status": status,
        "printed_total_cents": printed,
        "printed_total_null_reason": printed_reason,
        "parsed_total_cents": parsed_total,
        "parsed_total_null_reason": parsed_reason,
        "parsed_outcome": parsed_outcome,
        "delta_cents": delta,
        "delta_null_reason": delta_reason,
        "parsed_line_count": len(silver),
        "withheld_count": withheld,
        "revenue_excluded_count": revenue,
        "period_label_native": period_label,
        "period_start": period_start,
        "period_end": period_end,
        "coverage_note": "Observed document window only. Not continuous coverage of the fiscal year.",
    }


def _public_payload(document, source, sha, ordinal, raw, entity, entity_type, admin_county, ctds,
                    amount, vendor, description, dac, account, po, check_date, check_reason,
                    batch_date, batch_date_raw, batch_number, fiscal, period_label, period_start, period_end,
                    document_class, flags, privacy, page, y, date_conflict, overrides) -> dict[str, Any]:
    line_id = _line_id(sha, ordinal, raw)
    category = apply_override(classify_text(description, account), line_id, overrides)
    return {
        "line_id": line_id,
        "document_id": document["document_id"],
        "source_id": document["source_id"],
        "entity_name": entity,
        "entity_type": entity_type,
        "admin_county": admin_county,
        "lea_ctds": ctds,
        "amount_cents": amount,
        "currency": "USD",
        "vendor_raw": vendor,
        "vendor_key": _vendor_key(vendor),
        "description_public": description,
        "dac_raw": dac,
        "account_code_raw": account,
        "po_raw": po,
        "check_date": check_date,
        "check_date_null_reason": None if check_date else check_reason,
        "voucher_batch_date": batch_date,
        "voucher_batch_date_raw": batch_date_raw,
        "voucher_batch_number": batch_number,
        "fiscal_year_label_native": fiscal,
        "period_label_native": period_label,
        "period_start": period_start,
        "period_end": period_end,
        "document_class": document_class,
        "amount_semantics": AMOUNT_SEMANTICS,
        "category": category["category"],
        "category_confidence": category["category_confidence"],
        "category_ruleset": category["category_ruleset"],
        "category_evidence": category["category_evidence"],
        "privacy_class": privacy,
        "source_url": document["url"],
        "source_page": page,
        "source_row": ordinal,
        "source_locator": f"page {page} y {y}",
        "flags": _flags(flags),
        "date_conflict": 1 if date_conflict else 0,
        "in_default_aggregate": 1,
    }


def _write_sources(public, sources, indexed_source_ids, summaries) -> None:
    status_by_source: dict[str, str] = {}
    for row in summaries:
        current = status_by_source.get(row["source_id"])
        if row.get("indexed"):
            status_by_source[row["source_id"]] = "indexed_reconciled"
        elif current != "indexed_reconciled":
            status_by_source[row["source_id"]] = row.get("ingestion_status") or "not_indexed"
    for source in sources:
        source_id = source.get("source_id")
        public.execute(
            """INSERT INTO sources (
                source_id, entity_name, entity_type, source_status, access_status, line_item_confirmed,
                admin_county, lea_ctds, service_counties, service_counties_null_reason, document_class,
                adapter_family, discovery_state, ingestion_status, evidence_level
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                source_id,
                source.get("entity_name"),
                source.get("entity_type"),
                source.get("source_status"),
                source.get("access_status"),
                1 if source.get("line_item_confirmed") else 0,
                source.get("county_admin_legacy_unverified"),
                source.get("lea_ctds"),
                None,
                source.get("service_counties_null_reason"),
                source.get("document_class"),
                _adapter_family(source_id),
                "not_run_this_build",
                status_by_source.get(source_id, "not_attempted_this_run"),
                source.get("evidence_level"),
            ),
        )


def _write_overlap_notes(public, summaries) -> None:
    windows = [
        row for row in summaries
        if row.get("period_start") and row.get("period_end") and row.get("indexed")
    ]
    windows.sort(key=lambda row: (row["source_id"], row["period_start"]))
    for left, right in zip(windows, windows[1:]):
        if left["source_id"] != right["source_id"]:
            continue
        if left["period_end"] >= right["period_start"]:
            note = (
                f"{left['document_id']} ({left['period_start']} to {left['period_end']}) and "
                f"{right['document_id']} ({right['period_start']} to {right['period_end']}) share a boundary or overlap. "
                "Lines were not auto-deduplicated. A shared boundary date is not proof of double counting."
            )
            public.execute("INSERT INTO coverage_notes (source_id, note) VALUES (?, ?)", (left["source_id"], note))
