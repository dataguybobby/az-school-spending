"""Filter logic shared by search, charts, and CSV export."""

from __future__ import annotations

import sqlite3
from typing import Any

EXPORT_FIELDS = [
    "line_id",
    "entity_name",
    "entity_type",
    "admin_county",
    "lea_ctds",
    "check_date",
    "voucher_batch_date",
    "voucher_batch_number",
    "fiscal_year_label_native",
    "period_label_native",
    "vendor_raw",
    "description_public",
    "amount_cents",
    "currency",
    "category",
    "category_confidence",
    "category_ruleset",
    "dac_raw",
    "account_code_raw",
    "po_raw",
    "document_class",
    "amount_semantics",
    "source_url",
    "source_page",
    "source_row",
    "flags",
]

_SORTS = {
    "date": "COALESCE(check_date, voucher_batch_date)",
    "amount": "amount_cents",
    "vendor": "vendor_raw",
    "entity": "entity_name",
}


def _clauses(filters: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses = ["in_default_aggregate = 1"]
    params: list[Any] = []
    if filters.get("include_unresolved"):
        clauses = ["1=1"]
    if filters.get("source_id"):
        clauses.append("source_id = ?")
        params.append(filters["source_id"])
    if filters.get("entity"):
        clauses.append("entity_name LIKE ?")
        params.append(f"%{filters['entity']}%")
    if filters.get("vendor"):
        clauses.append("vendor_raw LIKE ?")
        params.append(f"%{filters['vendor']}%")
    if filters.get("category"):
        clauses.append("category = ?")
        params.append(filters["category"])
    if filters.get("min_confidence") not in (None, ""):
        clauses.append("category_confidence >= ?")
        params.append(float(filters["min_confidence"]))
    if filters.get("dac"):
        clauses.append("IFNULL(dac_raw,'') LIKE ?")
        params.append(f"%{filters['dac']}%")
    if filters.get("account"):
        clauses.append("IFNULL(account_code_raw,'') LIKE ?")
        params.append(f"%{filters['account']}%")
    if filters.get("q"):
        clauses.append(
            "line_id IN (SELECT line_id FROM lines_fts WHERE lines_fts MATCH ?)"
        )
        params.append(_fts_query(str(filters["q"])))
    basis = filters.get("basis") or "either"
    start = filters.get("start") or ""
    end = filters.get("end") or ""
    if basis == "check_date":
        clauses.append("check_date IS NOT NULL")
        if start:
            clauses.append("check_date >= ?")
            params.append(start)
        if end:
            clauses.append("check_date <= ?")
            params.append(end)
    elif basis == "voucher_batch_date":
        clauses.append("voucher_batch_date IS NOT NULL")
        if start:
            clauses.append("voucher_batch_date >= ?")
            params.append(start)
        if end:
            clauses.append("voucher_batch_date <= ?")
            params.append(end)
    else:
        if start:
            clauses.append("COALESCE(check_date, voucher_batch_date) >= ?")
            params.append(start)
        if end:
            clauses.append("COALESCE(check_date, voucher_batch_date) <= ?")
            params.append(end)
        if start or end:
            clauses.append("COALESCE(check_date, voucher_batch_date) IS NOT NULL")
    return " AND ".join(clauses), params


def _fts_query(text: str) -> str:
    cleaned = "".join(char if char.isalnum() or char.isspace() else " " for char in text)
    tokens = [token for token in cleaned.split() if token]
    if not tokens:
        return '""'
    return '"' + " ".join(tokens) + '"'


def _order(filters: dict[str, Any]) -> str:
    column = _SORTS.get(str(filters.get("sort") or "date"), _SORTS["date"])
    direction = "ASC" if str(filters.get("direction") or "desc").lower() == "asc" else "DESC"
    return f"{column} {direction}, line_id ASC"


def search_lines(connection: sqlite3.Connection, filters: dict[str, Any]) -> dict[str, Any]:
    where, params = _clauses(filters)
    total = connection.execute(f"SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents),0) AS cents FROM lines WHERE {where}", params).fetchone()
    limit = min(int(filters.get("limit") or 50), 200)
    offset = max(int(filters.get("offset") or 0), 0)
    rows = connection.execute(
        f"SELECT * FROM lines WHERE {where} ORDER BY {_order(filters)} LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return {
        "total": int(total["n"]),
        "amount_cents": int(total["cents"]),
        "limit": limit,
        "offset": offset,
        "rows": [dict(row) for row in rows],
    }


def monthly(connection: sqlite3.Connection, filters: dict[str, Any]) -> list[dict[str, Any]]:
    basis = filters.get("basis") or "either"
    if basis == "check_date":
        expr = "substr(check_date,1,7)"
    elif basis == "voucher_batch_date":
        expr = "substr(voucher_batch_date,1,7)"
    else:
        expr = "substr(COALESCE(check_date, voucher_batch_date),1,7)"
    where, params = _clauses(filters)
    rows = connection.execute(
        f"""
        SELECT {expr} AS month, SUM(amount_cents) AS amount_cents, COUNT(*) AS line_count
        FROM lines WHERE {where} AND {expr} IS NOT NULL AND {expr} != ''
        GROUP BY month ORDER BY month
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def categories(connection: sqlite3.Connection, filters: dict[str, Any]) -> list[dict[str, Any]]:
    where, params = _clauses(filters)
    rows = connection.execute(
        f"""
        SELECT category, SUM(amount_cents) AS amount_cents, COUNT(*) AS line_count,
               ROUND(AVG(category_confidence), 3) AS mean_confidence
        FROM lines WHERE {where} GROUP BY category ORDER BY amount_cents DESC
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def vendors(connection: sqlite3.Connection, filters: dict[str, Any], limit: int = 12) -> list[dict[str, Any]]:
    where, params = _clauses(filters)
    rows = connection.execute(
        f"""
        SELECT vendor_raw, SUM(amount_cents) AS amount_cents, COUNT(*) AS line_count
        FROM lines WHERE {where}
        GROUP BY vendor_key ORDER BY amount_cents DESC LIMIT ?
        """,
        [*params, limit],
    ).fetchall()
    return [dict(row) for row in rows]


def export_rows(connection: sqlite3.Connection, filters: dict[str, Any], limit: int = 5000) -> list[dict[str, Any]]:
    where, params = _clauses(filters)
    rows = connection.execute(
        f"SELECT {', '.join(EXPORT_FIELDS)} FROM lines WHERE {where} ORDER BY {_order(filters)} LIMIT ?",
        [*params, limit],
    ).fetchall()
    return [dict(row) for row in rows]


def unknown_date_count(connection: sqlite3.Connection, basis: str) -> int:
    if basis == "check_date":
        column = "check_date"
    elif basis == "voucher_batch_date":
        column = "voucher_batch_date"
    else:
        column = "COALESCE(check_date, voucher_batch_date)"
    row = connection.execute(f"SELECT COUNT(*) AS n FROM lines WHERE {column} IS NULL").fetchone()
    return int(row["n"])
