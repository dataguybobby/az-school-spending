"""Repeatable local commands. Nothing here starts a schedule."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from pipeline.csvsafe import write_csv, write_xlsx
from pipeline.discover import discover
from pipeline.ingest import run_ingest
from pipeline.scout import scout
from pipeline.paths import public_db
from pipeline.query import EXPORT_FIELDS, categories, export_rows, monthly, search_lines, vendors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("discover")
    sub.add_parser("scout")
    sub.add_parser("fetch")
    sub.add_parser("extract")
    sub.add_parser("normalize")
    sub.add_parser("classify")
    sub.add_parser("index")
    sub.add_parser("ingest")
    search = sub.add_parser("search")
    search.add_argument("text")
    search.add_argument("--basis", default="either")
    search.add_argument("--start", default="")
    search.add_argument("--source", default="")
    export = sub.add_parser("export")
    export.add_argument("--out", required=True)
    export.add_argument("--basis", default="either")
    export.add_argument("--start", default="")
    export.add_argument("--q", default="")
    export.add_argument("--xlsx", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "discover":
        print(json.dumps(discover(), indent=2))
        return 0
    if args.command == "scout":
        print(json.dumps(scout(), indent=2))
        return 0
    if args.command in {"fetch", "extract", "normalize", "classify", "index", "ingest"}:
        report = run_ingest()
        print(json.dumps({
            "indexed_documents": report["indexed_documents"],
            "public_lines": report["public_lines"],
            "public_amount_cents": report["public_amount_cents"],
        }, indent=2))
        return 0
    connection = sqlite3.connect(public_db())
    connection.row_factory = sqlite3.Row
    if args.command == "search":
        result = search_lines(connection, {"q": args.text, "basis": args.basis, "start": args.start, "source_id": args.source, "limit": 20})
        print(json.dumps({"total": result["total"], "amount_cents": result["amount_cents"], "rows": result["rows"][:5]}, indent=2))
        return 0
    filters = {"q": args.q, "basis": args.basis, "start": args.start}
    rows = export_rows(connection, filters)
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if args.xlsx:
        destination.write_bytes(write_xlsx(rows, EXPORT_FIELDS))
    else:
        destination.write_text(write_csv(rows, EXPORT_FIELDS), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "monthly": monthly(connection, filters), "categories": categories(connection, filters)[:8], "vendors": vendors(connection, filters, 5)}, indent=2))
    return 0
