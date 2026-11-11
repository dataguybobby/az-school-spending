import Link from "next/link";
import { notFound } from "next/navigation";
import { HowToRead } from "@/components/how-to-read";
import { basisLabel, withBasis } from "@/lib/basis";
import { monthExpr, openDb, where, type Filters } from "@/lib/db";
import { dollars } from "@/lib/utils";

export const dynamic = "force-dynamic";

type MoneyRow = { label: string; cents: number; n: number };
type LineRow = {
  line_id: string;
  amount_cents: number;
  vendor_raw: string;
  description_public: string;
  entity_name: string;
  dac_raw: string | null;
  check_date: string | null;
  voucher_batch_date: string | null;
  source_url: string | null;
  document_id: string;
  item_evidence: string | null;
  item_method: string | null;
  item_confidence: number | null;
};

export default async function ItemGroupPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { slug } = await params;
  const raw = await searchParams;
  const filters: Filters = { basis: raw.basis, start: raw.start, end: raw.end };
  const basis = filters.basis || "either";
  const db = openDb();
  const known = db.prepare(
    "SELECT DISTINCT item_label FROM lines WHERE item_label IS NOT NULL",
  ).all() as Array<{ item_label: string }>;
  const label = known.find((row) => slugify(row.item_label) === slug)?.item_label;
  if (!label) notFound();
  const filter = where(filters);
  const sql = `${filter.sql} AND item_label = ?`;
  const paramsSql = [...filter.params, label];
  const total = db.prepare(`SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents),0) AS cents FROM lines WHERE ${sql}`).get(...paramsSql) as { n: number; cents: number };
  const meta = db.prepare(
    `SELECT item_method, MIN(item_confidence) AS confidence FROM lines WHERE ${sql}`,
  ).get(...paramsSql) as { item_method: string | null; confidence: number | null };
  const monthColumn = monthExpr(basis);
  const districts = grouped(db, `entity_name`, sql, paramsSql);
  const sites = grouped(db, `IFNULL(dac_raw, 'No department or site text on the row')`, sql, paramsSql);
  const months = db.prepare(
    `SELECT ${monthColumn} AS label, SUM(amount_cents) AS cents, COUNT(*) AS n
     FROM lines WHERE ${sql} AND ${monthColumn} IS NOT NULL AND ${monthColumn} != ''
     GROUP BY label ORDER BY label`,
  ).all(...paramsSql) as MoneyRow[];
  const vendors = grouped(db, "vendor_raw", sql, paramsSql);
  const joined = where(filters, "l");
  const documents = db.prepare(
    `SELECT d.document_id AS label, d.url, SUM(l.amount_cents) AS cents, COUNT(*) AS n
     FROM lines l JOIN documents d ON d.document_id = l.document_id
     WHERE ${joined.sql} AND l.item_label = ?
     GROUP BY d.document_id ORDER BY cents DESC`,
  ).all(...joined.params, label) as Array<MoneyRow & { url: string | null }>;
  const lines = db.prepare(
    `SELECT line_id, amount_cents, vendor_raw, description_public, entity_name, dac_raw, check_date, voucher_batch_date, source_url, document_id, item_evidence, item_method, item_confidence
     FROM lines WHERE ${sql} ORDER BY amount_cents DESC, line_id LIMIT 80`,
  ).all(...paramsSql) as LineRow[];

  return (
    <article className="space-y-6">
      <p className="text-sm">
        <Link className="font-semibold text-teal" href={withBasis("/explore", basis)}>Groups</Link>
        {" · "}
        <Link className="font-semibold text-teal" href="/methodology">Methodology</Link>
      </p>
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal">
          {meta.item_method === "manual_override" ? "Reviewer override" : "Grouped from description text"}
          {meta.confidence == null ? "" : ` · confidence ${meta.confidence}`}
        </p>
        <h1 className="mt-2 font-extrabold text-4xl">{label}</h1>
        <p className="mt-3 font-extrabold text-5xl">{dollars(total.cents)}</p>
        <p className="mt-3 text-base leading-7">
          {dollars(total.cents)} was reported on descriptions grouped as {label}. Date basis: {basisLabel(basis)}. {total.n} lines.{" "}
          <HowToRead anchor="read-groups" />
        </p>
      </header>
      <Breakdown title="District on the line" rows={districts} />
      <Breakdown title="Department or site text, as printed" rows={sites} />
      <Breakdown title={basis === "check_date" ? "Check-date month" : basis === "voucher_batch_date" ? "Voucher-batch month" : "Labeled month"} rows={months} />
      <Breakdown title="Vendor, as printed" rows={vendors} />
      <section className="rounded-xl border border-teal/10 bg-page p-4">
        <h2 className="font-semibold">Source documents</h2>
        <ul className="mt-3 space-y-2 text-sm">
          {documents.map((row) => (
            <li key={row.label} className="flex flex-wrap justify-between gap-2">
              <span>
                {row.label}
                {row.url ? <> · <a className="font-semibold text-teal underline" href={row.url}>Official source</a></> : null}
              </span>
              <span>{dollars(row.cents)} · {row.n}</span>
            </li>
          ))}
        </ul>
      </section>
      <section className="overflow-x-auto rounded-xl border border-teal/10 bg-page">
        <h2 className="px-4 py-3 font-semibold">Lines</h2>
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-y border-teal/10 text-xs uppercase tracking-wide text-teal/60">
            <tr>
              <th className="px-3 py-2">When</th>
              <th className="px-3 py-2">District</th>
              <th className="px-3 py-2">Vendor</th>
              <th className="px-3 py-2">Description</th>
              <th className="px-3 py-2">Amount</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => (
              <tr key={line.line_id} className="border-b border-teal/5 align-top">
                <td className="px-3 py-2 whitespace-nowrap">{line.check_date ? `Check ${line.check_date}` : line.voucher_batch_date ? `Batch ${line.voucher_batch_date}` : "No confirmed date"}</td>
                <td className="px-3 py-2">{line.entity_name}<div className="text-xs text-teal/55">{line.dac_raw || "No department text"}</div></td>
                <td className="px-3 py-2">{line.vendor_raw}</td>
                <td className="px-3 py-2">
                  <Link className="font-semibold text-teal underline" href={`/lines/${line.line_id}`}>{line.description_public}</Link>
                  <div className="text-xs text-teal/55">Evidence “{line.item_evidence}”</div>
                </td>
                <td className="px-3 py-2 font-semibold">{dollars(line.amount_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </article>
  );
}

function slugify(label: string): string {
  return label.toLowerCase().replace(/\s+/g, "-");
}

function grouped(db: ReturnType<typeof openDb>, expression: string, sql: string, params: Array<string | number>): MoneyRow[] {
  return db.prepare(
    `SELECT ${expression} AS label, SUM(amount_cents) AS cents, COUNT(*) AS n
     FROM lines WHERE ${sql} GROUP BY label ORDER BY cents DESC`,
  ).all(...params) as MoneyRow[];
}

function Breakdown({ title, rows }: { title: string; rows: MoneyRow[] }) {
  return (
    <section className="rounded-xl border border-teal/10 bg-page p-4">
      <h2 className="font-semibold">{title}</h2>
      {rows.length === 0 ? <p className="mt-2 text-sm">No dated rows in this slice.</p> : (
        <ul className="mt-3 space-y-1 text-sm">
          {rows.map((row) => (
            <li key={row.label} className="flex justify-between gap-3 border-b border-teal/5 py-1">
              <span>{row.label}</span>
              <span className="shrink-0">{dollars(row.cents)} · {row.n}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
