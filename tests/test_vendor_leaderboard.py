"""Vendor leaderboard uses screened public lines and the printed payee."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from pipeline.paths import public_db

ROOT = Path(__file__).resolve().parents[1]


def test_printed_name_prefers_the_common_form_and_keeps_the_rest():
    subprocess.check_call(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "-e",
            r"""
import { pickPrintedName, dateExpr } from "./web/src/lib/vendor-rank.ts";
const chosen = pickPrintedName([
  { name: "RENAISSANCE LEARNING INC", lines: 1 },
  { name: "RENAISSANCE LEARNING, INC", lines: 31 },
]);
if (chosen.printed !== "RENAISSANCE LEARNING, INC") throw new Error(chosen.printed);
if (chosen.others.join("|") !== "RENAISSANCE LEARNING INC") throw new Error(chosen.others.join());
if (dateExpr("check_date") !== "check_date") throw new Error("check");
if (dateExpr("voucher_batch_date") !== "voucher_batch_date") throw new Error("voucher");
if (dateExpr("either") !== "COALESCE(check_date, voucher_batch_date)") throw new Error("either");
""",
        ],
        cwd=ROOT,
    )


def test_leaderboard_totals_match_screened_lines_and_hide_personal_payees():
    page = (ROOT / "web" / "src" / "app" / "vendors" / "page.tsx").read_text(encoding="utf-8")
    assert "Amount paid to vendor by indexed districts (reported / vouchered)" in page
    assert "They are not vendor revenue and not a vendor's total sales." in page
    assert "Coverage is not continuous." in page
    connection = sqlite3.connect(f"file:{public_db()}?mode=ro", uri=True)
    sensitive = connection.execute(
        """
        SELECT COUNT(*) FROM lines
        WHERE in_default_aggregate = 1 AND (
          lower(vendor_raw) LIKE '%authorized user%'
          OR upper(vendor_raw) LIKE '% IEP%'
          OR upper(vendor_raw) LIKE '%IEP %'
          OR upper(vendor_raw) LIKE '%MEDICAID%'
        )
        """
    ).fetchone()[0]
    assert sensitive == 0
    row = connection.execute(
        """
        SELECT SUM(amount_cents), COUNT(*), COUNT(DISTINCT entity_name),
               MIN(COALESCE(check_date, voucher_batch_date)),
               MAX(COALESCE(check_date, voucher_batch_date))
        FROM lines
        WHERE in_default_aggregate = 1 AND vendor_key = 'RENAISSANCELEARNINGINC'
        """
    ).fetchone()
    assert row[0] == 36427297
    assert row[1] == 32
    assert row[2] == 2
    assert row[3] is not None and row[4] is not None and row[3] <= row[4]
    forms = connection.execute(
        """
        SELECT vendor_raw, COUNT(*) FROM lines
        WHERE in_default_aggregate = 1 AND vendor_key = 'RENAISSANCELEARNINGINC'
        GROUP BY vendor_raw ORDER BY COUNT(*) DESC
        """
    ).fetchall()
    assert forms[0][0] == "RENAISSANCE LEARNING, INC"
    assert len(forms) == 2
