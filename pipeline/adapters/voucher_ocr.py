"""Layout parser for Diligent paper-capture voucher PDFs.

The scanner's text layer is real OCR, not a silent retype. Batch dates from
that layer stay unreviewed. A voucher is reconciled only when detail lines
match a printed total on the same voucher, and vendor totals match when they
parse. Cover-page fund amounts are not detail lines. A P-card merchant and
its clearing-account payee stay on one line.
"""

from __future__ import annotations

import re
import shutil
import subprocess

import pymupdf

from pipeline.adapters.voucher import (
    PARSER_ID,
    BatchRecon,
    VoucherLine,
    VoucherParse,
)
from pipeline.money import parse_cents

OCR_VERSION = "1.1.0"

_MONEY = re.compile(r"\$\s*\(?-?\d{1,3}(?:,\d{3})*\.\d{2}\)?")
_ACCOUNT = re.compile(r"\d{3}(?:\.\d{3,4}){3,}")
_CHECK = re.compile(r"Check\s*#\s*[:;]?\s*([A-Z0-9]{4,})", re.I)
_VOUCHER_NO = re.compile(r"Voucher\s+No:\s*(\d+)", re.I)
_VOUCHER_DATE = re.compile(r"Voucher\s+Date:\s*(\d{1,2}/\d{1,2}/\d{4})", re.I)
_COVER_SUM = re.compile(r"sum of\s+(\$\s*[\d,]+\.\d{2})", re.I)
_BATCH_NO = re.compile(r"Voucher\s+Batch\s+Number:\s*(\d+)", re.I)
_BATCH_DATE = re.compile(r"Voucher\s+Batch\s+Number:\s*\d+\s+(\d{1,2}/\d{1,2}/\d{4})")
_FY = re.compile(r"Fiscal\s+Year:\s*(\d{4})\s*[-•·]\s*(\d{4})", re.I)
_PERIOD = re.compile(r"July\s+1,\s*(\d{4})\s+to\s+June\s+30,\s*(\d{4})", re.I)
_PCARD = re.compile(r"^(.*?)\s+P-Card\s+Payee:\s*(.+)$", re.I)
_VENDOR_ID = re.compile(r"\s+[A-Z]\d{4,}\b.*$")


def layout_pages(path: str) -> list[str]:
    """Rebuild reading-order lines from the PDF text layer.

    Poppler's layout mode keeps voucher columns together on paper-capture
    scans. PyMuPDF word rows are the fallback when that binary is absent.
    """
    binary = shutil.which("pdftotext")
    if binary:
        completed = subprocess.run(
            [binary, "-layout", path, "-"],
            check=True,
            capture_output=True,
        )
        return completed.stdout.decode("utf-8", errors="replace").split("\f")
    document = pymupdf.open(path)
    pages = [_words_to_text(page.get_text("words")) for page in document]
    document.close()
    return pages


def _words_to_text(words: list[tuple]) -> str:
    if not words:
        return ""
    ordered = sorted(words, key=lambda word: (round(float(word[1]), 1), float(word[0])))
    rows: list[list[tuple]] = []
    current: list[tuple] = []
    current_y: float | None = None
    for word in ordered:
        y = float(word[1])
        if current_y is None or abs(y - current_y) <= 3.2:
            current.append(word)
            current_y = y if current_y is None else current_y
        else:
            rows.append(current)
            current = [word]
            current_y = y
    if current:
        rows.append(current)
    lines: list[str] = []
    for row in rows:
        row.sort(key=lambda word: float(word[0]))
        parts: list[str] = []
        previous_right: float | None = None
        for word in row:
            left = float(word[0])
            gap = 0.0 if previous_right is None else left - previous_right
            if parts and gap > 14:
                parts.append("  ")
            elif parts:
                parts.append(" ")
            parts.append(str(word[4]))
            previous_right = float(word[2])
        lines.append("".join(parts))
    return "\n".join(lines)


def parse_paper_capture(path: str) -> VoucherParse:
    pages = layout_pages(path)
    return parse_paper_capture_pages(pages)


def parse_paper_capture_pages(pages: list[str]) -> VoucherParse:
    covers: dict[str, dict[str, object]] = {}
    batches: dict[str, dict[str, object]] = {}
    order: list[str] = []
    warnings: list[str] = ["ocr_dates_unreviewed"]
    current_vendor: str | None = None
    clearing: str | None = None
    open_batch: str | None = None

    for page_index, page in enumerate(pages):
        if "hereby authorized" in page.lower():
            _read_cover(page, page_index + 1, covers)
            continue
        batch_match = _BATCH_NO.search(page)
        if batch_match is None:
            continue
        batch_no = batch_match.group(1)
        if batch_no not in batches:
            order.append(batch_no)
            batches[batch_no] = {
                "lines": [],
                "grand": None,
                "date_raws": [],
                "fy_header": None,
                "page": page_index + 1,
            }
        if batch_no != open_batch:
            current_vendor = None
            clearing = None
            open_batch = batch_no
        record = batches[batch_no]
        date_match = _BATCH_DATE.search(page)
        if date_match:
            raw_dates = record["date_raws"]
            if isinstance(raw_dates, list):
                raw_dates.append(date_match.group(1))
        fiscal = _FY.search(page)
        if fiscal and record["fy_header"] is None:
            record["fy_header"] = f"{fiscal.group(1)}-{fiscal.group(2)}"
        for raw_line in page.splitlines():
            current_vendor, clearing = _consume_line(
                raw_line, page_index + 1, record, current_vendor, clearing
            )

    lines: list[VoucherLine] = []
    recon: list[BatchRecon] = []
    ordinal = 0
    for batch_no in order:
        record = batches[batch_no]
        cover = covers.get(batch_no, {})
        detail_lines: list[dict[str, object]] = record["lines"]  # type: ignore[assignment]
        printed, batch_warnings = _printed_total(batch_no, detail_lines, cover, record["grand"])
        warnings.extend(batch_warnings)
        detail_sum = sum(int(row["amount"]) for row in detail_lines)
        delta = None if printed is None else detail_sum - printed
        fiscal = cover.get("fy") or _usable_fy(record["fy_header"], cover.get("fy"))
        raw_dates = [item for item in record["date_raws"] if isinstance(item, str)] if isinstance(record["date_raws"], list) else []
        if isinstance(cover.get("date"), str):
            raw_dates.append(cover["date"])
        date_raw = cover.get("date") if isinstance(cover.get("date"), str) else (raw_dates[0] if raw_dates else None)
        conflict_values = [item for item in raw_dates if _date_conflicts(item, fiscal)]
        if conflict_values:
            warnings.append(f"ocr_date_conflict_unreviewed:{batch_no}:{conflict_values[0]}")
        recon.append(
            BatchRecon(
                batch_number=batch_no,
                batch_date_raw=str(date_raw) if date_raw else None,
                fiscal_year_label_native=str(fiscal) if fiscal else None,
                detail_cents=detail_sum,
                printed_total_cents=printed,
                delta_cents=delta,
                page=int(record["page"]),
            )
        )
        conflict = bool(conflict_values)
        for row in detail_lines:
            ordinal += 1
            flags = ["voucher_batch_date_is_not_check_date", "ocr_batch_date_unreviewed"]
            if conflict:
                flags.append("ocr_date_conflict_unreviewed")
            if row.get("clearing"):
                flags.append(f"pcard_clearing_payee={row['clearing']}")
            description = str(row["description"])
            lines.append(
                VoucherLine(
                    page=int(row["page"]),
                    y=float(row["y"]),
                    ordinal=ordinal,
                    vendor_raw=str(row["vendor"] or ""),
                    account_code_raw=str(row["account"]),
                    description_raw=description,
                    amount_cents=int(row["amount"]),
                    check_number_raw=row.get("check_number") if isinstance(row.get("check_number"), str) else None,
                    voucher_batch_number=batch_no,
                    voucher_batch_date_raw=str(date_raw) if date_raw else None,
                    voucher_batch_date=None,
                    fiscal_year_label_native=str(fiscal) if fiscal else None,
                    date_conflict=conflict,
                    flags=flags,
                    raw_line=str(row["raw"]),
                )
            )
    for batch_no, cover in covers.items():
        if batch_no in batches:
            continue
        warnings.append(f"cover_without_supplement:{batch_no}")
        recon.append(
            BatchRecon(
                batch_number=batch_no,
                batch_date_raw=str(cover["date"]) if cover.get("date") else None,
                fiscal_year_label_native=str(cover["fy"]) if cover.get("fy") else None,
                detail_cents=0,
                printed_total_cents=cover.get("sum") if isinstance(cover.get("sum"), int) else None,
                delta_cents=None if not isinstance(cover.get("sum"), int) else 0 - int(cover["sum"]),
                page=int(cover["page"]),
            )
        )
    return VoucherParse(
        parser_id=PARSER_ID,
        parser_version=OCR_VERSION,
        lines=lines,
        batches=recon,
        warnings=warnings,
        page_count=len(pages),
        ocr_paper_capture=True,
        skipped_pages=[],
    )


def _read_cover(page: str, page_number: int, covers: dict[str, dict[str, object]]) -> None:
    number = _VOUCHER_NO.search(page)
    if number is None:
        return
    date = _VOUCHER_DATE.search(page)
    total = _COVER_SUM.search(page)
    period = _PERIOD.search(page)
    covers[number.group(1)] = {
        "page": page_number,
        "date": date.group(1) if date else None,
        "sum": parse_cents(total.group(1)) if total else None,
        "fy": f"{period.group(1)}-{period.group(2)}" if period else None,
    }


def _consume_line(
    raw_line: str,
    page_number: int,
    record: dict[str, object],
    vendor: str | None,
    clearing: str | None,
) -> tuple[str | None, str | None]:
    text = raw_line.strip()
    if not text:
        return vendor, clearing
    lowered = text.lower()
    if lowered.startswith(("vendor remit", "printed:", "fiscal year", "amount")):
        return vendor, clearing
    if "voucher supplement" in lowered or "voucher batch number" in lowered or "end of report" in lowered or "report:" in lowered:
        return vendor, clearing
    if re.search(r"Grand\s*Total\s*:", text, re.I):
        money = _MONEY.search(text)
        record["grand"] = parse_cents(money.group(0)) if money else None
        return None, None
    if re.search(r"Vendor\s*Total\s*:", text, re.I):
        money = _MONEY.search(text)
        printed = parse_cents(money.group(0)) if money else None
        rows: list[dict[str, object]] = record["lines"]  # type: ignore[assignment]
        for row in rows:
            if row.get("vendor") == vendor and row.get("open"):
                row["open"] = False
                row["vendor_total"] = printed
        return None, None
    if _is_district_header(text):
        return vendor, clearing
    check = _CHECK.search(text)
    account = _account_in(text)
    if check and account is None:
        rows = record["lines"]  # type: ignore[assignment]
        if rows:
            rows[-1]["check_number"] = check.group(1)
            rest = _CHECK.sub(" ", text)
            rest = re.sub(r"\s+", " ", rest).strip(" :;")
            if rest and "check" not in rest.lower():
                rows[-1]["description"] = f"{rows[-1]['description']} {rest}".strip()
        return vendor, clearing
    money = _MONEY.search(text)
    if account and money:
        amount = parse_cents(money.group(0))
        if amount is None:
            return vendor, clearing
        description = _description_without_account(text[: money.start()], account)
        rows = record["lines"]  # type: ignore[assignment]
        rows.append({
            "vendor": vendor,
            "clearing": clearing,
            "account": account,
            "amount": amount,
            "description": description,
            "page": page_number,
            "y": float(page_number),
            "open": True,
            "check_number": None,
            "raw": text,
        })
        return vendor, clearing
    pcard = _PCARD.search(text)
    if pcard:
        return _clean_vendor(pcard.group(1)), re.sub(r"\s+", " ", pcard.group(2)).strip()
    if re.search(r"[A-Za-z]", text):
        name = _clean_vendor(text)
        rows = record["lines"]  # type: ignore[assignment]
        open_row = vendor is not None and any(row.get("vendor") == vendor and row.get("open") for row in rows)
        if open_row and rows:
            rows[-1]["description"] = f"{rows[-1]['description']} {name}".strip()
            return vendor, clearing
        if vendor and not open_row:
            return f"{vendor} {name}".strip(), clearing
        return name, None
    return vendor, clearing


def _account_in(text: str) -> str | None:
    compact = re.sub(r"\s+", "", text)
    match = _ACCOUNT.search(compact)
    if match is None:
        return None
    return match.group(0)


def _description_without_account(left: str, account: str) -> str:
    spaced = r"\s*".join(re.escape(char) for char in account)
    without = re.sub(spaced, " ", left, count=1)
    without = re.sub(r"\s+", " ", without).strip(" -")
    return without


def _clean_vendor(text: str) -> str:
    name = _VENDOR_ID.sub("", text).strip()
    return re.sub(r"\s+", " ", name)


def _is_district_header(text: str) -> bool:
    compact = re.sub(r"\s+", " ", text).strip()
    return bool(re.fullmatch(r"(Chandler|Paradise Valley) Unified School District(?:\s*#\d+)?", compact, re.I))


def _usable_fy(header: object, cover_fy: object) -> str | None:
    if isinstance(cover_fy, str):
        return cover_fy
    if not isinstance(header, str) or "-" not in header:
        return None
    start, end = header.split("-", 1)
    if start.isdigit() and end.isdigit() and int(end) - int(start) == 1:
        return header
    return None


def _choose_date(raws: object, cover_date: object) -> str | None:
    values = [item for item in raws if isinstance(item, str)] if isinstance(raws, list) else []
    if isinstance(cover_date, str) and cover_date:
        if values and any(item != cover_date for item in values):
            return values[0]
        return cover_date
    return values[0] if values else None


def _date_conflicts(raw: str | None, fiscal: object) -> bool:
    if not raw or not isinstance(fiscal, str) or "-" not in fiscal:
        return False
    year = raw[-4:]
    end = fiscal.split("-")[1]
    if not year.isdigit() or not end.isdigit():
        return False
    return int(year) > int(end) + 1


def _printed_total(
    batch_no: str,
    rows: list[dict[str, object]],
    cover: dict[str, object],
    grand: object,
) -> tuple[int | None, list[str]]:
    warnings: list[str] = []
    cover_sum = cover.get("sum") if isinstance(cover.get("sum"), int) else None
    grand_sum = grand if isinstance(grand, int) else None
    if grand_sum is None and cover_sum is not None:
        warnings.append(f"supplement_grand_total_not_extracted:{batch_no}")
    if grand_sum is not None and cover_sum is not None and grand_sum != cover_sum:
        warnings.append(f"cover_and_grand_total_disagree:{batch_no}")
        return None, warnings
    printed = grand_sum if grand_sum is not None else cover_sum
    if printed is None:
        return None, warnings
    groups: dict[str, dict[str, int | None]] = {}
    for row in rows:
        key = str(row.get("vendor") or "")
        group = groups.setdefault(key, {"sum": 0, "printed": None})
        group["sum"] = int(group["sum"] or 0) + int(row["amount"])
        if isinstance(row.get("vendor_total"), int):
            group["printed"] = int(row["vendor_total"])
    if grand_sum is None:
        checked = [group for group in groups.values() if group["printed"] is not None]
        if not checked or sum(int(group["printed"] or 0) for group in checked) != sum(int(row["amount"]) for row in rows):
            warnings.append(f"vendor_totals_do_not_cover_detail:{batch_no}")
            return None, warnings
    for group in groups.values():
        if group["printed"] is not None and group["printed"] != group["sum"]:
            warnings.append(f"vendor_total_mismatch:{batch_no}")
            return None, warnings
    detail = sum(int(row["amount"]) for row in rows)
    if detail != printed:
        return printed, warnings
    return printed, warnings
