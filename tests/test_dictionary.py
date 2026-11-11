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
        "october1_enrollment_comparison",
        "october1_enrollment_series",
        "printed_category_pies",
        "spend_and_enrollment_lines",
    } <= ids
    for row in payload["aggregations"]:
        surface = (WEB / row["surface"].removeprefix("web/src/")).read_text(encoding="utf-8")
        assert row["public_wording"] in surface or _wording_parts_present(row["public_wording"], surface)
        assert "in_default_aggregate" in row["filter"] or row["id"] in {"story_cards", "october1_enrollment_series"}


def test_enrollment_is_official_october_1_not_a_blocked_fetch():
    enrollment = build_dictionary()["enrollment"]
    assert enrollment["status"] == "ingested"
    assert enrollment["http_status"] is None
    assert enrollment["null_reason"] is None
    assert enrollment["measure"] == "october_1_headcount"
    assert "not_fetched" not in json.dumps(enrollment)
    assert "http_403" not in json.dumps(enrollment)
    assert "azed.gov/accountability-research/data" in enrollment["official_url"]
    assert enrollment["per_student_label"] == "reported amount in this index per enrolled student"
    assert "2025-07-01 through 2026-06-30" in enrollment["year_match_rule"]
    assert enrollment["coverage_window_start"] == "2024-07-01"
    assert enrollment["lea_row_count"] == 11004
    assert enrollment["suppressed_asterisk_count"] == 265
    assert enrollment["blank_total_count"] == 6
    by_district = {(row["district"], row["status"]): row for row in enrollment["comparisons"]}
    scottsdale = by_district[("Scottsdale Unified School District #48", "reported_per_enrolled_student")]
    assert scottsdale["school_year"] == "2025-2026"
    assert scottsdale["october_1_enrollment"] == 20180
    assert scottsdale["screened_amount_cents"] == 1510301067
    assert scottsdale["reported_cents_per_enrolled_student"] == 74841
    higley = by_district[("Higley Unified School District No. 60", "reported_per_enrolled_student")]
    assert higley["school_year"] == "2024-2025"
    assert higley["october_1_enrollment"] == 12351
    queen = by_district[("Queen Creek Unified District #95", "no_enrollment_workbook")]
    assert queen["school_year"] == "2026-2027"
    assert queen["october_1_enrollment"] is None
    assert queen["reported_cents_per_enrolled_student"] is None
    chandler = by_district[("Chandler Unified School District #80", "no_dated_spending")]
    assert chandler["school_year"] is None
    assert chandler["reported_cents_per_enrolled_student"] is None
    paradise = by_district[("Paradise Valley Unified School District", "not_in_spending_index")]
    assert paradise["screened_amount_cents"] is None
    early = [
        row for row in enrollment["focus_series"]["not_comparable_2010_2011_through_2016_2017"]
        if row["focus_district"] == "Scottsdale Unified" and row["school_year"] == "2010-2011"
    ]
    assert sorted(row["october_1_enrollment"] for row in early) == [1, 2, 26210]
    assert sum(row["october_1_enrollment"] for row in early if row["lea_id_matches_known_entity_id"]) == 26210


def _wording_parts_present(wording: str, surface: str) -> bool:
    parts = [part.strip() for part in wording.split(".") if len(part.strip()) > 40]
    return bool(parts) and all(part in surface for part in parts)
