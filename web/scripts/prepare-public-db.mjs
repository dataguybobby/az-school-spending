import fs from "node:fs";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const bundled = path.join(webRoot, "data", "public", "ledger.sqlite");
const parent = path.resolve(webRoot, "..", "data", "public", "ledger.sqlite");
const allowedTables = new Set([
  "coverage_notes",
  "documents",
  "lines",
  "lines_fts",
  "lines_fts_config",
  "lines_fts_content",
  "lines_fts_data",
  "lines_fts_docsize",
  "lines_fts_idx",
  "october1_enrollment",
  "october1_extracts",
  "october1_focus",
  "october1_index_leas",
  "october1_screened_by_school_year",
  "october1_screened_undated",
  "october1_unmatched_charters",
  "october1_workbooks",
  "overlap_findings",
  "sources",
]);

function fail(message) {
  console.error(`public ledger check failed: ${message}`);
  process.exit(1);
}

function assertBundleTree() {
  const dataRoot = path.join(webRoot, "data");
  if (!fs.existsSync(dataRoot)) return;
  const stack = [dataRoot];
  while (stack.length) {
    const current = stack.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const full = path.join(current, entry.name);
      const relative = path.relative(webRoot, full);
      if (relative.includes(`${path.sep}raw${path.sep}`) || relative.endsWith(`${path.sep}raw`) || relative.includes(`${path.sep}private${path.sep}`) || relative.endsWith(`${path.sep}private`)) {
        fail(`refusing to bundle ${relative}`);
      }
      if (entry.isDirectory()) stack.push(full);
      else if (full !== bundled) fail(`unexpected file in web/data: ${relative}`);
    }
  }
}

if (fs.existsSync(parent)) {
  fs.mkdirSync(path.dirname(bundled), { recursive: true });
  const parentNewer = !fs.existsSync(bundled) || fs.statSync(parent).mtimeMs > fs.statSync(bundled).mtimeMs;
  if (parentNewer) fs.copyFileSync(parent, bundled);
}

if (!fs.existsSync(bundled)) fail("web/data/public/ledger.sqlite is missing");
assertBundleTree();

const db = new DatabaseSync(`file:${bundled}?mode=ro&immutable=1`, { readOnly: true });
const tables = db.prepare("SELECT name FROM sqlite_master WHERE type IN ('table','view')").all().map((row) => row.name);
for (const name of tables) {
  if (!allowedTables.has(name)) fail(`unexpected table ${name}`);
}
const lineColumns = db.prepare("PRAGMA table_info(lines)").all().map((row) => row.name);
if (lineColumns.includes("check_number") || lineColumns.includes("check_number_raw") || lineColumns.includes("description_raw")) {
  fail("public lines table has a private column");
}
const sensitive = db.prepare(
  "SELECT COUNT(*) AS n FROM lines WHERE lower(description_public || ' ' || vendor_raw) LIKE '%authorized user%' OR upper(description_public || ' ' || vendor_raw) LIKE '% IEP%' OR upper(description_public || ' ' || vendor_raw) LIKE '%IEP %' OR upper(description_public || ' ' || vendor_raw) LIKE '%MEDICAID%'",
).get();
if (sensitive.n !== 0) fail(`sensitive descriptions in public lines: ${sensitive.n}`);
const fixture = db.prepare(
  "SELECT amount_cents, dac_raw FROM lines WHERE description_public = ? AND in_default_aggregate = 1",
).get("24 pack slow rise stress balls");
if (!fixture || fixture.amount_cents !== 2063 || fixture.dac_raw !== "Mohave Middle School") {
  fail("stress-ball fixture missing from bundled public database");
}
const fts = db.prepare("SELECT COUNT(*) AS n FROM lines_fts WHERE lines_fts MATCH ?").get('"panda stickers"');
if (!fts || fts.n < 1) fail("FTS query failed on bundled public database");
const susd = db.prepare(
  "SELECT total_oct1_enrollment AS n FROM october1_enrollment WHERE school_year = '2025-2026' AND lea_entity_id = '4240' AND same_basis_as_2017_18_plus = 1",
).get();
if (!susd || susd.n !== 20180) fail("Scottsdale 2025-2026 October 1 enrollment missing");
const filled = db.prepare(
  "SELECT COUNT(*) AS n FROM october1_enrollment WHERE total_as_printed IN ('*', '') AND total_oct1_enrollment IS NOT NULL",
).get();
if (filled.n !== 0) fail("suppressed October 1 total was filled");
const screened = db.prepare("SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents), 0) AS cents FROM lines WHERE in_default_aggregate = 1").get();
if (screened.n !== 14387 || screened.cents !== 2155944882) fail("screened spending total changed while enrollment was loaded");
console.log(`public ledger ok: ${bundled}`);
