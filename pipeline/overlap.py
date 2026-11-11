"""Check-date overlap between report windows.

A shared header date does not prove duplicate rows. Rows are treated as
unresolved overlap only when the same check date appears in more than one
active document. Identical descriptions on different dates stay separate.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any


def window_dates(start: str | None, end: str | None) -> set[str]:
    if not start or not end:
        return set()
    cursor = date.fromisoformat(start)
    last = date.fromisoformat(end)
    found: set[str] = set()
    while cursor <= last:
        found.add(cursor.isoformat())
        cursor += timedelta(days=1)
    return found


def analyze_documents(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """documents items need id, source_id, period_start, period_end, and rows.

    Each row needs check_date, amount_cents, and identity (vendor, description, po, dac).
    """
    findings = []
    unresolved_dates_by_doc: dict[str, set[str]] = defaultdict(set)
    for left_index, left in enumerate(documents):
        for right in documents[left_index + 1 :]:
            if left["source_id"] != right["source_id"]:
                continue
            shared_window = window_dates(left.get("period_start"), left.get("period_end")) & window_dates(
                right.get("period_start"), right.get("period_end")
            )
            if not shared_window and _ranges_disjoint(left, right):
                continue
            left_dates = {row["check_date"] for row in left["rows"] if row.get("check_date")}
            right_dates = {row["check_date"] for row in right["rows"] if row.get("check_date")}
            shared_check = left_dates & right_dates
            rows_on_window = [
                row
                for row in left["rows"] + right["rows"]
                if row.get("check_date") in shared_window
            ]
            recurring = _recurring_keys(left["rows"], right["rows"])
            if shared_check:
                verdict = "unresolved_shared_check_dates"
                for row in left["rows"] + right["rows"]:
                    if row.get("check_date") in shared_check:
                        unresolved_dates_by_doc[row["document_id"]].add(row["check_date"])
            elif not rows_on_window:
                verdict = "check_dates_disjoint"
            else:
                verdict = "unresolved_rows_on_shared_header_dates"
                for row in rows_on_window:
                    unresolved_dates_by_doc[row["document_id"]].add(row["check_date"])
            findings.append({
                "left_document_id": left["document_id"],
                "right_document_id": right["document_id"],
                "source_id": left["source_id"],
                "header_shared_dates": ",".join(sorted(shared_window)),
                "shared_check_date_count": len(shared_check),
                "rows_on_shared_header_dates": len(rows_on_window),
                "rows_on_shared_header_cents": sum(row.get("amount_cents") or 0 for row in rows_on_window),
                "verdict": verdict,
                "recurring_different_date_keys": recurring["keys"],
                "recurring_different_date_line_count": recurring["lines"],
                "recurring_different_date_cents": recurring["cents"],
                "included_in_default_total": 1 if verdict == "check_dates_disjoint" else 0,
                "note": _note(verdict, shared_window, shared_check, rows_on_window, recurring),
            })
    return {"findings": findings, "unresolved_dates_by_doc": unresolved_dates_by_doc}


def _ranges_disjoint(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if not left.get("period_end") or not right.get("period_start"):
        return False
    return left["period_end"] < right["period_start"] or right["period_end"] < left["period_start"]


def _recurring_keys(left_rows: list[dict[str, Any]], right_rows: list[dict[str, Any]]) -> dict[str, int]:
    def ident(row: dict[str, Any]) -> tuple[Any, ...]:
        return (row.get("vendor"), row.get("description"), row.get("amount_cents"), row.get("po"), row.get("dac"))

    right_by = defaultdict(list)
    for row in right_rows:
        right_by[ident(row)].append(row.get("check_date"))
    keys = 0
    lines = 0
    cents = 0
    seen = set()
    for row in left_rows:
        key = ident(row)
        if key in seen or key not in right_by:
            continue
        other_dates = [item for item in right_by[key] if item and item != row.get("check_date")]
        if not other_dates:
            continue
        seen.add(key)
        keys += 1
        matched = 1 + len(other_dates)
        lines += matched
        cents += (row.get("amount_cents") or 0) * matched
    return {"keys": keys, "lines": lines, "cents": cents}


def _note(verdict: str, shared_window: set[str], shared_check: set[str], rows: list[dict[str, Any]], recurring: dict[str, int]) -> str:
    if verdict == "check_dates_disjoint":
        return (
            "Header windows share "
            + (", ".join(sorted(shared_window)) or "no calendar day")
            + f", but no parsed check date is in both documents and {len(rows)} rows fall on the shared header dates. "
            "Default totals keep both documents. "
            f"{recurring['keys']} identical vendor/description/amount/PO/DAC keys on different dates are separate lines, not collapsed."
        )
    return (
        f"Unresolved overlap: {len(shared_check)} shared check dates, {len(rows)} rows on the shared header dates. "
        "Those rows stay in the private ledger and are left out of default totals, charts, and export."
    )
