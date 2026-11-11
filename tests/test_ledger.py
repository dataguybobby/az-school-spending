"""Parser, privacy, reconciliation, and export tests.

Official-document tests read the cached public PDFs under data/raw.
Synthetic cases are named synthetic and are not district records.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pymupdf
import pytest

from pipeline.adapters.susd_ap import parse_susd_ap_pdf
from pipeline.adapters.voucher import parse_voucher_summary_pdf
from pipeline.csvsafe import sanitize_cell, write_csv, write_xlsx
from pipeline.ingest import _line_id, run_ingest
from pipeline.money import parse_cents
from pipeline.privacy import assess_row
from pipeline.query import export_rows, monthly, search_lines

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
FIXTURES = json.loads((ROOT / "fixtures" / "safe_fixture_rows.json").read_text(encoding="utf-8"))["rows"]


def test_manual_category_override_wins():
    from pipeline.classify import apply_override, classify_text
    base = classify_text("Tisaindor 100PCS Panda Stickers")
    assert base["category"] == "student_support"
    updated = apply_override(base, "line-1", {"line-1": {"category": "instructional_materials", "confidence": 0.2, "evidence": "reviewer"}})
    assert updated["category"] == "instructional_materials"
    assert updated["category_source"] == "manual_override"


def test_money_signs_and_exact_cents():
    assert parse_cents("$1,110.24") == 111024
    assert parse_cents("76,386.44") == 7638644
    assert parse_cents("($4.24)") == -424
    assert parse_cents("-($122.36)") == -12236
    assert parse_cents("3,654,818.18") == 365481818
    assert parse_cents("not money") is None


def test_synthetic_sensitive_descriptions_are_withheld():
    business = "AMAZON CAPITAL SERVICES, INC."
    for text in (
        "Authorized user Jordan Sample for classroom supplies",
        "Blanket PO for students per their IEP to attend ESY",
        "medicaid reimbursement for a named pupil",
    ):
        privacy, reasons = assess_row(business, text)
        assert privacy != "safe_business_vendor"
        assert reasons
    gloves, _reasons = assess_row(business, "Supmedic medical nitrile exam gloves, size large")
    assert gloves == "safe_business_vendor"


def test_synthetic_description_pii_quarantines_business_payee():
    privacy, reasons = assess_row(
        "AMAZON CAPITAL SERVICES, INC.",
        "reimbursement for student Alex Rivera, 123 Main Street",
    )
    assert privacy != "safe_business_vendor"
    assert reasons
    payee, _ = assess_row("SAMPLE, JORDAN Q", "orientation pay")
    assert payee == "personal_payee"


def test_spreadsheet_formula_injection():
    assert sanitize_cell("=cmd|' /C calc'!A0") .startswith("'")
    assert sanitize_cell("+1").startswith("'")
    assert sanitize_cell("@SUM(A1)").startswith("'")
    rows = [{"vendor_raw": "=1+1", "amount_cents": 10}]
    csv_text = write_csv(rows, ["vendor_raw", "amount_cents"])
    assert "'=1+1" in csv_text
    xlsx = write_xlsx(rows, ["vendor_raw", "amount_cents"])
    import io
    import zipfile
    xml = zipfile.ZipFile(io.BytesIO(xlsx)).read("xl/worksheets/sheet1.xml")
    assert b"'=1+1" in xml


def test_line_identity_keeps_identical_text_apart():
    raw = "same vendor|same amount"
    assert _line_id("abc", 1, raw) != _line_id("abc", 2, raw)


def _pdf(sha: str) -> Path:
    path = RAW / f"{sha}.pdf"
    if not path.exists():
        pytest.skip("official PDF cache is not present")
    return path


def test_safe_fixtures_match_official_pdf_cells():
    parsed = {
        "3fb1de5547e7c7b4e822149ebcdc92994b9694586a5d32f6d756fe06f8d6d5c6": parse_susd_ap_pdf(
            str(_pdf("3fb1de5547e7c7b4e822149ebcdc92994b9694586a5d32f6d756fe06f8d6d5c6"))
        ),
        "d72ec317de5a38a79d8d9c85a34856fe7913d6fc14a4fee6ac33cdc0ba726828": parse_susd_ap_pdf(
            str(_pdf("d72ec317de5a38a79d8d9c85a34856fe7913d6fc14a4fee6ac33cdc0ba726828"))
        ),
        "239855d59bbf04e37de6f9ed0e3b3423d7ee8b1187af74f56c50aee6c3ad9bf0": parse_voucher_summary_pdf(
            str(_pdf("239855d59bbf04e37de6f9ed0e3b3423d7ee8b1187af74f56c50aee6c3ad9bf0"))
        ),
        "345d6d2602aed2ac794286361ca4ebcf86f51f52d7d3dd6667288c4775a4125e": parse_voucher_summary_pdf(
            str(_pdf("345d6d2602aed2ac794286361ca4ebcf86f51f52d7d3dd6667288c4775a4125e"))
        ),
    }
    for fixture in FIXTURES:
        document = parsed[fixture["source_document_sha256"]]
        needle = fixture["detail_line_description"]
        matches = [
            line for line in document.lines
            if line.amount_cents == fixture["amount_cents"]
            and fixture["vendor"] in line.vendor_raw
            and (needle in line.description_raw or "NOT TO EXCEED AMOUNT $3,654,818.18" in line.description_raw and "NOT TO EXCEED" in needle)
        ]
        assert matches, fixture["fixture_id"]
        line = matches[0]
        assert line.page == fixture["pdf_page"]
        if fixture.get("school_or_dac_raw"):
            assert line.dac_raw == fixture["school_or_dac_raw"]
        if fixture.get("account_code_raw"):
            assert line.account_code_raw == fixture["account_code_raw"]
        if "check_date" in fixture and fixture["check_date"]:
            assert line.check_date == fixture["check_date"]
        if fixture.get("check_date") is None and fixture["source_id"] != "susd_diligent_ap_report":
            assert line.voucher_batch_date == fixture["voucher_batch_date"]
            assert not hasattr(line, "check_date") or getattr(line, "check_date", None) in (None,)


def test_abm_line_amount_is_not_the_nte_ceiling():
    parsed = parse_susd_ap_pdf(str(_pdf("d72ec317de5a38a79d8d9c85a34856fe7913d6fc14a4fee6ac33cdc0ba726828")))
    rows = [line for line in parsed.lines if line.po_raw == "2600245" and "NOT TO EXCEED" in line.description_raw]
    assert rows
    assert rows[0].amount_cents == 7638644
    assert rows[0].amount_cents != 365481818
    assert "3,654,818.18" in rows[0].description_raw
    assert rows[0].description_raw.endswith("FISCAL YEAR")


def test_reconciled_official_documents_match_printed_totals():
    expectations = {
        "3fb1de5547e7c7b4e822149ebcdc92994b9694586a5d32f6d756fe06f8d6d5c6": 522147865,
        "92b5b4b9a22fb3f660b6f097c935dea519fe30331f4c30ae1b2b761518f59cfe": 460628331,
        "42398b5e2742fc0c1377da402c854af17adf269b8cf6b3de92783097fd271cbe": 594864932,
        "d72ec317de5a38a79d8d9c85a34856fe7913d6fc14a4fee6ac33cdc0ba726828": 162091640,
        "1e3a60d4a9eee19cb5c82635afba081b8e6588fc16e40c3aa69fb4b666fbc420": 189919646,
    }
    for sha, total in expectations.items():
        parsed = parse_susd_ap_pdf(str(_pdf(sha)))
        assert sum(line.amount_cents or 0 for line in parsed.lines) == total
        assert parsed.report_total_cents == total
        assert any((line.amount_cents or 0) < 0 for line in parsed.lines)
    husd = parse_voucher_summary_pdf(str(_pdf("239855d59bbf04e37de6f9ed0e3b3423d7ee8b1187af74f56c50aee6c3ad9bf0")))
    assert sum(line.amount_cents for line in husd.lines) == 39830488
    assert husd.batches[0].delta_cents == 0
    assert all(line.voucher_batch_date == "2024-11-20" for line in husd.lines)
    qcusd = parse_voucher_summary_pdf(str(_pdf("345d6d2602aed2ac794286361ca4ebcf86f51f52d7d3dd6667288c4775a4125e")))
    assert all(batch.delta_cents == 0 for batch in qcusd.batches)
    assert any(line.check_number_raw == "0" for line in qcusd.lines)


def test_overlap_classifier_and_public_agreement():
    from pipeline.overlap import analyze_documents
    disjoint = analyze_documents([
        {"document_id": "a", "source_id": "susd", "period_start": "2025-09-18", "period_end": "2025-10-27",
         "rows": [{"document_id": "a", "check_date": "2025-10-23", "amount_cents": 100, "vendor": "A", "description": "paper", "po": "1", "dac": "X"}]},
        {"document_id": "b", "source_id": "susd", "period_start": "2025-10-27", "period_end": "2025-11-13",
         "rows": [{"document_id": "b", "check_date": "2025-10-29", "amount_cents": 100, "vendor": "A", "description": "paper", "po": "1", "dac": "X"}]},
    ])
    assert disjoint["findings"][0]["verdict"] == "check_dates_disjoint"
    assert disjoint["findings"][0]["rows_on_shared_header_dates"] == 0
    assert disjoint["findings"][0]["recurring_different_date_keys"] == 1
    shared = analyze_documents([
        {"document_id": "a", "source_id": "susd", "period_start": "2025-10-01", "period_end": "2025-10-27",
         "rows": [{"document_id": "a", "check_date": "2025-10-27", "amount_cents": 500, "vendor": "A", "description": "same", "po": "1", "dac": "X"}]},
        {"document_id": "b", "source_id": "susd", "period_start": "2025-10-27", "period_end": "2025-11-13",
         "rows": [{"document_id": "b", "check_date": "2025-10-27", "amount_cents": 500, "vendor": "A", "description": "same", "po": "1", "dac": "X"}]},
    ])
    assert shared["findings"][0]["verdict"] == "unresolved_shared_check_dates"
    assert "a" in shared["unresolved_dates_by_doc"]
    database = ROOT / "data" / "public" / "ledger.sqlite"
    if not database.exists():
        return
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    finding = connection.execute(
        "SELECT * FROM overlap_findings WHERE header_shared_dates LIKE '%2025-10-27%'"
    ).fetchone()
    assert finding is not None
    assert finding["verdict"] == "check_dates_disjoint"
    assert finding["shared_check_date_count"] == 0
    assert finding["rows_on_shared_header_dates"] == 0
    filtered = search_lines(connection, {"basis": "check_date", "start": "2025-08-01", "end": "2025-08-31"})
    months = monthly(connection, {"basis": "check_date", "start": "2025-08-01", "end": "2025-08-31"})
    exported = export_rows(connection, {"basis": "check_date", "start": "2025-08-01", "end": "2025-08-31"}, limit=100000)
    assert sum(row["amount_cents"] for row in months) == filtered["amount_cents"]
    assert sum(row["amount_cents"] for row in exported) == filtered["amount_cents"]
    assert filtered["total"] == len(exported)
    assert connection.execute("SELECT COUNT(*) FROM lines WHERE lower(description_public) LIKE '%authorized user%'").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM lines WHERE description_public LIKE '% IEP %' OR description_public LIKE 'IEP %' OR description_public LIKE '% IEP' OR description_public = 'IEP'").fetchone()[0] == 0
    pv = connection.execute("SELECT printed_total_cents, parsed_total_cents, delta_cents, parsed_outcome, indexed, printed_total_null_reason FROM documents WHERE document_id = 'pvusd_fy26_vouchers_scan'").fetchone()
    assert pv["printed_total_cents"] is None
    assert pv["parsed_total_cents"] is None
    assert pv["delta_cents"] is None
    assert pv["parsed_outcome"] == "parsed_zero"
    assert pv["indexed"] == 0
    assert pv["printed_total_null_reason"]


def test_public_index_hides_check_numbers_and_matches_filters():
    database = ROOT / "data" / "public" / "ledger.sqlite"
    if not database.exists():
        pytest.skip("public index has not been built")
    assert b"1605020380" not in database.read_bytes()
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    found = search_lines(connection, {"q": "stress balls", "basis": "check_date"})
    like = connection.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents),0) AS cents FROM lines WHERE description_public LIKE ?",
        ("%stress balls%",),
    ).fetchone()
    assert found["total"] == like["n"]
    assert found["amount_cents"] == like["cents"]
    assert found["total"] >= 1
    mohave = [row for row in found["rows"] if row["dac_raw"] == "Mohave Middle School" and row["amount_cents"] == 2063]
    assert mohave
    assert mohave[0]["check_date"] == "2025-08-18"
    months = monthly(connection, {"q": "stress balls", "basis": "check_date"})
    assert sum(row["amount_cents"] for row in months) == found["amount_cents"]
    exported = export_rows(connection, {"basis": "check_date", "start": "2025-07-01", "source_id": "husd_diligent_voucher_summary"})
    assert exported == []
    voucher_rows = export_rows(connection, {"basis": "voucher_batch_date", "source_id": "husd_diligent_voucher_summary"})
    assert voucher_rows
    assert all(row["check_date"] in (None, "") for row in voucher_rows)
    assert all(row["amount_semantics"] == "reported_ap_or_vouchered_not_settlement" for row in voucher_rows)
    text = write_csv(voucher_rows, list(voucher_rows[0].keys()))
    assert "1605020380" not in text


def test_ingest_rerun_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_HOME", str(tmp_path))
    document = {
        "document_id": "husd_voucher_batch_1058",
        "source_id": "husd_diligent_voucher_summary",
        "url": "https://husd.community.diligentoneplatform.com/document/689d0863-eeca-45c5-9d5f-46e9c061a48a/",
        "sha256": "239855d59bbf04e37de6f9ed0e3b3423d7ee8b1187af74f56c50aee6c3ad9bf0",
        "adapter": "diligent_voucher_account_summary",
        "manifest": "v2",
    }
    source = RAW / f"{document['sha256']}.pdf"
    if not source.exists():
        pytest.skip("Higley PDF cache is not present")
    target = tmp_path / "raw"
    target.mkdir()
    (target / source.name).write_bytes(source.read_bytes())
    first = run_ingest([document])
    second = run_ingest([document])
    assert first["public_lines"] == second["public_lines"]
    assert first["public_amount_cents"] == second["public_amount_cents"]
    private = sqlite3.connect(tmp_path / "private" / "ledger.sqlite")
    checks = [row[0] for row in private.execute("SELECT check_number_raw FROM silver_lines WHERE check_number_raw IS NOT NULL")]
    assert checks
    public_bytes = (tmp_path / "public" / "ledger.sqlite").read_bytes()
    for check in checks:
        assert str(check).encode() not in public_bytes or check == "0"


def test_synthetic_credit_pdf_preserves_negative_amount(tmp_path):
    path = tmp_path / "synthetic.pdf"
    document = pymupdf.open()
    page = document.new_page(width=792, height=612)
    page.insert_text((52, 70), "Check Date", fontsize=8)
    page.insert_text((98, 70), "PO No.", fontsize=8)
    page.insert_text((131, 70), "Vendor", fontsize=8)
    page.insert_text((321, 70), "Detail Line Description", fontsize=8)
    page.insert_text((548, 70), "Total", fontsize=8)
    page.insert_text((605, 70), "DAC", fontsize=8)
    page.insert_text((60, 90), "8/18/2025 2600001 AMAZON CAPITAL SERVICES, INC.", fontsize=8)
    page.insert_text((321, 90), "Order Discount", fontsize=8)
    page.insert_text((576, 90), "(4.24)", fontsize=8)
    page.insert_text((548, 90), "$", fontsize=8)
    page.insert_text((605, 90), "Mohave Middle School", fontsize=8)
    page.insert_text((524, 120), "Total", fontsize=8)
    page.insert_text((560, 120), "(4.24)", fontsize=8)
    document.save(path)
    document.close()
    parsed = parse_susd_ap_pdf(str(path))
    assert len(parsed.lines) == 1
    assert parsed.lines[0].amount_cents == -424
    assert "credit_or_negative" in parsed.lines[0].flags
    assert parsed.lines[0].description_raw == "Order Discount"


def _write_susd_pdf(path: Path, rows: list[tuple[str, str, str, str, str, str]], total: str) -> str:
    import hashlib
    document = pymupdf.open()
    page = document.new_page(width=792, height=612)
    y = 70
    for label, x in (("Check Date", 52), ("PO No.", 98), ("Vendor", 131), ("Detail Line Description", 321), ("Total", 548), ("DAC", 605)):
        page.insert_text((x, y), label, fontsize=8)
    y = 92
    for date_text, po, vendor, desc, amount, dac in rows:
        page.insert_text((60, y), f"{date_text} {po} {vendor}", fontsize=8)
        page.insert_text((321, y), desc, fontsize=8)
        page.insert_text((560, y), amount, fontsize=8)
        page.insert_text((548, y), "$", fontsize=8)
        page.insert_text((605, y), dac, fontsize=8)
        y += 16
    page.insert_text((548, y), "Total", fontsize=8)
    page.insert_text((570, y), total, fontsize=8)
    document.save(path)
    document.close()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_duplicate_legitimate_lines_and_revised_document(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_HOME", str(tmp_path))
    first = tmp_path / "v1.pdf"
    digest_one = _write_susd_pdf(
        first,
        [
            ("8/18/2025", "2600001", "AMAZON CAPITAL SERVICES, INC.", "pencils", "10.00", "Mohave Middle School"),
            ("8/18/2025", "2600001", "AMAZON CAPITAL SERVICES, INC.", "pencils", "10.00", "Mohave Middle School"),
        ],
        "20.00",
    )
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / f"{digest_one}.pdf").write_bytes(first.read_bytes())
    document = {
        "document_id": "synthetic_revision",
        "source_id": "susd_diligent_ap_report",
        "url": "https://example.invalid/synthetic",
        "sha256": digest_one,
        "adapter": "susd_ap_report_pdf",
        "manifest": "synthetic",
    }
    first_report = run_ingest([document])
    assert first_report["public_lines"] == 2
    assert first_report["public_amount_cents"] == 2000
    revised = tmp_path / "v2.pdf"
    digest_two = _write_susd_pdf(
        revised,
        [("8/18/2025", "2600009", "AMAZON CAPITAL SERVICES, INC.", "folders", "25.00", "Mohave Middle School")],
        "25.00",
    )
    (tmp_path / "raw" / f"{digest_two}.pdf").write_bytes(revised.read_bytes())
    document["sha256"] = digest_two
    second_report = run_ingest([document])
    assert second_report["public_lines"] == 1
    assert second_report["public_amount_cents"] == 2500
    private = sqlite3.connect(tmp_path / "private" / "ledger.sqlite")
    active = private.execute("SELECT COUNT(*) FROM silver_lines WHERE active = 1").fetchone()[0]
    inactive = private.execute("SELECT COUNT(*) FROM silver_lines WHERE active = 0").fetchone()[0]
    assert active == 1
    assert inactive == 2


def test_unresolved_shared_check_date_is_kept_out_of_default_total(tmp_path, monkeypatch):
    monkeypatch.setenv("LEDGER_HOME", str(tmp_path))
    raw = tmp_path / "raw"
    raw.mkdir()
    documents = []
    for index in (1, 2):
        path = tmp_path / f"doc{index}.pdf"
        digest = _write_susd_pdf(
            path,
            [("10/27/2025", "2600099", "AMAZON CAPITAL SERVICES, INC.", "paper", "10.00", "Mohave Middle School")],
            "10.00",
        )
        (raw / f"{digest}.pdf").write_bytes(path.read_bytes())
        documents.append({
            "document_id": f"synthetic_overlap_{index}",
            "source_id": "susd_diligent_ap_report",
            "url": "https://example.invalid/overlap",
            "sha256": digest,
            "adapter": "susd_ap_report_pdf",
            "manifest": "synthetic",
        })
    report = run_ingest(documents)
    assert report["public_amount_cents"] == 0
    assert report["overlap"][0]["verdict"] == "unresolved_shared_check_dates"
    private = sqlite3.connect(tmp_path / "private" / "ledger.sqlite")
    assert private.execute("SELECT COUNT(*) FROM silver_lines WHERE active = 1").fetchone()[0] == 2
    public = sqlite3.connect(tmp_path / "public" / "ledger.sqlite")
    held = public.execute("SELECT COUNT(*), COALESCE(SUM(amount_cents),0) FROM lines WHERE in_default_aggregate = 0").fetchone()
    assert held == (2, 2000)
