import Link from "next/link";
import { connection } from "next/server";
import { CategoryPies } from "@/components/category-pies";
import { DistrictBars } from "@/components/district-bars";
import { EnrollmentComparison } from "@/components/enrollment-comparison";
import { HomeSummary } from "@/components/home-summary";
import { HowToRead } from "@/components/how-to-read";
import { SpendEnrollmentChart } from "@/components/spend-enrollment-chart";
import { SpendingFilters } from "@/components/spending-filters";
import { StoryCards } from "@/components/story-cards";
import { VendorTreemap } from "@/components/treemap";
import { activeSort, dateBasis, openDb, orderBy, where, type DateBasis, type Filters, type SortDirection, type SortKey } from "@/lib/db";
import { basisLabel } from "@/lib/basis";
import { loadDistrictPies, loadSpendChart } from "@/lib/chart-data";
import { hasNarrowingFilter, loadComparisons } from "@/lib/enrollment";
import { dollars } from "@/lib/utils";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type Line = Record<string, string | number | null>;

export default async function SpendingPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  await connection();
  const raw = await searchParams;
  const filters: Filters = { ...raw };
  const db = openDb();
  const filter = where(filters);
  const page = Math.max(Number(filters.page || "1"), 1);
  const limit = 40;
  const offset = (page - 1) * limit;
  const totals = db.prepare(
    `SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents),0) AS cents FROM lines WHERE ${filter.sql}`,
  ).get(...filter.params) as { n: number; cents: number };
  const rows = db.prepare(
    `SELECT * FROM lines WHERE ${filter.sql} ORDER BY ${orderBy(filters)} LIMIT ? OFFSET ?`,
  ).all(...filter.params, limit, offset) as Line[];
  const vendorRows = db.prepare(
    `SELECT vendor_raw, SUM(amount_cents) AS amount_cents, COUNT(*) AS line_count
     FROM lines WHERE ${filter.sql} GROUP BY vendor_key ORDER BY amount_cents DESC LIMIT 8`,
  ).all(...filter.params) as Array<{ vendor_raw: string; amount_cents: number; line_count: number }>;
  const documents = db.prepare(
    "SELECT document_id, period_label_native, reconciliation_status, indexed, public_line_count, withheld_count, printed_total_cents, printed_total_null_reason, parsed_outcome FROM documents ORDER BY period_start",
  ).all() as Line[];
  const overlap = db.prepare("SELECT * FROM overlap_findings").all() as Line[];
  const entities = db.prepare("SELECT DISTINCT entity_name, source_id FROM lines ORDER BY entity_name").all() as Array<{ entity_name: string; source_id: string }>;
  const basis = filters.basis || "either";
  const sorting = activeSort(filters);
  const districts = db.prepare(
    `SELECT entity_name, SUM(amount_cents) AS amount_cents, COUNT(*) AS line_count, COUNT(DISTINCT document_id) AS documents
     FROM lines WHERE ${filter.sql} GROUP BY entity_name ORDER BY amount_cents DESC`,
  ).all(...filter.params) as Array<{ entity_name: string; amount_cents: number; line_count: number; documents: number }>;
  const vendorParts = db.prepare(
    `SELECT vendor_key, vendor_raw, SUM(amount_cents) AS amount_cents, COUNT(*) AS line_count
     FROM lines WHERE ${filter.sql} GROUP BY vendor_key, vendor_raw`,
  ).all(...filter.params) as Array<{ vendor_key: string; vendor_raw: string; amount_cents: number; line_count: number }>;
  const treemap = treemapSlices(vendorParts);
  const stories = db.prepare(
    `SELECT line_id, amount_cents, vendor_raw, description_public, entity_name, check_date, voucher_batch_date, dac_raw
     FROM lines WHERE in_default_aggregate = 1 AND (
       (description_public = '24 pack slow rise stress balls' AND amount_cents = 2063)
       OR (description_public = 'Tisaindor 100PCS Panda Stickers' AND amount_cents = 6469)
     ) ORDER BY amount_cents`,
  ).all() as Array<{
    line_id: string;
    amount_cents: number;
    vendor_raw: string;
    description_public: string;
    entity_name: string;
    check_date: string | null;
    voucher_batch_date: string | null;
    dac_raw: string | null;
  }>;
  const stress = db.prepare(
    `SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents),0) AS cents, COUNT(DISTINCT entity_name) AS districts, COUNT(DISTINCT vendor_key) AS vendors
     FROM lines WHERE ${filter.sql} AND item_label = 'stress balls'`,
  ).get(...filter.params) as { n: number; cents: number; districts: number; vendors: number };
  const unknown = db.prepare(
    basis === "check_date"
      ? "SELECT COUNT(*) AS n FROM lines WHERE check_date IS NULL"
      : basis === "voucher_batch_date"
        ? "SELECT COUNT(*) AS n FROM lines WHERE voucher_batch_date IS NULL"
        : "SELECT COUNT(*) AS n FROM lines WHERE check_date IS NULL AND voucher_batch_date IS NULL",
  ).get() as { n: number };
  const exportQuery = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    if (value && key !== "page") exportQuery.set(key, value);
  }
  const pages = Math.max(Math.ceil(totals.n / limit), 1);
  const enrollmentRows = loadComparisons(db, filters);
  const pies = loadDistrictPies(db, filters);
  const spendChart = loadSpendChart(db, filters);

  return (
    <div className="space-y-6">
      <section className="hero-figure rounded-xl border border-teal/10 bg-page p-5">
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-teal">Screened public lines</p>
        <h1 className="mt-2 font-extrabold text-4xl leading-tight">Reported spending lines</h1>
        <p className="hero-total mt-4 font-extrabold">{dollars(totals.cents)}</p>
        <p className="mt-2 text-base">
          Reported / vouchered. Date basis: {basisLabel(basis)}. <span className="font-semibold">{totals.n.toLocaleString()} public lines</span> in this filter.
          {unknown.n > 0 ? ` ${unknown.n.toLocaleString()} lines have no date on this basis.` : ""}
          {" "}
          <HowToRead anchor="read-totals" />
        </p>
      </section>

      <HomeSummary vendors={vendorRows} districts={districts} comparisons={enrollmentRows} />

      <SpendingFilters raw={raw} filters={filters} basis={basis} sorting={sorting} entities={entities} />

      <CategoryPies pies={pies} />
      <SpendEnrollmentChart chart={spendChart} />
      <VendorTreemap slices={treemap} />
      <DistrictBars rows={districts} />
      <EnrollmentComparison
        rows={enrollmentRows}
        basisName={basisLabel(basis)}
        filterNote={hasNarrowingFilter(filters) ? "The amounts in this section follow the current filter. The October 1 headcount stays the official district total." : null}
      />
      {stress.n > 0 ? (
        <p className="rounded-xl border border-teal/10 bg-page px-4 py-3 text-base leading-6">
          {dollars(stress.cents)} was reported on descriptions grouped as stress balls
          ({stress.n} lines, {stress.districts} district name{stress.districts === 1 ? "" : "s"}, {stress.vendors} vendor key{stress.vendors === 1 ? "" : "s"}).
          {" "}
          <Link className="font-semibold text-teal underline" href={`/explore/items/stress-balls${basis === "either" ? "" : `?basis=${basis}`}`}>See the breakdown</Link>
        </p>
      ) : null}
      <StoryCards stories={stories} />

      <section id="lines" className="overflow-x-auto rounded-xl border border-teal/10 bg-page">
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <div>
            <h2 className="font-semibold">Lines</h2>
            <p className="text-xs text-teal/70">{sortStatus(sorting.sort, sorting.direction, dateBasis(basis))}</p>
          </div>
          <a className="text-sm font-semibold text-teal underline" href={`/api/export?${exportQuery.toString()}`}>Download CSV</a>
        </div>
        <table className="w-full min-w-[760px] text-left text-base">
          <thead className="border-y border-teal/10 text-sm uppercase tracking-wide text-teal/60">
            <tr>
              <SortHeader label="Date used" column="date" sorting={sorting} raw={raw} />
              <th scope="col" className="px-3 py-2">Entity</th>
              <th scope="col" className="px-3 py-2">Vendor</th>
              <th scope="col" className="px-3 py-2">Description</th>
              <SortHeader label="Amount" column="amount" sorting={sorting} raw={raw} />
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={5} className="px-3 py-6 text-teal/70">No public lines match. That can mean the date basis excludes voucher rows, or the period was not indexed.</td></tr>
            ) : rows.map((row) => (
              <tr key={String(row.line_id)} className="border-b border-teal/5 align-top">
                <td className="px-3 py-2 whitespace-nowrap">
                  {row.check_date ? <span>Check {row.check_date}</span> : <span>Batch {row.voucher_batch_date || "unknown"}</span>}
                </td>
                <td className="px-3 py-2">{row.entity_name}</td>
                <td className="px-3 py-2">{row.vendor_raw}</td>
                <td className="px-3 py-2">
                  <Link className="font-semibold text-teal underline" href={`/lines/${row.line_id}`}>{row.description_public}</Link>
                  <div className="text-xs text-teal/60">{row.category} · {row.dac_raw || row.account_code_raw || "no DAC or account"}</div>
                </td>
                <td className="px-3 py-2 whitespace-nowrap font-semibold">{dollars(Number(row.amount_cents))}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex items-center justify-between px-4 py-3 text-sm">
          <span>Page {page} of {pages}</span>
          <span className="flex gap-3">
            {page > 1 ? <Link className="font-semibold text-teal" href={pageHref(raw, page - 1)}>Previous</Link> : null}
            {page < pages ? <Link className="font-semibold text-teal" href={pageHref(raw, page + 1)}>Next</Link> : null}
          </span>
        </div>
      </section>

      <section className="rounded-xl border border-teal/10 bg-page p-4 text-sm">
        <h2 className="font-semibold">Indexed document windows</h2>
        <p className="mt-1"><HowToRead anchor="read-sources" /></p>
        <ul className="mt-2 space-y-1">
          {documents.map((doc) => (
            <li key={String(doc.document_id)}>
              {doc.indexed ? "Indexed" : "Not indexed"} · {doc.period_label_native || doc.document_id} · {doc.reconciliation_status} · {doc.parsed_outcome} · printed total {doc.printed_total_cents == null ? String(doc.printed_total_null_reason || "not extracted") : dollars(Number(doc.printed_total_cents))} · {doc.public_line_count} default-aggregate lines, {doc.withheld_count} withheld
            </li>
          ))}
        </ul>
        {overlap.map((finding) => (
          <p key={String(finding.left_document_id) + String(finding.right_document_id)} className="mt-3 text-teal/80">
            {finding.verdict}: {finding.note} Recurring different-date keys kept: {finding.recurring_different_date_keys}. Rows on the shared header dates: {finding.rows_on_shared_header_dates}.
          </p>
        ))}
      </section>
    </div>
  );
}

function treemapSlices(rows: Array<{ vendor_key: string; vendor_raw: string; amount_cents: number; line_count: number }>) {
  const grouped = new Map<string, { label: string; amount_cents: number; lines: number; forms: Array<[string, number]> }>();
  for (const row of rows) {
    const current = grouped.get(row.vendor_key) ?? { label: row.vendor_raw, amount_cents: 0, lines: 0, forms: [] };
    current.amount_cents += row.amount_cents;
    current.lines += row.line_count;
    current.forms.push([row.vendor_raw, row.line_count]);
    grouped.set(row.vendor_key, current);
  }
  const ranked = [...grouped.values()].sort((left, right) => right.amount_cents - left.amount_cents);
  for (const row of ranked) {
    row.label = row.forms.sort((left, right) => right[1] - left[1] || right[0].length - left[0].length)[0][0];
  }
  const top = ranked.slice(0, 8).map((row) => ({ label: row.label, amount_cents: row.amount_cents, lines: row.lines }));
  const rest = ranked.slice(8);
  if (rest.length > 0) {
    top.push({
      label: "Other screened vendors",
      amount_cents: rest.reduce((sum, row) => sum + row.amount_cents, 0),
      lines: rest.reduce((sum, row) => sum + row.lines, 0),
    });
  }
  return top;
}

function pageHref(raw: Record<string, string | undefined>, page: number): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    if (value && key !== "page") params.set(key, value);
  }
  params.set("page", String(page));
  return `/?${params.toString()}#lines`;
}

function sortHref(raw: Record<string, string | undefined>, sort: "date" | "amount", direction: SortDirection): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    if (!value || key === "sort" || key === "direction") continue;
    params.set(key, value);
  }
  if (!(sort === "date" && direction === "desc")) {
    params.set("sort", sort);
    params.set("direction", direction);
  }
  const query = params.toString();
  return query ? `/?${query}#lines` : "/#lines";
}

function SortHeader({
  label,
  column,
  sorting,
  raw,
}: {
  label: string;
  column: "date" | "amount";
  sorting: { sort: SortKey; direction: SortDirection };
  raw: Record<string, string | undefined>;
}) {
  const isActive = sorting.sort === column;
  const nextDirection: SortDirection = isActive && sorting.direction === "desc" ? "asc" : "desc";
  const currentPhrase = columnPhrase(column, sorting.direction);
  const nextPhrase = columnPhrase(column, nextDirection);
  return (
    <th scope="col" aria-sort={isActive ? (sorting.direction === "asc" ? "ascending" : "descending") : "none"} className="px-3 py-2">
      <Link
        href={sortHref(raw, column, nextDirection)}
        className={isActive ? "font-semibold text-teal underline decoration-2 underline-offset-2" : "underline decoration-teal/30 underline-offset-2 hover:text-teal"}
      >
        {label}
        {isActive ? <span aria-hidden="true">{sorting.direction === "asc" ? " ↑" : " ↓"}</span> : null}
        <span className="sr-only">
          {isActive ? `, sorted ${currentPhrase}. Activate to sort ${nextPhrase}.` : `. Activate to sort ${nextPhrase}.`}
        </span>
      </Link>
    </th>
  );
}

function columnPhrase(column: "date" | "amount", direction: SortDirection): string {
  const order = direction === "asc";
  switch (column) {
    case "amount":
      return order ? "smallest first" : "largest first";
    case "date":
      return order ? "oldest first" : "newest first";
    default: {
      const unreachable: never = column;
      return unreachable;
    }
  }
}

function sortStatus(sort: SortKey, direction: SortDirection, basis: DateBasis): string {
  switch (sort) {
    case "amount":
      return direction === "asc" ? "Sorted by amount, smallest first." : "Sorted by amount, largest first.";
    case "vendor":
      return direction === "asc" ? "Sorted by vendor, A to Z." : "Sorted by vendor, Z to A.";
    case "entity":
      return direction === "asc" ? "Sorted by entity, A to Z." : "Sorted by entity, Z to A.";
    case "date":
      return `Sorted by ${dateSortLabel(basis)}, ${direction === "asc" ? "oldest first" : "newest first"}.`;
    default: {
      const unreachable: never = sort;
      return unreachable;
    }
  }
}

function dateSortLabel(basis: DateBasis): string {
  switch (basis) {
    case "check_date":
      return "check date";
    case "voucher_batch_date":
      return "voucher batch date";
    case "either":
      return "check date when present, otherwise voucher batch date";
    default: {
      const unreachable: never = basis;
      return unreachable;
    }
  }
}
