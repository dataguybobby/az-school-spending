import type { DatabaseSync } from "node:sqlite";
import { dateBasis, where, type Filters } from "@/lib/db";
import { dateExpr, pickPrintedName, type DistrictPay, type VendorRank } from "@/lib/vendor-rank";

export function vendorPageSize(): number {
  return 40;
}

export function loadVendorLeaderboard(db: DatabaseSync, filters: Filters, search: string): VendorRank[] {
  const filter = where(filters);
  const dated = dateExpr(dateBasis(filters.basis));
  const params = [...filter.params];
  let searchSql = "";
  const needle = search.trim();
  if (needle) {
    searchSql = " AND (vendor_raw LIKE ? OR vendor_key LIKE ?)";
    params.push(`%${needle}%`, `%${needle.replace(/[^A-Za-z0-9]+/g, "").toUpperCase()}%`);
  }
  const totals = db.prepare(
    `SELECT vendor_key,
            SUM(amount_cents) AS amount_cents,
            COUNT(*) AS line_count,
            COUNT(DISTINCT entity_name) AS district_count,
            MIN(${dated}) AS first_date,
            MAX(${dated}) AS last_date
     FROM lines
     WHERE ${filter.sql}${searchSql}
     GROUP BY vendor_key`,
  ).all(...params) as Array<{
    vendor_key: string;
    amount_cents: number;
    line_count: number;
    district_count: number;
    first_date: string | null;
    last_date: string | null;
  }>;
  const forms = db.prepare(
    `SELECT vendor_key, vendor_raw, COUNT(*) AS line_count
     FROM lines
     WHERE ${filter.sql}${searchSql}
     GROUP BY vendor_key, vendor_raw`,
  ).all(...params) as Array<{ vendor_key: string; vendor_raw: string; line_count: number }>;
  const districts = db.prepare(
    `SELECT vendor_key, entity_name,
            SUM(amount_cents) AS amount_cents,
            COUNT(*) AS line_count,
            MIN(${dated}) AS first_date,
            MAX(${dated}) AS last_date
     FROM lines
     WHERE ${filter.sql}${searchSql}
     GROUP BY vendor_key, entity_name`,
  ).all(...params) as Array<{
    vendor_key: string;
    entity_name: string;
    amount_cents: number;
    line_count: number;
    first_date: string | null;
    last_date: string | null;
  }>;
  const formsByKey = new Map<string, Array<{ name: string; lines: number }>>();
  for (const form of forms) {
    const list = formsByKey.get(form.vendor_key) ?? [];
    list.push({ name: form.vendor_raw, lines: form.line_count });
    formsByKey.set(form.vendor_key, list);
  }
  const districtsByKey = new Map<string, DistrictPay[]>();
  for (const row of districts) {
    const list = districtsByKey.get(row.vendor_key) ?? [];
    list.push({
      district: row.entity_name,
      amountCents: row.amount_cents,
      lineCount: row.line_count,
      firstDate: row.first_date,
      lastDate: row.last_date,
    });
    districtsByKey.set(row.vendor_key, list);
  }
  return totals.map((row) => {
    const chosen = pickPrintedName(formsByKey.get(row.vendor_key) ?? []);
    const pay = (districtsByKey.get(row.vendor_key) ?? []).sort((left, right) => right.amountCents - left.amountCents || left.district.localeCompare(right.district));
    return {
      vendorKey: row.vendor_key,
      printedName: chosen.printed,
      otherPrintedNames: chosen.others,
      amountCents: row.amount_cents,
      lineCount: row.line_count,
      districtCount: row.district_count,
      firstDate: row.first_date,
      lastDate: row.last_date,
      districts: pay,
    };
  });
}
