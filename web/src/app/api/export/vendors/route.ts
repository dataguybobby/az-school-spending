import { NextRequest } from "next/server";
import { openDb, type Filters } from "@/lib/db";
import { sanitizeCell } from "@/lib/utils";
import { loadVendorLeaderboard } from "@/lib/vendor-leaderboard";
import { sortDirection, vendorOrder, vendorSort } from "@/lib/vendor-rank";

export const dynamic = "force-dynamic";

const FIELDS = [
  "vendor_as_printed",
  "vendor_key",
  "other_printed_forms",
  "amount_cents",
  "line_count",
  "district_count",
  "district_breakdown",
  "first_date",
  "last_date",
] as const;

export function GET(request: NextRequest) {
  const filters: Filters = {
    source: request.nextUrl.searchParams.get("source") || undefined,
    basis: request.nextUrl.searchParams.get("basis") || undefined,
    start: request.nextUrl.searchParams.get("start") || undefined,
    end: request.nextUrl.searchParams.get("end") || undefined,
  };
  const search = request.nextUrl.searchParams.get("q") || "";
  const rows = loadVendorLeaderboard(openDb(), filters, search).sort(
    vendorOrder(vendorSort(request.nextUrl.searchParams.get("sort") || undefined), sortDirection(request.nextUrl.searchParams.get("direction") || undefined)),
  );
  const header = FIELDS.join(",");
  const body = rows.map((row) => FIELDS.map((field) => csv(sanitizeCell(cell(row, field)))).join(",")).join("\n");
  return new Response(`${header}\n${body}\n`, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": "attachment; filename=az-school-vendors.csv",
    },
  });
}

function cell(row: ReturnType<typeof loadVendorLeaderboard>[number], field: (typeof FIELDS)[number]): string | number {
  switch (field) {
    case "vendor_as_printed":
      return row.printedName;
    case "vendor_key":
      return row.vendorKey;
    case "other_printed_forms":
      return row.otherPrintedNames.join("; ");
    case "amount_cents":
      return row.amountCents;
    case "line_count":
      return row.lineCount;
    case "district_count":
      return row.districtCount;
    case "district_breakdown":
      return row.districts.map((district) => `${district.district}: ${district.amountCents} cents, ${district.lineCount} lines`).join("; ");
    case "first_date":
      return row.firstDate ?? "";
    case "last_date":
      return row.lastDate ?? "";
    default: {
      const unreachable: never = field;
      return unreachable;
    }
  }
}

function csv(value: string): string {
  if (/[",\n]/.test(value)) return `"${value.replaceAll('"', '""')}"`;
  return value;
}
