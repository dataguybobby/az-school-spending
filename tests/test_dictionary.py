"""The committed dictionary must match the public snapshot and the code."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.dictionary import OUT_REGISTRY, OUT_WEB, SEARCHED_NOT_INGESTED, build_dictionary
from pipeline.documents import DOCUMENTS
from pipeline.store import PUBLIC_SCHEMA

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "src"


def test_committed_dictionary_matches_the_generator():
    fresh = build_dictionary()
    assert json.loads(OUT_REGISTRY.read_text(encoding="utf-8")) == fresh
    assert json.loads(OUT_WEB.read_text(encoding="utf-8")) == fresh


def test_every_fetch_document_keeps_its_url_and_hash():
    by_id = {row["document_id"]: row for row in build_dictionary()["documents"]}
    for document in DOCUMENTS:
        row = by_id[document["document_id"]]
        assert row["official_url"] == document["url"]
        assert row["sha256"] == document["sha256"]


def test_paradise_valley_stays_unindexed_and_the_three_searches_are_not_ledgers():
    payload = build_dictionary()
    paradise = next(row for row in payload["documents"] if row["document_id"] == "pvusd_fy26_vouchers_scan")
    assert paradise["in_public_index"] is False
    assert paradise["parsed_outcome"] == "parsed_unreconciled"
    assert paradise["printed_total_cents"] is None
    sources = {row["source_id"]: row for row in payload["sources"]}
    for source_id in SEARCHED_NOT_INGESTED:
        assert sources[source_id]["in_public_index"] is False
        assert sources[source_id]["dictionary_status"] == "searched_not_ingested"
    assert sources["pvusd_diligent_voucher_summary"]["dictionary_status"] == "parsed_unreconciled"


def test_schema_and_default_total_come_from_the_public_database():
    payload = build_dictionary()
    tables = {row["name"]: row["columns"] for row in payload["schema"]["public_tables"]}
    assert "check_number" not in tables["lines"]
    assert "check_number_raw" not in tables["lines"]
    assert "in_default_aggregate" in tables["lines"]
    for name in ("sources", "documents", "lines", "overlap_findings"):
        assert name in PUBLIC_SCHEMA
        assert name in tables
    assert payload["snapshot"]["screened_line_count"] > 0
    assert payload["snapshot"]["screened_amount_cents"] > 0
    assert "not unique spend" in payload["snapshot"]["wording"]
    assert "AZ schools spent" not in json.dumps(payload)


def test_aggregation_wording_is_still_on_the_page_that_claims_it():
    payload = build_dictionary()
    ids = {row["id"] for row in payload["aggregations"]}
    assert {
        "default_screened_total",
        "month_chart",
        "category_chart",
        "vendor_treemap",
        "district_comparison",
        "story_cards",
        "item_group",
        "vendor_group",
        "fts_search",
        "csv_export",
    } <= ids
    for row in payload["aggregations"]:
        surface = (WEB / row["surface"].removeprefix("web/src/")).read_text(encoding="utf-8")
        assert row["public_wording"] in surface or _wording_parts_present(row["public_wording"], surface)
        assert "in_default_aggregate" in row["filter"] or row["id"] == "story_cards"


def test_enrollment_was_not_invented():
    enrollment = build_dictionary()["enrollment"]
    assert enrollment["status"] == "not_fetched"
    assert enrollment["http_status"] == 403
    assert enrollment["headcount"] is None
    assert "azed.gov/accountability-research/data" in enrollment["official_url"]


def _wording_parts_present(wording: str, surface: str) -> bool:
    parts = [part.strip() for part in wording.split(".") if len(part.strip()) > 40]
    return bool(parts) and all(part in surface for part in parts)
