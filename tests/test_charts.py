"""Printed-category pies and the spend/enrollment line use the public fields as stored."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_chart_helpers_keep_gaps_and_printed_slices():
    subprocess.check_call(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "-e",
            r"""
import { groupPrintedSlices, printedCategoryField, NO_CATEGORY_PRINTED, OTHER_AS_PRINTED } from "./web/src/lib/printed-slices.ts";
import { spendWithGaps, enrollmentMarks, axisMonths, contiguousSpendSegments, schoolYearForMonth } from "./web/src/lib/spend-series.ts";
import { schoolYearForDate } from "./web/src/lib/enrollment-match.ts";

if (printedCategoryField(true, true) !== "account_description") throw new Error("account field");
if (printedCategoryField(false, true) !== "dac") throw new Error("dac field");
if (printedCategoryField(false, false) !== "none") throw new Error("none field");

const slices = groupPrintedSlices([
  { label: "EXCESS INSURANCE", amountCents: 9000, lineCount: 1 },
  { label: "TECHNICAL SERVICES", amountCents: 500, lineCount: 1 },
  { label: "DUES", amountCents: 100, lineCount: 2 },
  { label: "  ", amountCents: 400, lineCount: 3 },
]);
const labels = slices.map((slice) => slice.label);
if (!labels.includes(NO_CATEGORY_PRINTED)) throw new Error("missing blank category");
if (!labels.includes(OTHER_AS_PRINTED)) throw new Error("small slices were not grouped");
if (labels.includes("DUES")) throw new Error("tiny printed label stayed out of Other");
const blank = slices.find((slice) => slice.label === NO_CATEGORY_PRINTED);
if (!blank || blank.amountCents !== 400) throw new Error("blank amount");
const other = slices.find((slice) => slice.label === OTHER_AS_PRINTED);
if (!other || other.amountCents !== 100 || other.members.length !== 1) throw new Error("other members");
const share = slices.reduce((sum, slice) => sum + (slice.share ?? 0), 0);
if (Math.abs(share - 1) > 0.0001) throw new Error("shares " + share);

const points = spendWithGaps(["2025-07", "2025-09"], new Map([["2025-07", 100]]), ["2025-07", "2025-08", "2025-09"]);
if (points[0].amountCents !== 100) throw new Error("july");
if (points[1].amountCents !== null) throw new Error("gap became a number");
if (points[2].amountCents !== 0) throw new Error("indexed month with no matching lines");
const segments = contiguousSpendSegments(points);
if (segments.length !== 2) throw new Error("gap was connected");

if (schoolYearForMonth("2024-11") !== schoolYearForDate("2024-11-01")) throw new Error("november year");
if (schoolYearForMonth("2025-07") !== "2025-2026") throw new Error("july year");
if (schoolYearForMonth("2026-07") !== "2026-2027") throw new Error("queen creek year");

const marks = enrollmentMarks([
  { schoolYear: "2016-2017", headcount: 23354, sameBasis: false, workbookLoaded: true, rowCount: 1 },
  { schoolYear: "2017-2018", headcount: 22518, sameBasis: true, workbookLoaded: true, rowCount: 1 },
  { schoolYear: "2024-2025", headcount: 12351, sameBasis: true, workbookLoaded: true, rowCount: 1 },
  { schoolYear: "2025-2026", headcount: 20180, sameBasis: true, workbookLoaded: true, rowCount: 1 },
  { schoolYear: "2026-2027", headcount: 15408, sameBasis: true, workbookLoaded: false, rowCount: 1 },
  { schoolYear: "2022-2023", headcount: null, sameBasis: true, workbookLoaded: true, rowCount: 2 },
]);
const years = marks.map((mark) => mark.schoolYear);
if (years.includes("2016-2017")) throw new Error("pre-2017 mark was drawn");
if (years.includes("2026-2027")) throw new Error("missing workbook was drawn");
if (years.includes("2022-2023")) throw new Error("multiple rows were summed");
if (years.join() !== "2017-2018,2024-2025,2025-2026") throw new Error(years.join());
const axis = axisMonths(["2024-11", "2025-07", "2026-07"], marks.filter((mark) => mark.schoolYear >= "2024-2025"));
if (axis[0] !== "2024-07" || !axis.includes("2024-10") || axis.at(-1) !== "2026-07") throw new Error(axis.join());
if (axis.includes("2027-06")) throw new Error("enrollment was extended without a workbook");
""",
        ],
        cwd=ROOT,
    )
