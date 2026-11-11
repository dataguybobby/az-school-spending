import { NextRequest } from "next/server";
import { openDb, orderBy, where, type Filters } from "@/lib/db";
import { sanitizeCell } from "@/lib/utils";

export const dynamic = "force-dynamic";

const FIELDS = [
  "line_id", "entity_name", "entity_type", "admin_county", "lea_ctds", "check_date",
  "voucher_batch_date", "voucher_batch_number", "fiscal_year_label_native", "period_label_native",
  "vendor_raw", "description_public", "amount_cents", "currency", "category", "category_confidence",
  "dac_raw", "account_code_raw", "po_raw", "document_class", "amount_semantics", "source_url",
  "source_page", "source_row", "flags",
];

export function GET(request: NextRequest) {
  const filters: Filters = Object.fromEntries(request.nextUrl.searchParams.entries());
  const db = openDb();
  const filter = where(filters);
  const rows = db.prepare(
    `SELECT ${FIELDS.join(", ")} FROM lines WHERE ${filter.sql} ORDER BY ${orderBy(filters)} LIMIT 5000`,
  ).all(...filter.params) as Array<Record<string, unknown>>;
  const header = FIELDS.join(",");
  const body = rows.map((row) => FIELDS.map((field) => csv(sanitizeCell(row[field]))).join(",")).join("\n");
  return new Response(`${header}\n${body}\n`, {
    headers: {
      "Content-Type": "text/csv; charset=utf-8",
      "Content-Disposition": "attachment; filename=az-school-spending.csv",
    },
  });
}

function csv(value: string): string {
  if (/[",\n]/.test(value)) return `"${value.replaceAll('"', '""')}"`;
  return value;
}
