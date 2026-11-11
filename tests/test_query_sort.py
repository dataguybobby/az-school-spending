"""Sort order for the public line list. Rows in this file are synthetic."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

from pipeline.query import export_rows, search_lines
from pipeline.store import PUBLIC_SCHEMA

ROOT = Path(__file__).resolve().parents[1]


def _ids(rows: list[dict[str, object]]) -> list[str]:
    return [str(row["line_id"]) for row in rows]


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(PUBLIC_SCHEMA)
    # check_date and voucher_batch_date disagree so each basis has its own order.
    rows = [
        ("b", "2025-06-01", "2024-01-15", 100, "AMAZON CAPITAL SERVICES", 1),
        ("d", "2025-06-01", "2025-07-01", 100, "AMAZON CAPITAL SERVICES", 1),
        ("a", "2025-01-01", "2024-12-01", 300, "CITY UTILITIES", 1),
        ("c", None, "2025-03-01", 200, "OFFICE SUPPLY CO", 1),
        ("n", None, None, 150, "NO DATE VENDOR", 1),
        ("z", "2024-01-01", None, 50, "HELD OUT OF THE DEFAULT TOTAL", 0),
    ]
    for line_id, check_date, voucher_batch_date, amount_cents, vendor_raw, included in rows:
        connection.execute(
            """
            INSERT INTO lines (
              line_id, in_default_aggregate, check_date, voucher_batch_date,
              amount_cents, vendor_raw, entity_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (line_id, included, check_date, voucher_batch_date, amount_cents, vendor_raw, "Synthetic District"),
        )
    connection.commit()
    return connection


def test_public_lines_sort_by_date_basis_and_amount():
    connection = _connection()

    default = search_lines(connection, {})
    assert _ids(default["rows"]) == ["b", "d", "c", "a", "n"]
    assert default["total"] == 5

    either_asc = search_lines(connection, {"sort": "date", "direction": "asc"})
    assert _ids(either_asc["rows"]) == ["a", "c", "b", "d", "n"]

    check_desc = search_lines(connection, {"basis": "check_date", "sort": "date", "direction": "desc"})
    assert _ids(check_desc["rows"]) == ["b", "d", "a"]
    check_asc = search_lines(connection, {"basis": "check_date", "sort": "date", "direction": "asc"})
    assert _ids(check_asc["rows"]) == ["a", "b", "d"]

    voucher_desc = search_lines(connection, {"basis": "voucher_batch_date", "sort": "date", "direction": "desc"})
    assert _ids(voucher_desc["rows"]) == ["d", "c", "a", "b"]
    voucher_asc = search_lines(connection, {"basis": "voucher_batch_date", "sort": "date", "direction": "asc"})
    assert _ids(voucher_asc["rows"]) == ["b", "a", "c", "d"]

    amount_desc = search_lines(connection, {"sort": "amount", "direction": "desc"})
    assert _ids(amount_desc["rows"]) == ["a", "c", "n", "b", "d"]
    amount_asc = search_lines(connection, {"sort": "amount", "direction": "ASC"})
    assert _ids(amount_asc["rows"]) == ["b", "d", "n", "c", "a"]

    unknown = search_lines(connection, {"sort": "not-a-column"})
    assert _ids(unknown["rows"]) == _ids(default["rows"])

    filtered = search_lines(connection, {
        "vendor": "AMAZON",
        "basis": "check_date",
        "start": "2025-06-01",
        "end": "2025-06-01",
        "sort": "amount",
        "direction": "asc",
        "q": "",
    })
    assert _ids(filtered["rows"]) == ["b", "d"]
    assert filtered["total"] == 2
    assert filtered["amount_cents"] == 200

    paged = search_lines(connection, {"sort": "amount", "direction": "asc", "limit": 1, "offset": 1})
    assert _ids(paged["rows"]) == ["d"]
    assert paged["total"] == 5

    exported = export_rows(connection, {"basis": "voucher_batch_date", "sort": "date", "direction": "asc"})
    assert _ids(exported) == _ids(voucher_asc["rows"])


def test_next_order_by_follows_the_same_date_basis():
    script = r"""
import { orderBy } from "./src/lib/db.ts";

const cases = [
  [{}, "COALESCE(check_date, voucher_batch_date) DESC NULLS LAST, line_id ASC"],
  [{ sort: "date", direction: "desc" }, "COALESCE(check_date, voucher_batch_date) DESC NULLS LAST, line_id ASC"],
  [{ sort: "date", direction: "asc" }, "COALESCE(check_date, voucher_batch_date) ASC NULLS LAST, line_id ASC"],
  [{ basis: "check_date" }, "check_date DESC NULLS LAST, line_id ASC"],
  [{ sort: "date", direction: "asc", basis: "check_date" }, "check_date ASC NULLS LAST, line_id ASC"],
  [{ sort: "date", basis: "voucher_batch_date" }, "voucher_batch_date DESC NULLS LAST, line_id ASC"],
  [{ sort: "date", direction: "asc", basis: "voucher_batch_date" }, "voucher_batch_date ASC NULLS LAST, line_id ASC"],
  [{ sort: "date", basis: "other" }, "COALESCE(check_date, voucher_batch_date) DESC NULLS LAST, line_id ASC"],
  [{ sort: "amount" }, "amount_cents DESC NULLS LAST, line_id ASC"],
  [{ sort: "amount", direction: "asc" }, "amount_cents ASC NULLS LAST, line_id ASC"],
  [{ sort: "amount", direction: "ASC" }, "amount_cents ASC NULLS LAST, line_id ASC"],
  [{ sort: "vendor", direction: "asc" }, "vendor_raw ASC NULLS LAST, line_id ASC"],
  [{ sort: "entity" }, "entity_name DESC NULLS LAST, line_id ASC"],
  [{ sort: "not-a-column", basis: "check_date" }, "check_date DESC NULLS LAST, line_id ASC"],
];

for (const [filters, expected] of cases) {
  const actual = orderBy(filters);
  if (actual !== expected) {
    console.error(JSON.stringify({ filters, actual, expected }));
    process.exit(1);
  }
}
"""
    completed = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT / "web",
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
