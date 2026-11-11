"""Historic screened lines merge beside the existing index without double-counting."""

from __future__ import annotations

import sqlite3

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
