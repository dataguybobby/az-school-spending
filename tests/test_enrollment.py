"""Official ADE October 1 enrollment stays a headcount and does not change spending."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from pipeline.enrollment import (
    SCHOOL_YEAR_CASE,
    reported_cents_per_enrolled_student,
    school_year_for_date,
    snapshot_comparisons,
)
from pipeline.paths import public_db

ROOT = Path(__file__).resolve().parents[1]


def test_school_year_follows_july_1_not_the_coverage_window_start():
    assert school_year_for_date("2024-07-01") == "2024-2025"
    assert school_year_for_date("2025-06-30") == "2024-2025"
    assert school_year_for_date("2025-07-01") == "2025-2026"
    assert school_year_for_date("2026-06-30") == "2025-2026"
    assert school_year_for_date("2026-07-06") == "2026-2027"
    assert school_year_for_date("2024-11-20") == "2024-2025"


def test_per_student_cents_round_half_up_and_do_not_divide_by_zero():
    assert reported_cents_per_enrolled_student(1510301067, 20180) == 74841
    assert reported_cents_per_enrolled_student(38747872, 12351) == 3137
    assert reported_cents_per_enrolled_student(1, 2) == 1
    assert reported_cents_per_enrolled_student(2, 5) == 0
    assert reported_cents_per_enrolled_student(3, 5) == 1
    assert reported_cents_per_enrolled_student(100, 0) is None


def test_public_enrollment_keeps_suppression_and_the_comparability_break():
    connection = sqlite3.connect(f"file:{public_db()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    filled = connection.execute(
        "SELECT COUNT(*) FROM october1_enrollment WHERE total_as_printed IN ('*', '') AND total_oct1_enrollment IS NOT NULL"
    ).fetchone()[0]
    assert filled == 0
    stars = connection.execute("SELECT COUNT(*) FROM october1_enrollment WHERE total_as_printed = '*'").fetchone()[0]
    blanks = connection.execute("SELECT COUNT(*) FROM october1_enrollment WHERE total_as_printed = ''").fetchone()[0]
    assert stars == 265
    assert blanks == 6
    early = connection.execute(
        "SELECT COUNT(*) FROM october1_enrollment WHERE school_year < '2017-2018' AND same_basis_as_2017_18_plus = 1"
    ).fetchone()[0]
    later = connection.execute(
        "SELECT COUNT(*) FROM october1_enrollment WHERE school_year >= '2017-2018' AND same_basis_as_2017_18_plus = 0"
    ).fetchone()[0]
    assert early == 0
    assert later == 0
    susd_2010 = connection.execute(
        """SELECT lea_entity_id, total_oct1_enrollment FROM october1_enrollment
           WHERE school_year = '2010-2011' AND lea_name = 'Scottsdale Unified District'
           ORDER BY lea_entity_id"""
    ).fetchall()
    assert [(row["lea_entity_id"], row["total_oct1_enrollment"]) for row in susd_2010] == [
        ("4240", 26210),
        ("4241", 2),
        ("4286", 1),
    ]
    screened = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_cents), 0) FROM lines WHERE in_default_aggregate = 1"
    ).fetchone()
    assert tuple(screened) == (14387, 2155944882)


def test_year_match_does_not_use_the_previous_july_or_an_undated_fiscal_label():
    connection = sqlite3.connect(f"file:{public_db()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    rows = {(row["source_id"], row["status"]): row for row in snapshot_comparisons(connection, "either")}
    scottsdale = rows[("susd_diligent_ap_report", "reported_per_enrolled_student")]
    assert scottsdale["school_year"] == "2025-2026"
    assert scottsdale["october_1_enrollment"] == 20180
    assert scottsdale["spending_first_date"] == "2025-07-14"
    higley = rows[("husd_diligent_voucher_summary", "reported_per_enrolled_student")]
    assert higley["school_year"] == "2024-2025"
    assert higley["october_1_enrollment"] == 12351
    queen = rows[("qcusd_diligent_voucher_summary", "no_enrollment_workbook")]
    assert queen["school_year"] == "2026-2027"
    assert queen["october_1_enrollment"] is None
    chandler = rows[("chandler_highbond_voucher_unverified", "no_dated_spending")]
    assert chandler["school_year"] is None
    assert chandler["reported_cents_per_enrolled_student"] is None
    check_date = {(row["source_id"], row["status"]): row for row in snapshot_comparisons(connection, "check_date")}
    assert ("husd_diligent_voucher_summary", "reported_per_enrolled_student") not in check_date
    assert check_date[("husd_diligent_voucher_summary", "no_dated_spending")]["reported_cents_per_enrolled_student"] is None
    assert check_date[("susd_diligent_ap_report", "reported_per_enrolled_student")]["october_1_enrollment"] == 20180


def test_web_school_year_sql_matches_the_python_rule():
    web = (ROOT / "web" / "src" / "lib" / "enrollment.ts").read_text(encoding="utf-8")
    assert " ".join(SCHOOL_YEAR_CASE.split()) in " ".join(web.split())
    subprocess.check_call(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "-e",
            """
import { schoolYearForDate, reportedCentsPerEnrolledStudent } from "./web/src/lib/enrollment-match.ts";
const pairs = [
  ["2024-07-01", "2024-2025"],
  ["2025-06-30", "2024-2025"],
  ["2025-07-01", "2025-2026"],
  ["2026-06-30", "2025-2026"],
  ["2026-07-06", "2026-2027"],
  ["2024-11-20", "2024-2025"],
];
for (const [date, year] of pairs) {
  if (schoolYearForDate(date) !== year) throw new Error(date + " -> " + schoolYearForDate(date));
}
if (reportedCentsPerEnrolledStudent(1510301067, 20180) !== 74841) throw new Error("scottsdale");
if (reportedCentsPerEnrolledStudent(38747872, 12351) !== 3137) throw new Error("higley");
if (reportedCentsPerEnrolledStudent(1, 2) !== 1) throw new Error("half");
""",
        ],
        cwd=ROOT,
    )
