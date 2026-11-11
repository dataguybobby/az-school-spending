"""Living data dictionary. Facts come from the public snapshot and the registry.

Regenerate with ``python3 -m pipeline dictionary`` after an ingest. Tests compare
the committed JSON to this function so a new source, column, or total cannot
drift silently.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pipeline.documents import AMOUNT_SEMANTICS, DOCUMENTS
from pipeline.paths import public_db

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "v2" / "sources.json"
OUT_REGISTRY = ROOT / "registry" / "data_dictionary.json"
OUT_WEB = ROOT / "web" / "src" / "data" / "dictionary.json"

SEARCHED_NOT_INGESTED = (
    "dysart_diligent_voucher_fund_totals",
    "dvusd_agenda_voucher_approval_partial",
    "scout_tempe_union",
)


def build_dictionary(database: Path | None = None) -> dict[str, object]:
    path = database or public_db()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    by_source = {row["source_id"]: row for row in registry["sources"]}
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    documents = [_document(connection, row) for row in connection.execute(
        """SELECT d.*, s.entity_name, s.entity_type, s.document_class, s.admin_county,
                  s.source_status, s.access_status, s.ingestion_status
           FROM documents d
           LEFT JOIN sources s ON s.source_id = d.source_id
           ORDER BY d.indexed DESC, s.entity_name, d.document_id"""
    )]
    source_rows = list(connection.execute(
        "SELECT * FROM sources ORDER BY entity_name, source_id"
    ))
    default_count, default_cents = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_cents),0) FROM lines WHERE in_default_aggregate = 1"
    ).fetchone()
    before_window = connection.execute(
        """SELECT COUNT(*) FROM lines
           WHERE in_default_aggregate = 1 AND (
             (check_date IS NOT NULL AND check_date < '2024-07-01')
             OR (voucher_batch_date IS NOT NULL AND voucher_batch_date < '2024-07-01')
           )"""
    ).fetchone()[0]
    schema = {
        "public_tables": _tables(connection),
        "private_tables_not_in_this_snapshot": _private_tables(),
        "note": "The web app opens only data/public/ledger.sqlite. data/private is gitignored and is not a public table.",
    }
    connection.close()
    scope = registry.get("scope") or {}
    return {
        "product": "AZ School Spending",
        "publisher": "Phoenix Dataworks",
        "official_government_site": False,
        "geography": (
            "Phoenix metro in this registry means administrative Maricopa and Pinal counties. "
            "Service geography is not verified from DAC or account text. "
            "This is not statewide coverage and not every Phoenix school."
        ),
        "amount_semantics": AMOUNT_SEMANTICS,
        "scope": {
            "window_start": scope.get("window_start"),
            "window_basis": scope.get("window_basis"),
            "claim_all": scope.get("claim_all"),
            "window_enforcement": (
                "school year 2025 in this project means a transaction date on or after 2024-07-01. "
                "The registry records that start. The ingest does not delete a public line only because its date is earlier. "
                f"In this public snapshot, screened lines with a check date or voucher batch date before 2024-07-01: {before_window}."
            ),
        },
        "snapshot": {
            "public_database": "data/public/ledger.sqlite",
            "screened_line_count": int(default_count),
            "screened_amount_cents": int(default_cents),
            "wording": (
                "This figure is the sum of screened public lines on that date basis. "
                "It is not unique spend, not the printed report total, not proof a payment settled, "
                "and not a census of districts or of Arizona schools."
            ),
        },
        "schema": schema,
        "documents": documents,
        "sources": [_source(row, by_source, documents) for row in source_rows],
        "transformations": _transformations(),
        "aggregations": _aggregations(),
        "enrollment": _enrollment(),
    }


def write_dictionary(payload: dict[str, object] | None = None) -> tuple[Path, Path]:
    body = json.dumps(payload or build_dictionary(), indent=2, ensure_ascii=False) + "\n"
    OUT_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    OUT_WEB.parent.mkdir(parents=True, exist_ok=True)
    OUT_REGISTRY.write_text(body, encoding="utf-8")
    OUT_WEB.write_text(body, encoding="utf-8")
    return OUT_REGISTRY, OUT_WEB


def _document(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    document_id = row["document_id"]
    fiscal = [
        item[0]
        for item in connection.execute(
            """SELECT DISTINCT fiscal_year_label_native FROM lines
               WHERE document_id = ? AND fiscal_year_label_native IS NOT NULL
               ORDER BY 1""",
            (document_id,),
        )
    ]
    period = row["period_label_native"]
    if period is None and fiscal:
        period = "fiscal year label on public lines: " + ", ".join(fiscal)
    period_null_reason = None
    if period is None:
        period_null_reason = (
            "No native period label is stored on this document, and it has no public lines to read a fiscal-year label from."
        )
    return {
        "document_id": document_id,
        "source_id": row["source_id"],
        "district": row["entity_name"],
        "admin_county": row["admin_county"],
        "document_class": row["document_class"],
        "official_url": row["url"],
        "sha256": row["sha256"],
        "period_as_printed_or_stored": period,
        "period_null_reason": period_null_reason,
        "period_start": row["period_start"],
        "period_end": row["period_end"],
        "reconciliation_status": row["reconciliation_status"],
        "parsed_outcome": row["parsed_outcome"],
        "in_public_index": bool(row["indexed"]),
        "printed_total_cents": row["printed_total_cents"],
        "printed_total_null_reason": row["printed_total_null_reason"],
        "public_line_count": row["public_line_count"],
        "withheld_count": row["withheld_count"],
        "amount_semantics": row["amount_semantics"],
        "coverage_note": row["coverage_note"],
    }


def _source(row: sqlite3.Row, registry: dict[str, dict], documents: list[dict[str, object]]) -> dict[str, object]:
    source_id = row["source_id"]
    meta = registry.get(source_id) or {}
    url = meta.get("document_or_page_url") or meta.get("discovery_url")
    own_documents = [item for item in documents if item["source_id"] == source_id]
    in_index = any(item["in_public_index"] for item in own_documents)
    status = "in_public_index" if in_index else _registry_status(row, source_id, own_documents)
    return {
        "source_id": source_id,
        "district_or_dataset": row["entity_name"],
        "entity_type": row["entity_type"],
        "admin_county": row["admin_county"],
        "service_counties": row["service_counties"],
        "service_counties_null_reason": row["service_counties_null_reason"],
        "document_class": row["document_class"],
        "source_status": row["source_status"],
        "access_status": row["access_status"],
        "ingestion_status": row["ingestion_status"],
        "dictionary_status": status,
        "official_url": url,
        "official_url_null_reason": None if url else "no document_or_page_url or discovery_url in registry/v2/sources.json",
        "sha256": [item["sha256"] for item in own_documents] or None,
        "sha256_null_reason": None if own_documents else "no fetched document in the public snapshot, so no content hash is stored",
        "in_public_index": in_index,
        "documents": [item["document_id"] for item in own_documents],
    }


def _registry_status(row: sqlite3.Row, source_id: str, documents: list[dict[str, object]]) -> str:
    if documents and not any(item["in_public_index"] for item in documents):
        return "parsed_unreconciled" if any(item["parsed_outcome"] == "parsed_unreconciled" for item in documents) else "fetched_not_indexed"
    if source_id in SEARCHED_NOT_INGESTED:
        return "searched_not_ingested"
    if row["source_status"] == "candidate_unsearched":
        return "not_searched"
    if row["ingestion_status"] in (None, "not_attempted_this_run"):
        return "not_ingested"
    return str(row["ingestion_status"])


def _tables(connection: sqlite3.Connection) -> list[dict[str, object]]:
    tables = []
    for (name,) in connection.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({name})")]
        tables.append({"name": name, "columns": columns})
    return tables


def _private_tables() -> list[dict[str, object]]:
    return [
        {
            "name": "artifacts",
            "where": "data/private/ledger.sqlite",
            "columns": ["sha256", "document_id", "source_id", "url", "content_type", "byte_length", "retrieved_at", "parser_id", "parser_version", "active"],
            "public": False,
        },
        {
            "name": "silver_lines",
            "where": "data/private/ledger.sqlite",
            "columns": ["line_id", "sha256", "document_id", "active", "vendor_raw", "description_raw", "amount_cents", "check_number_raw", "privacy_class", "privacy_reasons", "line_kind", "payload_json"],
            "public": False,
            "note": "check_number_raw stays here. It is not a public column. Withheld personal rows stay here. They are not a payroll register.",
        },
    ]


def _transformations() -> list[dict[str, object]]:
    return [
        {
            "id": "fetch",
            "step": "Download the official URL and require the SHA-256 in pipeline/documents.py. A different hash is stored under its own name and is not indexed as this document.",
            "code": "pipeline/ingest.py _ensure_raw",
        },
        {
            "id": "parse",
            "step": "Text-native Scottsdale AP PDFs use susd_ap_report_pdf. Diligent voucher account summaries use diligent_voucher_account_summary. Paper-capture scans use the OCR layout parser. A cover-page fund total is not a vendor line. A P-card merchant and its clearing-account payee stay on one line.",
            "code": "pipeline/adapters",
        },
        {
            "id": "reconcile",
            "step": "A document enters the public index only when parsed detail lines match the printed total on that same document. Paradise Valley stays out until a printed total can be reconciled. An unindexed file is not zero spending.",
            "code": "pipeline/ingest.py _build_rows",
        },
        {
            "id": "dates",
            "step": (
                "Check date, voucher batch date, and the native fiscal-year label are separate columns. "
                "A voucher batch date is not copied into check_date. "
                "School year 2025 in the registry means a transaction on or after 2024-07-01; the ingest does not drop lines solely for an earlier date. "
                "OCR batch dates are flagged ocr_batch_date_unreviewed and voucher_batch_date is null until reviewed. "
                "The raw OCR string may remain in voucher_batch_date_raw and is not a transaction date."
            ),
            "code": "pipeline/adapters/voucher_ocr.py",
        },
        {
            "id": "cents",
            "step": "Amounts are integer cents from the printed dollars. Floats are not used for money.",
            "code": "pipeline/money.py parse_cents",
        },
        {
            "id": "amount_semantics",
            "step": (
                f"Every public line is tagged {AMOUNT_SEMANTICS}. "
                "That is a reported AP or vouchered amount, not proof a payment settled. "
                "po_raw may sit on an AP line. The public sum uses amount_cents of that line, not a separate purchase-order commitment total. "
                "Govly purchase-order awards are excluded_secondary_PO and are not public lines."
            ),
            "code": "pipeline/documents.py AMOUNT_SEMANTICS",
        },
        {
            "id": "privacy",
            "step": (
                "A row is public only when the payee is classed safe_business_vendor and the vendor plus description have no email, phone, street address, "
                "long digit identifier, reimbursement or student context, authorized-user text, IEP or ESY, or medicaid, diagnosis, or prescription language. "
                "Personal and unknown payees are quarantined in the private silver table. The public table omits the row. Hiding a column is not the control. "
                "This is an AP and voucher extract, not a payroll register. Public lines generally do not include salaries. Withheld personal lines are not a payroll substitute."
            ),
            "code": "pipeline/privacy.py assess_row",
        },
        {
            "id": "default_aggregate",
            "step": "Indexed public lines start with in_default_aggregate = 1. A line whose check date sits on an unresolved shared-date overlap is set to 0 and left out of the default total, charts, and CSV.",
            "code": "pipeline/ingest.py overlap",
        },
        {
            "id": "categories_and_items",
            "step": (
                "Categories use phoenix-k12-neutral-2026.11.11. Account titles are stronger than item text. Unclassified is the default. Metered natural gas, water, sewer, and electricity are utilities. "
                "Amazon is a vendor, not a category. Categories are not USFR codes. "
                "Item groups are reviewed description phrases with a label, evidence span, method, and confidence. A not-to-exceed figure in the text is not the line amount."
            ),
            "code": "pipeline/classify.py and pipeline/items.py",
        },
    ]


def _aggregations() -> list[dict[str, object]]:
    return [
        {
            "id": "default_screened_total",
            "grain": "one number for the lines in the current filter",
            "filter": "in_default_aggregate = 1, plus the selected date basis and any search filters",
            "date_basis": "either, unless the page selects check date or voucher batch date",
            "public_wording": "This figure is the sum of screened public lines on that date basis. It is not unique spend, not the printed report total, not proof a payment settled, and not a census of districts or of Arizona schools.",
            "surface": "web/src/app/page.tsx",
        },
        {
            "id": "month_chart",
            "grain": "calendar month of the selected date basis",
            "filter": "in_default_aggregate = 1 and the month expression is not null",
            "date_basis": "check date, voucher batch date, or check date when present otherwise voucher batch date",
            "public_wording": "A month with no bar was not indexed, not recorded as zero.",
            "surface": "web/src/app/page.tsx",
        },
        {
            "id": "category_chart",
            "grain": "inferred category",
            "filter": "in_default_aggregate = 1 and the page filters",
            "date_basis": "same as the page filter; the chart does not relabel the basis",
            "public_wording": "Inferred category, not a budget code",
            "surface": "web/src/app/page.tsx",
        },
        {
            "id": "vendor_treemap",
            "grain": "vendor_key, top 8 by amount_cents, remainder labeled Other screened vendors",
            "filter": "in_default_aggregate = 1 and the page filters",
            "date_basis": "same as the page filter",
            "public_wording": "Area is the sum of screened public lines for that vendor. Other screened vendors are grouped. This is not unique spend and not a printed report total.",
            "surface": "web/src/components/treemap.tsx",
        },
        {
            "id": "district_comparison",
            "grain": "entity_name on the indexed document",
            "filter": "in_default_aggregate = 1 and the page filters",
            "date_basis": "same as the page filter",
            "public_wording": "Each bar is the screened public lines from the documents ingested for that district. Districts are not complete, not on the same calendar, and not comparable coverage. A missing district was not indexed. This is not a ranking of all Phoenix spending and not a share of any population.",
            "surface": "web/src/components/district-bars.tsx",
        },
        {
            "id": "story_cards",
            "grain": "two fixed public lines, not a ranked sample",
            "filter": "in_default_aggregate = 1 AND ((description_public = '24 pack slow rise stress balls' AND amount_cents = 2063) OR (description_public = 'Tisaindor 100PCS Panda Stickers' AND amount_cents = 6469))",
            "date_basis": "the line's own check date or voucher batch date, labeled on the card",
            "public_wording": "Each card is one screened public line. It is not a finding, not proof a payment settled, and not the whole vendor or district.",
            "surface": "web/src/components/story-cards.tsx",
        },
        {
            "id": "item_group",
            "grain": "item_label from a reviewed description phrase",
            "filter": "in_default_aggregate = 1 AND item_label IS NOT NULL, plus the selected date basis",
            "date_basis": "either, unless the groups page selects check date or voucher batch date",
            "public_wording": "They are sums of screened public lines, not unique spend, not printed report totals, and not complete district or statewide coverage.",
            "surface": "web/src/app/explore/page.tsx",
        },
        {
            "id": "vendor_group",
            "grain": "vendor_key; display name is the vendor_raw that occurs most often",
            "filter": "in_default_aggregate = 1 and the selected date basis",
            "date_basis": "either, unless the groups page selects check date or voucher batch date",
            "public_wording": "This is not unique spend, not a printed report total, and not complete coverage of that vendor or of any district.",
            "surface": "web/src/app/explore/vendors/[key]/page.tsx",
        },
        {
            "id": "fts_search",
            "grain": "public line",
            "filter": "in_default_aggregate = 1 AND line_id IN (SELECT line_id FROM lines_fts WHERE lines_fts MATCH ?)",
            "date_basis": "same as the page filter",
            "public_wording": "Description, vendor, or account",
            "surface": "web/src/app/page.tsx",
        },
        {
            "id": "csv_export",
            "grain": "public line, at most 5000 rows",
            "filter": "the same where() clause as the spending page, including in_default_aggregate = 1",
            "date_basis": "the basis query parameter, defaulting to either",
            "public_wording": "Download CSV",
            "surface": "web/src/app/page.tsx",
        },
    ]


def _enrollment() -> dict[str, object]:
    return {
        "source_id": "ade_october_1_enrollment",
        "official_url": "https://www.azed.gov/accountability-research/data",
        "what_it_is": "ADE Accountability October 1 enrollment, LEA or district and school. This is not ADM.",
        "status": "not_fetched",
        "http_status": 403,
        "headcount": None,
        "null_reason": "http_403_cloudflare_challenge",
        "note": (
            "An ordinary GET of the official page returned HTTP 403 and a Cloudflare challenge. "
            "That response was not bypassed. No enrollment file was downloaded and no headcount was invented. "
            "A per-enrolled-student figure is not on the site. If a later fetch succeeds, it must be year-matched "
            "and labeled as reported amount in this index per enrolled student, not total cost per pupil. "
            "Salaries are not in this AP extract, and the index is not full-district coverage."
        ),
    }
