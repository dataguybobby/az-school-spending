"""Scottsdale Unified accounts-payable board report PDFs.

Columns come from each file's own header, because Excel and Adobe exports do
not share x positions. A run is assigned by where it starts, so a long
description that overflows the amount column stays a description.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

import pymupdf

from pipeline.money import parse_cents

PARSER_ID = "susd_ap_report_pdf"
PARSER_VERSION = "1.0.0"

_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
_PERIOD = re.compile(
    r"([A-Za-z]+)\s*(\d{1,2})\s*,\s*(\d{4})\s+through\s+([A-Za-z]+)\s*(\d{1,2})\s*,\s*(\d{4})",
    re.I,
)
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


@dataclass
class ParsedLine:
    page: int
    y: float
    ordinal: int
    check_date_raw: str | None
    check_date: str | None
    po_raw: str | None
    vendor_raw: str
    description_raw: str
    amount_cents: int | None
    dac_raw: str | None
    flags: list[str] = field(default_factory=list)
    raw_line: str = ""


@dataclass
class SusdParse:
    parser_id: str
    parser_version: str
    period_label_native: str | None
    period_start: str | None
    period_end: str | None
    lines: list[ParsedLine]
    report_total_cents: int | None
    warnings: list[str]
    page_count: int
    skipped_pages: list[int]


def _iso_from_mdy(text: str) -> str | None:
    try:
        return datetime.strptime(text, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _period_date(month: str, day: str, year: str) -> str | None:
    number = _MONTHS.get(month.lower())
    if not number:
        return None
    try:
        return datetime(int(year), number, int(day)).date().isoformat()
    except ValueError:
        return None


def _rows(page: pymupdf.Page) -> list[tuple[float, list[tuple[str, float, float]]]]:
    raw = page.get_text("rawdict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)
    chars: list[tuple[int, dict]] = []
    seq = 0
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for char in span.get("chars", []):
                    chars.append((seq, char))
                    seq += 1
    clusters: list[dict] = []
    for index, char in chars:
        y = float(char["bbox"][1])
        if clusters and abs(y - clusters[-1]["y"]) <= 1.4:
            clusters[-1]["items"].append((index, char))
        else:
            clusters.append({"y": y, "items": [(index, char)]})
    rows: list[tuple[float, list[tuple[str, float, float]]]] = []
    for cluster in clusters:
        cluster["items"].sort(key=lambda item: item[0])
        runs: list[list] = []
        for _index, char in cluster["items"]:
            x0 = float(char["bbox"][0])
            x1 = float(char["bbox"][2])
            text = char["c"]
            if not runs:
                runs.append([text, x0, x1, [x0]])
                continue
            prev_x1 = runs[-1][2]
            if x0 < prev_x1 - 0.45 or x0 - prev_x1 > 1.8:
                runs.append([text, x0, x1, [x0]])
            else:
                runs[-1][0] += text
                runs[-1][2] = max(runs[-1][2], x1)
                runs[-1][3].append(x0)
        rows.append((cluster["y"], [(text, x0, x1, xs) for text, x0, x1, xs in runs]))
    return rows


def _label_x(runs: list[tuple[str, float, float, list[float]]], label: str) -> float | None:
    for text, _x0, _x1, xs in runs:
        index = text.find(label)
        if index >= 0 and index < len(xs):
            return xs[index]
    return None


def _header_bounds(rows: list[tuple[float, list[tuple[str, float, float, list[float]]]]]) -> dict[str, float] | None:
    for _y, runs in rows:
        found = {name: _label_x(runs, label) for name, label in (
            ("date", "Check Date"),
            ("po", "PO No"),
            ("vendor", "Vendor"),
            ("detail", "Detail"),
            ("total", "Total"),
            ("dac", "DAC"),
        )}
        if all(value is not None for value in found.values()):
            return {name: float(value) for name, value in found.items() if value is not None}
    return None


def _column(x0: float, bounds: dict[str, float]) -> str | None:
    ordered = ["date", "po", "vendor", "detail", "total", "dac"]
    starts = [bounds[name] for name in ordered]
    for index, name in enumerate(ordered):
        left = starts[index] - 8
        right = starts[index + 1] - 4 if index + 1 < len(starts) else 10_000
        if left <= x0 < right:
            return name
    return None


_AMOUNT_TOKEN = re.compile(r"(-?\(?\$?\(?\d{1,3}(?:,\d{3})*\.\d{2}\)?)")


def _peel_trailing_amount(text: str) -> tuple[str | None, str]:
    match = _AMOUNT_TOKEN.search(text)
    if match is None or not text.rstrip().endswith(match.group(1)):
        return None, text
    end = text.rfind(match.group(1))
    prefix = text[:end].strip() if end >= 0 else ""
    return match.group(1), prefix


def _restore_year_digits(description: str, amount_text: str) -> tuple[str, str]:
    """Repair one observed overprint: ``/202`` plus ``647,600.00`` is ``/2026`` and ``47,600.00``."""
    if re.search(r"/\s*202$", description) and re.fullmatch(r"6\d{1,3},\d{3}\.\d{2}", amount_text):
        repaired = amount_text[1:]
        if parse_cents(repaired) is not None:
            return description + "6", repaired
    return description, amount_text


def _amount_and_trailing(parts: list[str]) -> tuple[int | None, str | None]:
    """Read the total column. A short DAC sometimes shares that run."""
    found: int | None = None
    trailing: str | None = None
    for part in parts:
        stripped = part.strip()
        if not stripped or stripped == "$":
            continue
        cents = parse_cents(stripped)
        if cents is not None:
            found = cents
            continue
        match = _AMOUNT_TOKEN.search(stripped.replace(" ", "") if "$" in stripped and "  " in stripped else stripped)
        if match is None:
            compact = stripped.replace(" ", "")
            match = _AMOUNT_TOKEN.search(compact)
            if match is None:
                continue
            cents = parse_cents(match.group(1))
            if cents is None:
                continue
            found = cents
            rest = compact[match.end():].strip(" $|")
            if rest:
                trailing = rest
            continue
        cents = parse_cents(match.group(1))
        if cents is None:
            continue
        found = cents
        rest = stripped[match.end():].strip(" $|")
        if rest:
            trailing = rest
    return found, trailing


def _flags(description: str, amount: int | None) -> list[str]:
    flags: list[str] = []
    upper = description.upper()
    if "NOT TO EXCEED" in upper or re.search(r"\bNTE\b", upper):
        flags.append("not_to_exceed_ceiling_in_description")
    if "BLANKET" in upper:
        flags.append("blanket_po_language")
    if "PRE-PAYMENT" in upper or "PREPAYMENT" in upper:
        flags.append("prepayment_language")
    if "CHANGE ORDER" in upper:
        flags.append("change_order_language")
    if amount is not None and amount < 0:
        flags.append("credit_or_negative")
    if "REFUND" in upper:
        flags.append("refund_language")
    if "VOID" in upper:
        flags.append("void_language")
    return flags


def parse_susd_ap_pdf(path: str) -> SusdParse:
    document = pymupdf.open(path)
    bounds: dict[str, float] | None = None
    lines: list[ParsedLine] = []
    warnings: list[str] = []
    skipped: list[int] = []
    period_label: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    report_total: int | None = None
    ordinal = 0
    for page_index, page in enumerate(document):
        page_number = page_index + 1
        rows = _rows(page)
        found = _header_bounds(rows)
        if found:
            bounds = found
        if bounds is None:
            skipped.append(page_number)
            warnings.append(f"page {page_number} skipped: column header not found yet")
            continue
        for y, runs in rows:
            buckets: dict[str, list[str]] = {name: [] for name in ("date", "po", "vendor", "detail", "total", "dac")}
            plain = []
            for text, x0, _x1, xs in runs:
                stripped = text.strip()
                if not stripped:
                    continue
                plain.append(stripped)
                column = _column(x0, bounds)
                if column == "detail":
                    left_chars = []
                    right_chars = []
                    for char, char_x in zip(text, xs):
                        if char_x >= bounds["total"] - 0.8:
                            right_chars.append(char)
                        else:
                            left_chars.append(char)
                    left = "".join(left_chars).strip()
                    right = "".join(right_chars).strip()
                    already = any(parse_cents(part) is not None for part in buckets["total"])
                    amount_text, prefix = _peel_trailing_amount(right) if right and not already else (None, right)
                    if amount_text:
                        kept = " ".join(part for part in (left, prefix) if part).strip()
                        kept, amount_text = _restore_year_digits(kept, amount_text)
                        if parse_cents(amount_text) is not None:
                            buckets["total"].append(amount_text)
                            if kept:
                                buckets["detail"].append(kept)
                        else:
                            whole = " ".join(part for part in (left, right) if part).strip()
                            if whole:
                                buckets["detail"].append(whole)
                    else:
                        kept = " ".join(part for part in (left, right) if part).strip()
                        if kept:
                            buckets["detail"].append(kept)
                elif column:
                    buckets[column].append(stripped)
            joined = " ".join(plain)
            if "Check Date" in joined and "Vendor" in joined:
                continue
            period_match = _PERIOD.search(re.sub(r"\s+", " ", joined))
            if period_label is None and period_match:
                period_label = re.sub(r"\s+", " ", joined).strip()
                period_start = _period_date(period_match.group(1), period_match.group(2), period_match.group(3))
                period_end = _period_date(period_match.group(4), period_match.group(5), period_match.group(6))
                continue
            compact = re.sub(r"\s+", " ", joined).strip()
            if re.match(r"^Total\b", compact) and not _DATE.search(compact):
                amount, _trailing = _amount_and_trailing([compact])
                if amount is None:
                    token = _AMOUNT_TOKEN.search(compact.replace(" ", ""))
                    amount = parse_cents(token.group(1)) if token else None
                if amount is not None:
                    report_total = amount
                continue
            date_blob = " ".join(buckets["date"]).strip()
            date_raw = next((part for part in buckets["date"] if _DATE.match(part)), None)
            po_raw = " ".join(part for part in buckets["po"] if part).strip() or None
            vendor = " ".join(buckets["vendor"]).strip()
            # Space glyphs often bridge date, PO, and vendor into one run that
            # starts in the date column. Split that run without moving a real
            # description, which starts in its own column.
            bridged = re.match(r"^(\d{1,2}/\d{1,2}/\d{4})(?:\s+(\S+))?(?:\s+(.+))?$", date_blob)
            if bridged:
                date_raw = bridged.group(1)
                if not po_raw and bridged.group(2):
                    po_raw = bridged.group(2)
                if not vendor and bridged.group(3):
                    vendor = bridged.group(3).strip()
            description = " ".join(buckets["detail"]).strip()
            dac = " ".join(buckets["dac"]).strip() or None
            if not vendor and po_raw and " " in po_raw:
                head, tail = po_raw.split(None, 1)
                if re.fullmatch(r"[0-9A-Z]{1,12}", head):
                    po_raw = head
                    vendor = tail.strip()
            amount, trailing_dac = _amount_and_trailing(buckets["total"])
            if not dac and trailing_dac:
                dac = trailing_dac
            if date_raw is None and amount is None and description and lines:
                previous = lines[-1]
                previous.description_raw = (previous.description_raw + " " + description).strip()
                if "wrapped_description" not in previous.flags:
                    previous.flags.append("wrapped_description")
                continue
            if date_raw is None and amount is not None and lines:
                previous = lines[-1]
                date_raw = previous.check_date_raw
                if not vendor:
                    vendor = previous.vendor_raw
                if not po_raw:
                    po_raw = previous.po_raw
                if not dac:
                    dac = previous.dac_raw
                carried = True
            else:
                carried = False
            if date_raw is None or amount is None or not vendor:
                if date_raw or amount is not None:
                    warnings.append(f"page {page_number} y={y:.1f} unparsed detail skipped")
                continue
            ordinal += 1
            flags = _flags(description, amount)
            if carried:
                flags.append("context_carried_from_previous_row")
            check_iso = _iso_from_mdy(date_raw)
            if check_iso is None:
                flags.append("check_date_unparsed")
            raw_line = " | ".join(
                part for part in (date_raw, po_raw or "", vendor, description, str(amount), dac or "")
            )
            lines.append(
                ParsedLine(
                    page=page_number,
                    y=round(y, 1),
                    ordinal=ordinal,
                    check_date_raw=date_raw,
                    check_date=check_iso,
                    po_raw=po_raw,
                    vendor_raw=vendor,
                    description_raw=description,
                    amount_cents=amount,
                    dac_raw=dac,
                    flags=flags,
                    raw_line=raw_line,
                )
            )
    if period_label is None:
        warnings.append("report period header not found")
    return SusdParse(
        parser_id=PARSER_ID,
        parser_version=PARSER_VERSION,
        period_label_native=period_label,
        period_start=period_start,
        period_end=period_end,
        lines=lines,
        report_total_cents=report_total,
        warnings=warnings,
        page_count=document.page_count,
        skipped_pages=skipped,
    )
