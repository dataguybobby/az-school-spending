"""The Next bundle may contain only the screened public SQLite file."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "web" / "data" / "public" / "ledger.sqlite"
ALLOWED = {
    "coverage_notes",
    "documents",
    "lines",
    "lines_fts",
    "lines_fts_config",
    "lines_fts_content",
    "lines_fts_data",
    "lines_fts_docsize",
    "lines_fts_idx",
    "overlap_findings",
    "sources",
}


def test_web_data_tree_is_only_the_public_snapshot():
    files = [path for path in (ROOT / "web" / "data").rglob("*") if path.is_file()]
    assert files == [BUNDLED]
    assert not (ROOT / "web" / "data" / "raw").exists()
    assert not (ROOT / "web" / "data" / "private").exists()


def test_bundled_database_has_no_private_schema_and_keeps_fixtures():
    connection = sqlite3.connect(f"file:{BUNDLED}?mode=ro", uri=True)
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    assert tables <= ALLOWED
    columns = {row[1] for row in connection.execute("PRAGMA table_info(lines)")}
    assert "check_number" not in columns
    assert "check_number_raw" not in columns
    assert "description_raw" not in columns
    sensitive = connection.execute(
        """
        SELECT COUNT(*) FROM lines
        WHERE lower(description_public) LIKE '%authorized user%'
           OR upper(description_public) LIKE '% IEP%'
           OR upper(description_public) LIKE '%IEP %'
           OR upper(description_public) LIKE '%MEDICAID%'
        """
    ).fetchone()[0]
    assert sensitive == 0
    stress = connection.execute(
        "SELECT amount_cents, dac_raw FROM lines WHERE description_public = ? AND in_default_aggregate = 1",
        ("24 pack slow rise stress balls",),
    ).fetchone()
    assert stress == (2063, "Mohave Middle School")
    panda = connection.execute(
        "SELECT amount_cents FROM lines WHERE description_public = ? AND check_date = ?",
        ("Tisaindor 100PCS Panda Stickers", "2025-11-05"),
    ).fetchone()
    assert panda == (6469,)
    pv = connection.execute(
        "SELECT printed_total_cents, parsed_outcome, indexed FROM documents WHERE document_id = 'pvusd_fy26_vouchers_scan'"
    ).fetchone()
    assert pv[0] is None
    assert pv[1] == "parsed_unreconciled"
    assert pv[2] == 0
    chandler = connection.execute(
        "SELECT indexed, delta_cents, printed_total_cents, parsed_total_cents FROM documents WHERE document_id = 'chandler_voucher_aug2026'"
    ).fetchone()
    assert chandler[0] == 1
    assert chandler[1] == 0
    assert chandler[2] == chandler[3]
    stress_group = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_cents),0) FROM lines WHERE item_label = 'stress balls' AND in_default_aggregate = 1"
    ).fetchone()
    assert stress_group == (6, 13018)
    vendor_sensitive = connection.execute(
        """
        SELECT COUNT(*) FROM lines
        WHERE lower(vendor_raw) LIKE '%authorized user%'
           OR upper(vendor_raw) LIKE '% IEP%'
           OR upper(vendor_raw) LIKE '%IEP %'
           OR upper(vendor_raw) LIKE '%MEDICAID%'
        """
    ).fetchone()[0]
    assert vendor_sensitive == 0


def test_prepare_script_opens_fts():
    subprocess.check_call(["node", "web/scripts/prepare-public-db.mjs"], cwd=ROOT)
