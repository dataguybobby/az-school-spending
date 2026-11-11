import Link from "next/link";
import { BarChart } from "@/components/charts";
import { DistrictBars } from "@/components/district-bars";
import { StoryCards } from "@/components/story-cards";
import { VendorTreemap } from "@/components/treemap";
import { ButtonLink } from "@/components/ui/button";
import { monthExpr, openDb, orderBy, where, type Filters } from "@/lib/db";
import { basisLabel } from "@/lib/basis";
import { dollars } from "@/lib/utils";

export const dynamic = "force-dynamic";

type Line = Record<string, string | number | null>;

export default async function SpendingPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
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
  const monthColumn = monthExpr(filters.basis);
  const months = db.prepare(
    `SELECT ${monthColumn} AS month, SUM(amount_cents) AS amount_cents, COUNT(*) AS line_count
     FROM lines WHERE ${filter.sql} AND ${monthColumn} IS NOT NULL AND ${monthColumn} != ''
     GROUP BY month ORDER BY month`,
  ).all(...filter.params) as Array<{ month: string; amount_cents: number }>;
  const cats = db.prepare(
    `SELECT category, SUM(amount_cents) AS amount_cents, COUNT(*) AS line_count
     FROM lines WHERE ${filter.sql} GROUP BY category ORDER BY amount_cents DESC`,
  ).all(...filter.params) as Array<{ category: string; amount_cents: number; line_count: number }>;
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

  return (
    <div className="space-y-6">
      <section className="hero-figure rounded-xl border border-teal/10 bg-page p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal">Screened public lines</p>
        <h1 className="mt-2 max-w-3xl font-extrabold text-4xl leading-tight">Reported spending lines</h1>
        <p className="mt-4 font-extrabold text-5xl tracking-tight">{dollars(totals.cents)}</p>
        <p className="mt-2 text-sm">
          Date basis: {basisLabel(basis)}. <span className="font-semibold">{totals.n.toLocaleString()} public lines</span> in this filter.
          Across the index, {unknown.n.toLocaleString()} lines have no date on this basis and stay out of a dated filter.
        </p>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-teal/75">
          This figure is the sum of screened public lines on that date basis. It is not unique spend, not the printed report total, not proof a payment settled, and not a census of districts or of Arizona schools.
          Personal payees, unknown payees, and sensitive description text are withheld. A month with no bar was not indexed, not recorded as zero.
        </p>
        {stress.n > 0 ? (
          <p className="mt-4 max-w-3xl rounded-lg bg-cream px-3 py-2 text-sm leading-6">
            In the screened public lines in this filter, {dollars(stress.cents)} was reported on descriptions grouped as stress balls
            ({stress.n} lines, {stress.districts} district name{stress.districts === 1 ? "" : "s"}, {stress.vendors} vendor key{stress.vendors === 1 ? "" : "s"}).
            {" "}
            <Link className="font-semibold text-teal underline" href={`/explore/items/stress-balls${basis === "either" ? "" : `?basis=${basis}`}`}>See the breakdown</Link>
            {" · "}
            <Link className="font-semibold text-teal underline" href="/explore">All groups</Link>
          </p>
        ) : null}
      </section>

      <form className="grid gap-3 rounded-xl border border-teal/10 bg-page p-4 md:grid-cols-4" action="/">
        <label className="text-sm md:col-span-2">Description, vendor, or account
          <input name="q" defaultValue={filters.q || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <label className="text-sm">Date basis
          <select name="basis" defaultValue={basis} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2">
            <option value="either">Either labeled date</option>
            <option value="check_date">Check date only</option>
            <option value="voucher_batch_date">Voucher batch date only</option>
          </select>
        </label>
        <label className="text-sm">Entity
          <select name="source" defaultValue={filters.source || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2">
            <option value="">All indexed</option>
            {entities.map((entity) => <option key={entity.source_id} value={entity.source_id}>{entity.entity_name}</option>)}
          </select>
        </label>
        <label className="text-sm">From
          <input type="date" name="start" defaultValue={filters.start || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <label className="text-sm">Through
          <input type="date" name="end" defaultValue={filters.end || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <label className="text-sm">Vendor contains
          <input name="vendor" defaultValue={filters.vendor || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <label className="text-sm">Category
          <select name="category" defaultValue={filters.category || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2">
            <option value="">Any</option>
            {["unclassified","utilities","communications","insurance","instructional_materials","technology","facilities","transport","food","professional_services","student_support","staff_activities"].map((item) => (
              <option key={item} value={item}>{item.replaceAll("_", " ")}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">Minimum category confidence
          <input name="confidence" defaultValue={filters.confidence || ""} placeholder="0.5" className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <label className="text-sm">School or department text
          <input name="dac" defaultValue={filters.dac || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <label className="text-sm">Account code contains
          <input name="account" defaultValue={filters.account || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <div className="flex flex-wrap items-end gap-2">
          <button className="rounded-md bg-terracotta px-3 py-2 text-sm font-semibold text-white" type="submit">Apply</button>
          <ButtonLink href="/?basis=check_date&start=2025-07-01" variant="ghost">Check dates from July 1, 2025</ButtonLink>
        </div>
      </form>

      <div className="grid gap-4 lg:grid-cols-2">
        <BarChart
          title={basis === "voucher_batch_date" ? "Voucher batch month (not a payment date)" : basis === "check_date" ? "Check-date month" : "Labeled month"}
          bars={months.map((month) => ({ label: month.month.slice(2), amount_cents: month.amount_cents, note: month.month }))}
          empty="No indexed lines have a date on this basis inside the filter."
        />
        <BarChart
          title="Inferred category, not a budget code"
          bars={cats.map((cat) => ({ label: cat.category.replaceAll("_", " ").slice(0, 18), amount_cents: cat.amount_cents, note: `${cat.line_count} lines` }))}
          empty="No lines in this filter."
        />
      </div>

      <VendorTreemap slices={treemap} />
      <DistrictBars rows={districts} />
      <StoryCards stories={stories} />

      <section className="rounded-xl border border-teal/10 bg-page p-4">
        <h2 className="font-semibold">Business vendors in this filter</h2>
        <ul className="mt-3 grid gap-2 text-sm md:grid-cols-2">
          {vendorRows.map((vendor) => (
            <li key={vendor.vendor_raw} className="flex justify-between gap-3 border-b border-teal/5 py-1">
              <span>{vendor.vendor_raw}</span>
              <span className="shrink-0 font-semibold">{dollars(vendor.amount_cents)} · {vendor.line_count}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="overflow-x-auto rounded-xl border border-teal/10 bg-page">
        <div className="flex items-center justify-between gap-3 px-4 py-3">
          <h2 className="font-semibold">Lines</h2>
          <a className="text-sm font-semibold text-teal underline" href={`/api/export?${exportQuery.toString()}`}>Download CSV</a>
        </div>
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-y border-teal/10 text-xs uppercase tracking-wide text-teal/60">
            <tr>
              <th className="px-3 py-2">Date used</th>
              <th className="px-3 py-2">Entity</th>
              <th className="px-3 py-2">Vendor</th>
              <th className="px-3 py-2">Description</th>
              <th className="px-3 py-2">Amount</th>
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
        <ul className="mt-2 space-y-1">
          {documents.map((doc) => (
            <li key={String(doc.document_id)}>
              {doc.indexed ? "Indexed" : "Not in spending totals, and not zero spending"} · {doc.period_label_native || doc.document_id} · {doc.reconciliation_status} · {doc.parsed_outcome} · printed total {doc.printed_total_cents == null ? String(doc.printed_total_null_reason || "not extracted") : dollars(Number(doc.printed_total_cents))} · {doc.public_line_count} default-aggregate lines, {doc.withheld_count} withheld
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
  return `/?${params.toString()}`;
}
