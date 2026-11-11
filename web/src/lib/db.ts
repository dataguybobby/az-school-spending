import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";

export type Filters = {
  q?: string;
  source?: string;
  vendor?: string;
  category?: string;
  confidence?: string;
  dac?: string;
  account?: string;
  basis?: string;
  start?: string;
  end?: string;
  sort?: string;
  direction?: string;
  page?: string;
};

const SORTS: Record<string, string> = {
  date: "COALESCE(check_date, voucher_batch_date)",
  amount: "amount_cents",
  vendor: "vendor_raw",
  entity: "entity_name",
};

const BUNDLED = path.join("data", "public", "ledger.sqlite");

let cached: DatabaseSync | undefined;

function bundledSource(): string {
  if (process.env.LEDGER_PUBLIC_DB) return process.env.LEDGER_PUBLIC_DB;
  const candidates = [
    path.join(process.cwd(), BUNDLED),
    path.join(process.cwd(), "..", BUNDLED),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new Error(
    "Screened public ledger not found at web/data/public/ledger.sqlite. Run the local Python ingest, then node web/scripts/prepare-public-db.mjs.",
  );
}

function openReadOnlyCopy(source: string): DatabaseSync {
  const directory = fs.existsSync("/tmp") ? "/tmp" : os.tmpdir();
  const target = path.join(directory, "metro-school-ledger-public.sqlite");
  const sourceStat = fs.statSync(source);
  const stale =
    !fs.existsSync(target) ||
    fs.statSync(target).size !== sourceStat.size ||
    fs.statSync(target).mtimeMs < sourceStat.mtimeMs;
  if (stale) {
    if (fs.existsSync(target)) fs.chmodSync(target, 0o644);
    fs.copyFileSync(source, target);
    fs.chmodSync(target, 0o444);
  }
  return new DatabaseSync(`file:${target}?mode=ro&immutable=1`, { readOnly: true });
}

export function openDb(): DatabaseSync {
  if (!cached) cached = openReadOnlyCopy(bundledSource());
  return cached;
}

function ftsQuery(text: string): string {
  const tokens = text.replace(/[^\p{L}\p{N}\s]/gu, " ").split(/\s+/).filter(Boolean);
  if (tokens.length === 0) return '""';
  return `"${tokens.join(" ")}"`;
}

export function where(filters: Filters, alias = ""): { sql: string; params: Array<string | number> } {
  const column = (name: string) => (alias ? `${alias}.${name}` : name);
  const clauses = [`${column("in_default_aggregate")} = 1`];
  const params: Array<string | number> = [];
  if (filters.source) {
    clauses.push(`${column("source_id")} = ?`);
    params.push(filters.source);
  }
  if (filters.vendor) {
    clauses.push(`${column("vendor_raw")} LIKE ?`);
    params.push(`%${filters.vendor}%`);
  }
  if (filters.category) {
    clauses.push(`${column("category")} = ?`);
    params.push(filters.category);
  }
  if (filters.confidence) {
    clauses.push(`${column("category_confidence")} >= ?`);
    params.push(Number(filters.confidence));
  }
  if (filters.dac) {
    clauses.push(`IFNULL(${column("dac_raw")},'') LIKE ?`);
    params.push(`%${filters.dac}%`);
  }
  if (filters.account) {
    clauses.push(`IFNULL(${column("account_code_raw")},'') LIKE ?`);
    params.push(`%${filters.account}%`);
  }
  if (filters.q) {
    clauses.push(`${column("line_id")} IN (SELECT line_id FROM lines_fts WHERE lines_fts MATCH ?)`);
    params.push(ftsQuery(filters.q));
  }
  const basis = filters.basis || "either";
  if (basis === "check_date") {
    clauses.push(`${column("check_date")} IS NOT NULL`);
    if (filters.start) {
      clauses.push(`${column("check_date")} >= ?`);
      params.push(filters.start);
    }
    if (filters.end) {
      clauses.push(`${column("check_date")} <= ?`);
      params.push(filters.end);
    }
  } else if (basis === "voucher_batch_date") {
    clauses.push(`${column("voucher_batch_date")} IS NOT NULL`);
    if (filters.start) {
      clauses.push(`${column("voucher_batch_date")} >= ?`);
      params.push(filters.start);
    }
    if (filters.end) {
      clauses.push(`${column("voucher_batch_date")} <= ?`);
      params.push(filters.end);
    }
  } else if (filters.start || filters.end) {
    clauses.push(`COALESCE(${column("check_date")}, ${column("voucher_batch_date")}) IS NOT NULL`);
    if (filters.start) {
      clauses.push(`COALESCE(${column("check_date")}, ${column("voucher_batch_date")}) >= ?`);
      params.push(filters.start);
    }
    if (filters.end) {
      clauses.push(`COALESCE(${column("check_date")}, ${column("voucher_batch_date")}) <= ?`);
      params.push(filters.end);
    }
  }
  return { sql: clauses.join(" AND "), params };
}

export function orderBy(filters: Filters): string {
  const column = SORTS[filters.sort || "date"] ?? SORTS.date;
  const direction = filters.direction === "asc" ? "ASC" : "DESC";
  return `${column} ${direction}, line_id ASC`;
}

export function monthExpr(basis: string | undefined): string {
  if (basis === "check_date") return "substr(check_date,1,7)";
  if (basis === "voucher_batch_date") return "substr(voucher_batch_date,1,7)";
  return "substr(COALESCE(check_date, voucher_batch_date),1,7)";
}
