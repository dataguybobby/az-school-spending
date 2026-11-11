"""Official ADE October 1 enrollment, kept beside the screened spending index.

The CSV extracts in ``registry/ade/october1`` are the counts. Asterisks and blank
totals stay null. This module does not change line amounts.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADE_DIR = ROOT / "registry" / "ade" / "october1"
LEA_CSV = ADE_DIR / "enrollment_october1_lea.csv"
FOCUS_CSV = ADE_DIR / "enrollment_october1_focus_leas.csv"
SOURCES_JSON = ADE_DIR / "sources.json"
INDEX_LEAS_JSON = ADE_DIR / "index_leas.json"

OFFICIAL_URL = "https://www.azed.gov/accountability-research/data"
PER_STUDENT_LABEL = "reported amount in this index per enrolled student"
COMPARABLE_FIRST_YEAR = 2017

LEA_FIELDS = (
    "school_year_official",
    "fiscal_year_as_printed",
    "lea_name",
    "lea_id_as_printed",
    "lea_id_header_as_printed",
    "total_oct1_enrollment",
    "total_as_printed",
    "suppression_or_null_reason",
    "row_scope",
    "lea_grouping_basis",
    "same_basis_as_2017_18_plus_lea_tab",
    "source_file",
    "source_tab",
    "source_row",
)
FOCUS_FIELDS = (
    "focus_district",
    "school_year_official",
    "lea_name",
    "lea_id_as_printed",
    "total_oct1_enrollment",
    "total_as_printed",
    "suppression_or_null_reason",
    "focus_note",
    "same_basis_as_2017_18_plus_lea_tab",
    "lea_id_matches_known_entity_id",
    "source_file",
    "source_tab",
    "source_row",
)

SCHOOL_YEAR_CASE = """CASE
    WHEN substr(tx_date, 6, 5) >= '07-01'
      THEN substr(tx_date, 1, 4) || '-' || (CAST(substr(tx_date, 1, 4) AS INTEGER) + 1)
    ELSE (CAST(substr(tx_date, 1, 4) AS INTEGER) - 1) || '-' || substr(tx_date, 1, 4)
  END"""

ENROLLMENT_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS october1_extracts (
  extract_id TEXT PRIMARY KEY,
  relative_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  row_count INTEGER
);
CREATE TABLE IF NOT EXISTS october1_workbooks (
  school_year TEXT PRIMARY KEY,
  original_filename TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  byte_size INTEGER NOT NULL,
  official_source_url TEXT NOT NULL,
  listing_page TEXT NOT NULL,
  tabs_used TEXT NOT NULL,
  lea_grouping_basis TEXT NOT NULL,
  official_total_column TEXT NOT NULL,
  school_year_label_evidence TEXT NOT NULL,
  statewide_total_as_printed TEXT,
  statewide_total INTEGER,
  statewide_null_reason TEXT,
  spending_window_start TEXT NOT NULL,
  spending_window_end TEXT NOT NULL,
  same_basis_as_2017_18_plus INTEGER NOT NULL,
  lea_row_count INTEGER NOT NULL,
  data_quality_notes TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS october1_enrollment (
  enrollment_id INTEGER PRIMARY KEY,
  school_year TEXT NOT NULL,
  fiscal_year_as_printed TEXT,
  lea_name TEXT NOT NULL,
  lea_entity_id TEXT NOT NULL,
  lea_id_header_as_printed TEXT NOT NULL,
  total_oct1_enrollment INTEGER,
  total_as_printed TEXT NOT NULL,
  suppression_or_null_reason TEXT,
  row_scope TEXT NOT NULL,
  lea_grouping_basis TEXT NOT NULL,
  same_basis_as_2017_18_plus INTEGER NOT NULL,
  series_basis TEXT NOT NULL,
  source_file TEXT NOT NULL,
  source_tab TEXT NOT NULL,
  source_row INTEGER NOT NULL,
  UNIQUE (school_year, source_file, source_tab, source_row)
);
CREATE INDEX IF NOT EXISTS october1_enrollment_year_lea
  ON october1_enrollment (school_year, lea_entity_id, same_basis_as_2017_18_plus);
CREATE TABLE IF NOT EXISTS october1_focus (
  focus_id INTEGER PRIMARY KEY,
  focus_district TEXT NOT NULL,
  school_year TEXT NOT NULL,
  lea_name TEXT NOT NULL,
  lea_entity_id TEXT NOT NULL,
  total_oct1_enrollment INTEGER,
  total_as_printed TEXT NOT NULL,
  suppression_or_null_reason TEXT,
  focus_note TEXT NOT NULL,
  same_basis_as_2017_18_plus INTEGER NOT NULL,
  lea_id_matches_known_entity_id INTEGER NOT NULL,
  series_basis TEXT NOT NULL,
  source_file TEXT NOT NULL,
  source_tab TEXT NOT NULL,
  source_row INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS october1_index_leas (
  source_id TEXT PRIMARY KEY,
  entity_name TEXT NOT NULL,
  focus_district TEXT NOT NULL,
  lea_entity_id TEXT NOT NULL,
  display_order INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS october1_unmatched_charters (
  charter_name TEXT PRIMARY KEY,
  display_order INTEGER NOT NULL
);
DROP VIEW IF EXISTS october1_screened_by_school_year;
CREATE VIEW october1_screened_by_school_year AS
SELECT
  source_id,
  entity_name,
  school_year,
  date_basis,
  SUM(amount_cents) AS amount_cents,
  COUNT(*) AS line_count,
  MIN(tx_date) AS first_date,
  MAX(tx_date) AS last_date
FROM (
  SELECT
    source_id,
    entity_name,
    amount_cents,
    tx_date,
    date_basis,
    {SCHOOL_YEAR_CASE} AS school_year
  FROM (
    SELECT source_id, entity_name, amount_cents, check_date AS tx_date, 'check_date' AS date_basis
    FROM lines
    WHERE in_default_aggregate = 1 AND check_date IS NOT NULL
    UNION ALL
    SELECT source_id, entity_name, amount_cents, voucher_batch_date AS tx_date, 'voucher_batch_date' AS date_basis
    FROM lines
    WHERE in_default_aggregate = 1 AND voucher_batch_date IS NOT NULL
    UNION ALL
    SELECT source_id, entity_name, amount_cents, COALESCE(check_date, voucher_batch_date) AS tx_date, 'either' AS date_basis
    FROM lines
    WHERE in_default_aggregate = 1 AND COALESCE(check_date, voucher_batch_date) IS NOT NULL
  )
)
GROUP BY source_id, entity_name, school_year, date_basis;
DROP VIEW IF EXISTS october1_screened_undated;
CREATE VIEW october1_screened_undated AS
SELECT source_id, entity_name, 'check_date' AS date_basis, COUNT(*) AS line_count, SUM(amount_cents) AS amount_cents
FROM lines
WHERE in_default_aggregate = 1 AND check_date IS NULL
GROUP BY source_id, entity_name
UNION ALL
SELECT source_id, entity_name, 'voucher_batch_date' AS date_basis, COUNT(*) AS line_count, SUM(amount_cents) AS amount_cents
FROM lines
WHERE in_default_aggregate = 1 AND voucher_batch_date IS NULL
GROUP BY source_id, entity_name
UNION ALL
SELECT source_id, entity_name, 'either' AS date_basis, COUNT(*) AS line_count, SUM(amount_cents) AS amount_cents
FROM lines
WHERE in_default_aggregate = 1 AND check_date IS NULL AND voucher_batch_date IS NULL
GROUP BY source_id, entity_name;
"""


class EnrollmentExtractError(ValueError):
    """The official extract is missing a required fact or contradicts itself."""


def school_year_for_date(iso_date: str) -> str:
    """Map a transaction date to the July 1–June 30 school year that contains it."""
    if len(iso_date) != 10 or iso_date[4] != "-" or iso_date[7] != "-":
        raise EnrollmentExtractError(f"not an ISO date: {iso_date}")
    year = int(iso_date[:4])
    if iso_date[5:] >= "07-01":
        return f"{year:04d}-{year + 1:04d}"
    return f"{year - 1:04d}-{year:04d}"


def spending_window(school_year: str) -> tuple[str, str]:
    start, end = _year_pair(school_year)
    return f"{start:04d}-07-01", f"{end:04d}-06-30"


def october_1_date(school_year: str) -> str:
    start, _end = _year_pair(school_year)
    return f"{start:04d}-10-01"


def reported_cents_per_enrolled_student(amount_cents: int, enrollment: int) -> int | None:
    """Round half up to whole cents. The inputs stay the exact ratio."""
    if enrollment <= 0:
        return None
    quotient = (Decimal(abs(amount_cents)) / Decimal(enrollment)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    rounded = int(quotient)
    return -rounded if amount_cents < 0 else rounded


def series_basis(school_year: str) -> str:
    start, _end = _year_pair(school_year)
    if start >= COMPARABLE_FIRST_YEAR:
        return "lea_of_enrollment"
    if start == 2010:
        return "residence_pair_not_an_lea_total"
    return "district_of_residence_subtotal"


def load_october1_enrollment(connection: sqlite3.Connection, *, commit: bool = True) -> dict[str, int]:
    """Replace enrollment tables. Screened line amounts are left as they are."""
    before = _screened_total(connection)
    connection.executescript(ENROLLMENT_SCHEMA)
    leas = _read_csv(LEA_CSV, LEA_FIELDS)
    focus_rows = _read_csv(FOCUS_CSV, FOCUS_FIELDS)
    sources = json.loads(SOURCES_JSON.read_text(encoding="utf-8"))
    index_leas = json.loads(INDEX_LEAS_JSON.read_text(encoding="utf-8"))
    _validate_extract(leas, focus_rows, sources, index_leas)
    for table in (
        "october1_enrollment",
        "october1_focus",
        "october1_workbooks",
        "october1_index_leas",
        "october1_unmatched_charters",
        "october1_extracts",
    ):
        connection.execute(f"DELETE FROM {table}")
    _insert_extracts(connection, len(leas), len(focus_rows), len(sources["sources"]))
    _insert_workbooks(connection, sources)
    _insert_enrollment(connection, leas)
    _insert_focus(connection, focus_rows)
    _insert_index_leas(connection, index_leas)
    for order, name in enumerate(sources["unmatched_focus_candidates"]):
        connection.execute(
            "INSERT INTO october1_unmatched_charters (charter_name, display_order) VALUES (?, ?)",
            (name, order),
        )
    after = _screened_total(connection)
    if after != before:
        raise EnrollmentExtractError("loading enrollment changed the screened spending total")
    if commit:
        connection.commit()
    return {
        "lea_rows": len(leas),
        "focus_rows": len(focus_rows),
        "workbooks": len(sources["sources"]),
        "screened_line_count": before[0],
        "screened_amount_cents": before[1],
    }


def snapshot_comparisons(connection: sqlite3.Connection, basis: str = "either") -> list[dict[str, object]]:
    """Year-matched comparison for one date basis and the full screened index."""
    if basis not in {"either", "check_date", "voucher_batch_date"}:
        raise EnrollmentExtractError(f"unknown date basis: {basis}")
    leas = [
        dict(row)
        for row in connection.execute(
            "SELECT source_id, entity_name, focus_district, lea_entity_id FROM october1_index_leas ORDER BY display_order"
        )
    ]
    dated = [
        dict(row)
        for row in connection.execute(
            """SELECT source_id, entity_name, school_year, amount_cents, line_count, first_date, last_date
               FROM october1_screened_by_school_year WHERE date_basis = ?""",
            (basis,),
        )
    ]
    undated = {
        row["source_id"]: dict(row)
        for row in connection.execute(
            "SELECT source_id, line_count, amount_cents FROM october1_screened_undated WHERE date_basis = ?",
            (basis,),
        )
    }
    workbook_years = {
        row[0] for row in connection.execute("SELECT school_year FROM october1_workbooks")
    }
    workbook_by_year = {
        row["school_year"]: dict(row)
        for row in connection.execute("SELECT school_year, official_source_url, sha256 FROM october1_workbooks")
    }
    results: list[dict[str, object]] = []
    linked = {row["source_id"] for row in leas}
    for lea in leas:
        results.extend(_comparisons_for_lea(connection, lea, dated, undated.get(lea["source_id"]), workbook_years, workbook_by_year, basis))
    extras = sorted({row["source_id"] for row in dated} - linked)
    for source_id in extras:
        for row in sorted((item for item in dated if item["source_id"] == source_id), key=lambda item: str(item["school_year"])):
            results.append(_comparison_record(
                source_id=source_id,
                district=str(row["entity_name"]),
                lea_entity_id=None,
                basis=basis,
                school_year=str(row["school_year"]),
                enrollment=None,
                printed=None,
                reason="No ADE entity id is linked for this source. Enrollment is not guessed from the name.",
                line_count=int(row["line_count"]),
                amount_cents=int(row["amount_cents"]),
                first_date=row["first_date"],
                last_date=row["last_date"],
                status="no_lea_link",
                official_source_url=None,
                source_sha256=None,
            ))
    return results


def dictionary_enrollment(connection: sqlite3.Connection) -> dict[str, object]:
    """Facts for the living data dictionary. Headcounts come from the loaded extract."""
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "october1_enrollment" not in tables:
        raise EnrollmentExtractError("october1_enrollment is not in the public database")
    lea_count = connection.execute("SELECT COUNT(*) FROM october1_enrollment").fetchone()[0]
    focus_count = connection.execute("SELECT COUNT(*) FROM october1_focus").fetchone()[0]
    asterisks = connection.execute(
        "SELECT COUNT(*) FROM october1_enrollment WHERE total_as_printed = '*'"
    ).fetchone()[0]
    blanks = connection.execute(
        "SELECT COUNT(*) FROM october1_enrollment WHERE total_as_printed = ''"
    ).fetchone()[0]
    years = [row[0] for row in connection.execute("SELECT school_year FROM october1_workbooks ORDER BY school_year")]
    focus_series = {"comparable_2017_2018_onward": [], "not_comparable_2010_2011_through_2016_2017": []}
    for row in connection.execute(
        """SELECT focus_district, school_year, lea_name, lea_entity_id, total_oct1_enrollment,
                  total_as_printed, suppression_or_null_reason, focus_note, same_basis_as_2017_18_plus,
                  lea_id_matches_known_entity_id, series_basis, source_file, source_tab, source_row
           FROM october1_focus
           ORDER BY school_year, focus_district, lea_entity_id, source_row"""
    ):
        item = {
            "focus_district": row[0],
            "school_year": row[1],
            "lea_name": row[2],
            "lea_entity_id": row[3],
            "october_1_enrollment": row[4],
            "total_as_printed": row[5],
            "suppression_or_null_reason": row[6],
            "focus_note": row[7],
            "same_basis_as_2017_18_plus": bool(row[8]),
            "lea_id_matches_known_entity_id": bool(row[9]),
            "series_basis": row[10],
            "source_file": row[11],
            "source_tab": row[12],
            "source_row": row[13],
        }
        key = "comparable_2017_2018_onward" if row[8] else "not_comparable_2010_2011_through_2016_2017"
        focus_series[key].append(item)
    workbooks = []
    for row in connection.execute(
        """SELECT school_year, original_filename, sha256, official_source_url, spending_window_start,
                  spending_window_end, same_basis_as_2017_18_plus, statewide_total, statewide_total_as_printed,
                  statewide_null_reason, school_year_label_evidence, lea_row_count, data_quality_notes
           FROM october1_workbooks ORDER BY school_year"""
    ):
        workbooks.append({
            "school_year": row[0],
            "original_filename": row[1],
            "sha256": row[2],
            "official_source_url": row[3],
            "spending_window_start": row[4],
            "spending_window_end": row[5],
            "same_basis_as_2017_18_plus": bool(row[6]),
            "statewide_total": row[7],
            "statewide_total_as_printed": row[8],
            "statewide_null_reason": row[9],
            "school_year_label_evidence": row[10],
            "lea_row_count": row[11],
            "data_quality_notes": json.loads(row[12]),
        })
    extracts = [
        {"extract_id": row[0], "relative_path": row[1], "sha256": row[2], "byte_size": row[3], "row_count": row[4]}
        for row in connection.execute(
            "SELECT extract_id, relative_path, sha256, byte_size, row_count FROM october1_extracts ORDER BY extract_id"
        )
    ]
    return {
        "source_id": "ade_october_1_enrollment",
        "official_url": OFFICIAL_URL,
        "what_it_is": "ADE Accountability October 1 enrollment: a headcount of students enrolled on October 1. This is not ADM.",
        "status": "ingested",
        "http_status": None,
        "null_reason": None,
        "measure": "october_1_headcount",
        "lea_row_count": int(lea_count),
        "focus_row_count": int(focus_count),
        "suppressed_asterisk_count": int(asterisks),
        "blank_total_count": int(blanks),
        "school_years": years,
        "comparable_series": "2017-2018 through 2025-2026, from the LEA by Grade tab, LEA of enrollment.",
        "not_comparable_series": (
            "2010-2011 through 2016-2017 are not on the same basis as 2017-2018 onward and are not a continuous series. "
            "2010-2011 has no single all-students LEA total."
        ),
        "year_match_rule": (
            "School year YYYY-(YYYY+1) pairs with spending dated July 1, YYYY through June 30, YYYY+1. "
            "School year 2025-2026 pairs with 2025-07-01 through 2026-06-30."
        ),
        "coverage_window_start": "2024-07-01",
        "coverage_note": (
            "The spending coverage window still starts 2024-07-01. "
            "Year matching is only the rule for this per-enrolled-student comparison."
        ),
        "per_student_label": PER_STUDENT_LABEL,
        "comparisons": snapshot_comparisons(connection, "either"),
        "focus_series": focus_series,
        "workbooks": workbooks,
        "extracts": extracts,
        "unmatched_charter_names_not_these_districts": [
            row[0]
            for row in connection.execute(
                "SELECT charter_name FROM october1_unmatched_charters ORDER BY display_order, charter_name"
            )
        ],
        "note": (
            "Official ADE October 1 enrollment workbooks for school years 2010-2011 through 2025-2026 are loaded from the published extracts. "
            "Counts are the printed Total column. An asterisk or a blank Total is null and is not filled. "
            "This is a headcount of students enrolled on October 1, not ADM. "
            "A per-student figure is a reported amount in this index per enrolled student. "
            "It is not cost per pupil and not total district spending. "
            "School year 2025-2026 pairs with spending dated 2025-07-01 through 2026-06-30. "
            "District totals for 2010-2011 through 2016-2017 are not on the same basis as 2017-2018 onward and are not shown as one continuous series."
        ),
    }


def _comparisons_for_lea(connection, lea, dated, undated, workbook_years, workbook_by_year, basis) -> list[dict[str, object]]:
    source_id = lea["source_id"]
    screened = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_cents), 0) FROM lines WHERE source_id = ? AND in_default_aggregate = 1",
        (source_id,),
    ).fetchone()
    own_dated = sorted((row for row in dated if row["source_id"] == source_id), key=lambda row: str(row["school_year"]))
    if int(screened[0]) == 0:
        return [_comparison_record(
            source_id=source_id,
            district=lea["entity_name"],
            lea_entity_id=lea["lea_entity_id"],
            basis=basis,
            school_year=None,
            enrollment=None,
            printed=None,
            reason="This district is not in the spending index. An unindexed file is not zero spending.",
            line_count=0,
            amount_cents=None,
            first_date=None,
            last_date=None,
            status="not_in_spending_index",
            official_source_url=None,
            source_sha256=None,
        )]
    records: list[dict[str, object]] = []
    if not own_dated:
        amount = int(undated["amount_cents"]) if undated else int(screened[1])
        count = int(undated["line_count"]) if undated else int(screened[0])
        records.append(_comparison_record(
            source_id=source_id,
            district=lea["entity_name"],
            lea_entity_id=lea["lea_entity_id"],
            basis=basis,
            school_year=None,
            enrollment=None,
            printed=None,
            reason="No date is stored on this basis, so no school year is assigned. The native fiscal-year label is not used.",
            line_count=count,
            amount_cents=amount,
            first_date=None,
            last_date=None,
            status="no_dated_spending",
            official_source_url=None,
            source_sha256=None,
        ))
        return records
    for row in own_dated:
        school_year = str(row["school_year"])
        workbook = workbook_by_year.get(school_year)
        classified = _classify_year(connection, lea["lea_entity_id"], school_year, workbook_years)
        records.append(_comparison_record(
            source_id=source_id,
            district=lea["entity_name"],
            lea_entity_id=lea["lea_entity_id"],
            basis=basis,
            school_year=school_year,
            enrollment=classified["enrollment"],
            printed=classified["printed"],
            reason=classified["reason"],
            line_count=int(row["line_count"]),
            amount_cents=int(row["amount_cents"]),
            first_date=row["first_date"],
            last_date=row["last_date"],
            status=classified["status"],
            official_source_url=None if workbook is None else workbook["official_source_url"],
            source_sha256=None if workbook is None else workbook["sha256"],
        ))
    if undated and int(undated["line_count"]) > 0:
        records.append(_comparison_record(
            source_id=source_id,
            district=lea["entity_name"],
            lea_entity_id=lea["lea_entity_id"],
            basis=basis,
            school_year=None,
            enrollment=None,
            printed=None,
            reason="These screened lines have no date on this basis and are not assigned to a school year.",
            line_count=int(undated["line_count"]),
            amount_cents=int(undated["amount_cents"]),
            first_date=None,
            last_date=None,
            status="no_dated_spending",
            official_source_url=None,
            source_sha256=None,
        ))
    return records


def _classify_year(connection: sqlite3.Connection, lea_entity_id: str, school_year: str, workbook_years: set[str]) -> dict[str, object]:
    start, _end = _year_pair(school_year)
    if start < COMPARABLE_FIRST_YEAR:
        rows = _enrollment_rows(connection, lea_entity_id, school_year, same_basis=0)
        return {
            "status": "not_comparable_basis",
            "enrollment": rows[0]["total_oct1_enrollment"] if len(rows) == 1 else None,
            "printed": rows[0]["total_as_printed"] if len(rows) == 1 else None,
            "reason": (
                "This October 1 file is not the 2017-2018 and later LEA-of-enrollment basis. "
                "It is not used as a denominator."
            ),
        }
    if school_year not in workbook_years:
        return {
            "status": "no_enrollment_workbook",
            "enrollment": None,
            "printed": None,
            "reason": f"No October 1 enrollment workbook is loaded for school year {school_year}.",
        }
    rows = _enrollment_rows(connection, lea_entity_id, school_year, same_basis=1)
    if len(rows) == 0:
        return {
            "status": "lea_not_in_workbook",
            "enrollment": None,
            "printed": None,
            "reason": "This entity id is not in the October 1 workbook for that school year.",
        }
    if len(rows) > 1:
        return {
            "status": "multiple_official_rows",
            "enrollment": None,
            "printed": None,
            "reason": "More than one official total is printed for this LEA and year. Those rows are not summed.",
        }
    row = rows[0]
    if row["total_oct1_enrollment"] is None:
        return {
            "status": "suppressed_enrollment",
            "enrollment": None,
            "printed": row["total_as_printed"],
            "reason": row["suppression_or_null_reason"],
        }
    if int(row["total_oct1_enrollment"]) <= 0:
        return {
            "status": "no_positive_enrollment",
            "enrollment": int(row["total_oct1_enrollment"]),
            "printed": row["total_as_printed"],
            "reason": "The printed October 1 total is not a positive headcount, so it is not used as a denominator.",
        }
    return {
        "status": "reported_per_enrolled_student",
        "enrollment": int(row["total_oct1_enrollment"]),
        "printed": row["total_as_printed"],
        "reason": None,
    }


def _enrollment_rows(connection: sqlite3.Connection, lea_entity_id: str, school_year: str, same_basis: int) -> list[dict[str, object]]:
    return [
        dict(row)
        for row in connection.execute(
            """SELECT total_oct1_enrollment, total_as_printed, suppression_or_null_reason
               FROM october1_enrollment
               WHERE lea_entity_id = ? AND school_year = ? AND same_basis_as_2017_18_plus = ?
               ORDER BY source_row""",
            (lea_entity_id, school_year, same_basis),
        )
    ]


def _comparison_record(
    *,
    source_id: str,
    district: str,
    lea_entity_id: str | None,
    basis: str,
    school_year: str | None,
    enrollment: int | None,
    printed: str | None,
    reason: str | None,
    line_count: int,
    amount_cents: int | None,
    first_date: str | None,
    last_date: str | None,
    status: str,
    official_source_url: str | None,
    source_sha256: str | None,
) -> dict[str, object]:
    per_student = None
    if status == "reported_per_enrolled_student" and enrollment is not None and amount_cents is not None:
        per_student = reported_cents_per_enrolled_student(amount_cents, enrollment)
    window_start = None
    window_end = None
    october_date = None
    if school_year is not None:
        window_start, window_end = spending_window(school_year)
        october_date = october_1_date(school_year)
    return {
        "source_id": source_id,
        "district": district,
        "lea_entity_id": lea_entity_id,
        "date_basis": basis,
        "school_year": school_year,
        "october_1_date": october_date,
        "spending_window_start": window_start,
        "spending_window_end": window_end,
        "october_1_enrollment": enrollment,
        "enrollment_as_printed": printed,
        "enrollment_null_reason": reason,
        "screened_line_count": line_count,
        "screened_amount_cents": amount_cents,
        "spending_first_date": first_date,
        "spending_last_date": last_date,
        "reported_cents_per_enrolled_student": per_student,
        "status": status,
        "label": PER_STUDENT_LABEL,
        "official_source_url": official_source_url,
        "source_sha256": source_sha256,
    }


def _screened_total(connection: sqlite3.Connection) -> tuple[int, int]:
    row = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_cents), 0) FROM lines WHERE in_default_aggregate = 1"
    ).fetchone()
    return int(row[0]), int(row[1])


def _read_csv(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != fields:
            raise EnrollmentExtractError(f"{path.name} columns are {reader.fieldnames}")
        return list(reader)


def _validate_extract(leas: list[dict[str, str]], focus_rows: list[dict[str, str]], sources: dict, index_leas: list[dict]) -> None:
    if sources.get("failed_or_not_found"):
        raise EnrollmentExtractError("sources.json lists failed workbooks")
    by_file = {row["original_filename"]: row for row in sources["sources"]}
    if len(by_file) != len(sources["sources"]):
        raise EnrollmentExtractError("duplicate workbook filename")
    expected_years = [row["school_year_official"] for row in sources["sources"]]
    if expected_years != sources["years_extracted"]:
        raise EnrollmentExtractError("workbook order does not match years_extracted")
    counts: dict[str, int] = {}
    lea_index: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in leas:
        _parsed_total(row)
        basis = _flag(row["same_basis_as_2017_18_plus_lea_tab"], "same_basis")
        expected = series_basis(row["school_year_official"]) == "lea_of_enrollment"
        if basis != expected:
            raise EnrollmentExtractError(f"basis flag disagrees with school year for {row['lea_name']} {row['school_year_official']}")
        if row["source_file"] not in by_file:
            raise EnrollmentExtractError(f"unknown source file {row['source_file']}")
        if by_file[row["source_file"]]["school_year_official"] != row["school_year_official"]:
            raise EnrollmentExtractError("source file year does not match the row")
        counts[row["school_year_official"]] = counts.get(row["school_year_official"], 0) + 1
        lea_index[(row["source_file"], row["source_tab"], row["source_row"])] = row
    for source in sources["sources"]:
        printed_count = source["row_counts"]["lea"]
        if counts.get(source["school_year_official"]) != printed_count:
            raise EnrollmentExtractError(
                f"{source['school_year_official']} lea rows {counts.get(source['school_year_official'])} != {printed_count}"
            )
    known = {row["focus_district"]: row["lea_entity_id"] for row in index_leas}
    if set(known) != {
        "Chandler Unified",
        "Higley Unified",
        "Queen Creek Unified",
        "Scottsdale Unified",
        "Paradise Valley Unified",
    }:
        raise EnrollmentExtractError("index_leas.json does not list the five focus districts")
    for row in focus_rows:
        if row["focus_district"] not in known:
            raise EnrollmentExtractError(f"unexpected focus district {row['focus_district']}")
        matches = _flag(row["lea_id_matches_known_entity_id"], "lea_id_matches")
        if matches and row["lea_id_as_printed"] != known[row["focus_district"]]:
            raise EnrollmentExtractError(f"{row['focus_district']} id {row['lea_id_as_printed']} is not the known entity id")
        if not matches and row["school_year_official"] != "2010-2011":
            raise EnrollmentExtractError("a non-matching entity id appears after 2010-2011")
        _parsed_total(row)
        key = (row["source_file"], row["source_tab"], row["source_row"])
        official = lea_index.get(key)
        if official is None:
            raise EnrollmentExtractError(f"focus row is not in the LEA extract: {key}")
        for field in ("school_year_official", "lea_name", "lea_id_as_printed", "total_as_printed", "total_oct1_enrollment"):
            if official[field] != row[field]:
                raise EnrollmentExtractError(f"focus row disagrees with the LEA extract on {field}")


def _parsed_total(row: dict[str, str]) -> None:
    printed = row["total_as_printed"]
    numeric = row["total_oct1_enrollment"]
    reason = row["suppression_or_null_reason"]
    if printed in {"*", ""}:
        if numeric != "":
            raise EnrollmentExtractError("a suppressed or blank total was filled with a number")
        if not reason:
            raise EnrollmentExtractError("a null total has no recorded reason")
        return
    if not printed.isdigit() or printed != numeric:
        raise EnrollmentExtractError(f"printed total {printed!r} is not an unfilled integer")
    if reason:
        raise EnrollmentExtractError("a numeric total also has a null reason")
    int(row["source_row"])


def _flag(value: str, label: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise EnrollmentExtractError(f"{label} is {value!r}")


def _year_pair(school_year: str) -> tuple[int, int]:
    parts = school_year.split("-")
    if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 4:
        raise EnrollmentExtractError(f"school year {school_year}")
    start, end = int(parts[0]), int(parts[1])
    if end != start + 1:
        raise EnrollmentExtractError(f"school year {school_year} is not a single July-June year")
    return start, end


def _insert_extracts(connection: sqlite3.Connection, lea_rows: int, focus_rows: int, workbook_count: int) -> None:
    files = (
        ("lea_csv", LEA_CSV, lea_rows),
        ("focus_csv", FOCUS_CSV, focus_rows),
        ("sources_json", SOURCES_JSON, workbook_count),
        ("index_leas_json", INDEX_LEAS_JSON, None),
    )
    for extract_id, path, row_count in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        connection.execute(
            """INSERT INTO october1_extracts (extract_id, relative_path, sha256, byte_size, row_count)
               VALUES (?, ?, ?, ?, ?)""",
            (extract_id, str(path.relative_to(ROOT)), digest, path.stat().st_size, row_count),
        )


def _insert_workbooks(connection: sqlite3.Connection, sources: dict) -> None:
    for source in sources["sources"]:
        school_year = source["school_year_official"]
        window_start, window_end = spending_window(school_year)
        statewide, statewide_reason = _statewide(source.get("statewide_total_as_printed"))
        sha = source["sha256"]
        if len(sha) != 64 or any(char not in "0123456789abcdef" for char in sha):
            raise EnrollmentExtractError(f"workbook sha256 is not 64 hex digits: {source['original_filename']}")
        url = source["official_source_url"]
        if not url.startswith("https://www.azed.gov/"):
            raise EnrollmentExtractError(f"workbook URL is not on azed.gov: {url}")
        connection.execute(
            """INSERT INTO october1_workbooks (
                 school_year, original_filename, sha256, byte_size, official_source_url, listing_page,
                 tabs_used, lea_grouping_basis, official_total_column, school_year_label_evidence,
                 statewide_total_as_printed, statewide_total, statewide_null_reason,
                 spending_window_start, spending_window_end, same_basis_as_2017_18_plus,
                 lea_row_count, data_quality_notes
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                school_year,
                source["original_filename"],
                sha,
                int(source["byte_size"]),
                url,
                source["listing_page"],
                json.dumps(source["tabs_used"], ensure_ascii=False),
                source["lea_grouping_basis"],
                json.dumps(source["official_total_column"], ensure_ascii=False),
                source["school_year_label_evidence"],
                source.get("statewide_total_as_printed"),
                statewide,
                statewide_reason,
                window_start,
                window_end,
                1 if series_basis(school_year) == "lea_of_enrollment" else 0,
                int(source["row_counts"]["lea"]),
                json.dumps(source["data_quality_notes"], ensure_ascii=False),
            ),
        )


def _statewide(printed: object) -> tuple[int | None, str | None]:
    if printed is None or printed == "":
        return None, "blank in source"
    text = str(printed)
    if text == "*":
        return None, "printed '*' in source; not filled"
    if text.isdigit():
        return int(text), None
    raise EnrollmentExtractError(f"statewide total {printed!r} is not a printed integer, blank, or asterisk")


def _insert_enrollment(connection: sqlite3.Connection, leas: list[dict[str, str]]) -> None:
    for row in leas:
        total, printed = _stored_total(row)
        connection.execute(
            """INSERT INTO october1_enrollment (
                 school_year, fiscal_year_as_printed, lea_name, lea_entity_id, lea_id_header_as_printed,
                 total_oct1_enrollment, total_as_printed, suppression_or_null_reason, row_scope,
                 lea_grouping_basis, same_basis_as_2017_18_plus, series_basis, source_file, source_tab, source_row
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["school_year_official"],
                row["fiscal_year_as_printed"] or None,
                row["lea_name"],
                row["lea_id_as_printed"],
                row["lea_id_header_as_printed"],
                total,
                printed,
                row["suppression_or_null_reason"] or None,
                row["row_scope"],
                row["lea_grouping_basis"],
                1 if _flag(row["same_basis_as_2017_18_plus_lea_tab"], "same_basis") else 0,
                series_basis(row["school_year_official"]),
                row["source_file"],
                row["source_tab"],
                int(row["source_row"]),
            ),
        )


def _insert_focus(connection: sqlite3.Connection, focus_rows: list[dict[str, str]]) -> None:
    for row in focus_rows:
        total, printed = _stored_total(row)
        connection.execute(
            """INSERT INTO october1_focus (
                 focus_district, school_year, lea_name, lea_entity_id, total_oct1_enrollment, total_as_printed,
                 suppression_or_null_reason, focus_note, same_basis_as_2017_18_plus, lea_id_matches_known_entity_id,
                 series_basis, source_file, source_tab, source_row
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["focus_district"],
                row["school_year_official"],
                row["lea_name"],
                row["lea_id_as_printed"],
                total,
                printed,
                row["suppression_or_null_reason"] or None,
                row["focus_note"],
                1 if _flag(row["same_basis_as_2017_18_plus_lea_tab"], "same_basis") else 0,
                1 if _flag(row["lea_id_matches_known_entity_id"], "lea_id_matches") else 0,
                series_basis(row["school_year_official"]),
                row["source_file"],
                row["source_tab"],
                int(row["source_row"]),
            ),
        )


def _insert_index_leas(connection: sqlite3.Connection, index_leas: list[dict]) -> None:
    for order, row in enumerate(index_leas):
        found = connection.execute(
            "SELECT entity_name FROM sources WHERE source_id = ?",
            (row["source_id"],),
        ).fetchone()
        if found is None:
            continue
        if found[0] != row["entity_name"]:
            raise EnrollmentExtractError(
                f"{row['source_id']} is stored as {found[0]!r}, not {row['entity_name']!r}"
            )
        connection.execute(
            """INSERT INTO october1_index_leas (source_id, entity_name, focus_district, lea_entity_id, display_order)
               VALUES (?, ?, ?, ?, ?)""",
            (row["source_id"], found[0], row["focus_district"], row["lea_entity_id"], order),
        )


def _stored_total(row: dict[str, str]) -> tuple[int | None, str]:
    printed = row["total_as_printed"]
    if printed in {"*", ""}:
        return None, printed
    return int(printed), printed
