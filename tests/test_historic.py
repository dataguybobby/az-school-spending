"""Historic screened lines merge beside the existing index without double-counting."""

from __future__ import annotations

import shutil
import sqlite3

from pipeline.enrollment import load_october1_enrollment
from pipeline.enrollment import snapshot_comparisons
from pipeline.paths import public_db

EXPECTED = {
    "Chandler Unified School District #80": (1183, 2030150446),
    "Higley Unified School District No. 60": (1084, 878855408),
    "Paradise Valley Unified School District": (131, 821293538),
    "Queen Creek Unified District #95": (2675, 1675302101),
    "Scottsdale Unified School District #48": (67888, 8068394313),
}


def test_historic_merge_keeps_existing_lines_and_adds_the_screened_extract():
    connection = sqlite3.connect(f"file:{public_db()}?mode=ro", uri=True)
    total = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_cents), 0) FROM lines WHERE in_default_aggregate = 1"
    ).fetchone()
    assert total == (72961, 13473995806)
    existing = connection.execute(
        "SELECT COUNT(*) FROM lines WHERE document_id = 'susd_ap_2025-07-01_2025-08-19' AND in_default_aggregate = 1"
    ).fetchone()[0]
    assert existing == 2559
    added = connection.execute(
        "SELECT COUNT(*) FROM lines WHERE document_id LIKE 'susd_ap_2024%' OR document_id LIKE 'cusd80_%' OR document_id LIKE 'husd_%' AND document_id != 'husd_voucher_batch_1058'"
    ).fetchone()[0]
    assert added > 0
    for entity, (lines, cents) in EXPECTED.items():
        row = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_cents), 0) FROM lines WHERE entity_name = ? AND in_default_aggregate = 1",
            (entity,),
        ).fetchone()
        assert row == (lines, cents), (entity, row)
    duplicate_sha = connection.execute(
        "SELECT sha256 FROM documents GROUP BY sha256 HAVING COUNT(*) > 1 AND sha256 IS NOT NULL"
    ).fetchall()
    assert duplicate_sha == []
    gate = connection.execute(
        """
        SELECT COUNT(*) FROM documents d
        WHERE d.indexed = 1 AND d.withheld_cents IS NOT NULL AND d.printed_total_cents IS NOT NULL
          AND (
            (SELECT COALESCE(SUM(amount_cents), 0) FROM lines
             WHERE document_id = d.document_id AND in_default_aggregate = 1)
            + d.withheld_cents + COALESCE(d.revenue_excluded_cents, 0)
          ) != d.printed_total_cents
        """
    ).fetchone()[0]
    assert gate == 0
    gaps = connection.execute(
        """
        SELECT COUNT(*) FROM documents
        WHERE indexed = 0 AND public_line_count = 0
          AND coverage_note LIKE '%not zero spending%'
        """
    ).fetchone()[0]
    assert gaps >= 12
    sensitive = connection.execute(
        """
        SELECT COUNT(*) FROM lines
        WHERE lower(description_public || ' ' || vendor_raw) LIKE '%authorized user%'
           OR upper(description_public || ' ' || vendor_raw) LIKE '% IEP%'
           OR upper(description_public || ' ' || vendor_raw) LIKE '%IEP %'
           OR upper(description_public || ' ' || vendor_raw) LIKE '%MEDICAID%'
        """
    ).fetchone()[0]
    assert sensitive == 0


def test_enrollment_reload_keeps_the_chandler_supplement_link(tmp_path):
    destination = tmp_path / "ledger.sqlite"
    shutil.copy(public_db(), destination)
    connection = sqlite3.connect(destination)
    connection.row_factory = sqlite3.Row
    before = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_cents), 0) FROM lines WHERE in_default_aggregate = 1"
    ).fetchone()
    load_october1_enrollment(connection)
    linked = connection.execute(
        "SELECT lea_entity_id, entity_name FROM october1_index_leas WHERE source_id = ?",
        ("chandler_highbond_voucher_supplement",),
    ).fetchone()
    assert linked["lea_entity_id"] == "4242"
    assert linked["entity_name"] == "Chandler Unified School District #80"
    after = connection.execute(
        "SELECT COUNT(*), COALESCE(SUM(amount_cents), 0) FROM lines WHERE in_default_aggregate = 1"
    ).fetchone()
    assert tuple(after) == tuple(before)
    match = next(
        row for row in snapshot_comparisons(connection, "either")
        if row["source_id"] == "chandler_highbond_voucher_supplement" and row["school_year"] == "2025-2026"
    )
    assert match["status"] == "reported_per_enrolled_student"
    assert match["october_1_enrollment"] == 39672
