"""Diligent voucher supplement account summaries.

Exercised on text-native Higley and Queen Creek PDFs. Scanned paper-capture
files can be passed through the same parser; the caller decides whether an
unreconciled OCR result may be indexed. Vendor totals and grand totals are not
detail lines. Check numbers stay on the parse result for the private store only.
A printed check number of 0 is not treated as proof of payment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

import pymupdf

from pipeline.money import parse_cents

PARSER_ID = "diligent_voucher_account_summary"
PARSER_VERSION = "1.0.0"

_ACCT = re.compile(r"^\d{3}(?:\.\d{3,4}){3,}$")
_FY = re.compile(r"Fiscal Year:\s*(\d{4}-\d{4})", re.I)
_DATE = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")


@dataclass
class VoucherLine:
    page: int
    y: float
    ordinal: int
    vendor_raw: str
    account_code_raw: str
    description_raw: str
    amount_cents: int
    check_number_raw: str | None
    voucher_batch_number: str | None
    voucher_batch_date_raw: str | None
    voucher_batch_date: str | None
    fiscal_year_label_native: str | None
    date_conflict: bool
    flags: list[str] = field(default_factory=list)
    raw_line: str = ""


@dataclass
class BatchRecon:
    batch_number: str | None
    batch_date_raw: str | None
    fiscal_year_label_native: str | None
    detail_cents: int
    printed_total_cents: int | None
    delta_cents: int | None
    page: int


@dataclass
class VoucherParse:
    parser_id: str
    parser_version: str
    lines: list[VoucherLine]
    batches: list[BatchRecon]
    warnings: list[str]
    page_count: int
    ocr_paper_capture: bool
    skipped_pages: list[int]


def _iso(text: str | None) -> str | None:
    if not text:
        return None
    try:
        return datetime.strptime(text, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _conflict(iso_date: str | None, fiscal_year: str | None) -> bool:
    if not iso_date or not fiscal_year or "-" not in fiscal_year:
        return False
    try:
        end_year = int(fiscal_year.split("-")[1])
    except ValueError:
        return False
    year = int(iso_date[:4])
    return year > end_year + 1


@dataclass
class _Span:
    page: int
    y: float
    x: float
    text: str


def _spans(page: pymupdf.Page, page_index: int) -> list[_Span]:
    found: list[_Span] = []
    payload = page.get_text("dict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)
    for block in payload.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span["text"].strip()
                if text:
                    found.append(_Span(page_index, float(span["bbox"][1]), float(span["bbox"][0]), text))
    return found


def _header(spans: list[_Span]) -> tuple[str | None, str | None, str | None]:
    header = [span for span in spans if span.y < 100]
    fiscal = None
    for span in header:
        match = _FY.search(span.text)
        if match:
            fiscal = match.group(1)
    dates = [span for span in header if _DATE.fullmatch(span.text) and span.x > 560]
    batch_date = dates[0].text if dates else None
    numbers = [
        span.text
        for span in header
        if re.fullmatch(r"\d{3,6}", span.text) and span.x > 560 and not _DATE.fullmatch(span.text)
    ]
    batch = numbers[0] if numbers else None
    return fiscal, batch, batch_date


def parse_voucher_summary_pdf(path: str) -> VoucherParse:
    document = pymupdf.open(path)
    producer = f"{document.metadata.get('producer') or ''} {document.metadata.get('creator') or ''}"
    ocr = "paper capture" in producer.lower() or "ricoh" in producer.lower()
    lines: list[VoucherLine] = []
    warnings: list[str] = []
    skipped: list[int] = []
    batches: list[BatchRecon] = []
    vendor: str | None = None
    vendor_parts: list[str] = []
    current: VoucherLine | None = None
    batch_lines: list[VoucherLine] = []
    fiscal: str | None = None
    batch_no: str | None = None
    batch_date_raw: str | None = None
    ordinal = 0
    for page_index, page in enumerate(document):
        spans = _spans(page, page_index)
        page_fiscal, page_batch, page_date = _header(spans)
        if page_fiscal or page_batch or page_date:
            fiscal = page_fiscal or fiscal
            batch_no = page_batch or batch_no
            batch_date_raw = page_date or batch_date_raw
        body = [span for span in spans if 100 <= span.y <= 548]
        body.sort(key=lambda span: (span.y, span.x))
        if not any(_ACCT.match(span.text) for span in body) and not any("Grand Total" in span.text for span in body):
            if not any("Vendor Total" in span.text for span in body):
                skipped.append(page_index + 1)
        for span in body:
            if "Grand Total" in span.text:
                printed = _nearest_amount(body, span)
                detail_sum = sum(row.amount_cents for row in batch_lines)
                delta = None if printed is None else detail_sum - printed
                batches.append(
                    BatchRecon(
                        batch_number=batch_no,
                        batch_date_raw=batch_date_raw,
                        fiscal_year_label_native=fiscal,
                        detail_cents=detail_sum,
                        printed_total_cents=printed,
                        delta_cents=delta,
                        page=page_index + 1,
                    )
                )
                batch_lines = []
                vendor = None
                vendor_parts = []
                current = None
                continue
            if "Vendor Total" in span.text:
                vendor = None
                vendor_parts = []
                current = None
                continue
            if span.text.startswith("End of Report"):
                continue
            if 250 <= span.x <= 430 and _ACCT.match(span.text):
                if vendor is None:
                    vendor = " ".join(vendor_parts).strip() or None
                    vendor_parts = []
                amount = _nearest_amount(body, span)
                if vendor is None or amount is None:
                    warnings.append(
                        f"page {page_index + 1} y={span.y:.1f} account row missing vendor or amount"
                    )
                    continue
                description = _description(body, span.y)
                ordinal += 1
                date_iso = _iso(batch_date_raw)
                conflict = _conflict(date_iso, fiscal)
                flags = ["voucher_batch_date_is_not_check_date"]
                if conflict:
                    flags.append("batch_date_conflicts_with_fiscal_year_label")
                    date_iso = None
                if re.search(r"\bREVENUE\b", description, re.I):
                    flags.append("non_spending_revenue_label")
                check_number = None
                row = VoucherLine(
                    page=page_index + 1,
                    y=round(span.y, 1),
                    ordinal=ordinal,
                    vendor_raw=vendor,
                    account_code_raw=span.text,
                    description_raw=description,
                    amount_cents=amount,
                    check_number_raw=check_number,
                    voucher_batch_number=batch_no,
                    voucher_batch_date_raw=batch_date_raw,
                    voucher_batch_date=date_iso,
                    fiscal_year_label_native=fiscal,
                    date_conflict=conflict,
                    flags=flags,
                    raw_line=" | ".join([vendor, span.text, description, str(amount)]),
                )
                lines.append(row)
                batch_lines.append(row)
                current = row
                continue
            if span.text.startswith("Check"):
                number = next(
                    (
                        item.text
                        for item in body
                        if abs(item.y - span.y) <= 3 and re.fullmatch(r"\d{1,12}", item.text) and item.x > 300
                    ),
                    None,
                )
                if current is not None and current.check_number_raw is None:
                    current.check_number_raw = number
                    if number == "0":
                        current.flags.append("check_number_printed_zero_not_payment_proof")
                continue
            if 430 <= span.x < 670:
                continue
            if span.x < 190 and not span.text.startswith("Vendor"):
                if vendor is None:
                    vendor_parts.append(span.text)
                continue
    if batch_lines:
        warnings.append("detail lines remain after the last printed grand total")
    return VoucherParse(
        parser_id=PARSER_ID,
        parser_version=PARSER_VERSION,
        lines=lines,
        batches=batches,
        warnings=warnings,
        page_count=document.page_count,
        ocr_paper_capture=ocr,
        skipped_pages=skipped,
    )


def _nearest_amount(spans: list[_Span], anchor: _Span) -> int | None:
    best: tuple[float, int] | None = None
    for span in spans:
        if span.x < 660:
            continue
        if abs(span.y - anchor.y) > 4:
            continue
        cents = parse_cents(span.text)
        if cents is None:
            continue
        distance = abs(span.y - anchor.y)
        if best is None or distance < best[0]:
            best = (distance, cents)
    return None if best is None else best[1]


def _description(spans: list[_Span], account_y: float) -> str:
    boundary = _next_boundary(spans, account_y)
    parts: list[str] = []
    for span in spans:
        if not (430 <= span.x < 670):
            continue
        if span.y < account_y - 3.5 or span.y >= boundary - 2.4:
            continue
        if parts and parts[-1] == span.text:
            continue
        parts.append(span.text)
    text = " ".join(parts).strip()
    return text


def _next_boundary(spans: list[_Span], y: float) -> float:
    candidates = [
        span.y
        for span in spans
        if span.y > y + 3
        and (
            (250 <= span.x <= 430 and _ACCT.match(span.text))
            or "Vendor Total" in span.text
            or "Grand Total" in span.text
        )
    ]
    return min(candidates) if candidates else 10_000
