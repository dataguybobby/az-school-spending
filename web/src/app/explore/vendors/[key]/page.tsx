import Link from "next/link";
import { notFound } from "next/navigation";
import { basisLabel, withBasis } from "@/lib/basis";
import { monthExpr, openDb, where, type Filters } from "@/lib/db";
import { dollars } from "@/lib/utils";

export const dynamic = "force-dynamic";

export default async function VendorGroupPage({
  params,
  searchParams,
}: {
  params: Promise<{ key: string }>;
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const { key } = await params;
  if (!/^[A-Z0-9]+$/.test(key)) notFound();
  const raw = await searchParams;
  const filters: Filters = { basis: raw.basis, start: raw.start, end: raw.end };
  const basis = filters.basis || "either";
  const db = openDb();
  const filter = where(filters);
  const sql = `${filter.sql} AND vendor_key = ?`;
  const paramsSql = [...filter.params, key];
  const total = db.prepare(`SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents),0) AS cents FROM lines WHERE ${sql}`).get(...paramsSql) as { n: number; cents: number };
  if (total.n === 0) notFound();
  const forms = db.prepare(
    `SELECT vendor_raw AS label, SUM(amount_cents) AS cents, COUNT(*) AS n FROM lines WHERE ${sql} GROUP BY vendor_raw ORDER BY n DESC, cents DESC`,
  ).all(...paramsSql) as Array<{ label: string; cents: number; n: number }>;
  const display = forms[0]?.label || key;
  const monthColumn = monthExpr(basis);
  const districts = db.prepare(
    `SELECT entity_name AS label, SUM(amount_cents) AS cents, COUNT(*) AS n FROM lines WHERE ${sql} GROUP BY entity_name ORDER BY cents DESC`,
  ).all(...paramsSql) as Array<{ label: string; cents: number; n: number }>;
  const months = db.prepare(
    `SELECT ${monthColumn} AS label, SUM(amount_cents) AS cents, COUNT(*) AS n
     FROM lines WHERE ${sql} AND ${monthColumn} IS NOT NULL AND ${monthColumn} != '' GROUP BY label ORDER BY label`,
  ).all(...paramsSql) as Array<{ label: string; cents: number; n: number }>;
  const joined = where(filters, "l");
  const documents = db.prepare(
    `SELECT d.document_id AS label, d.url, SUM(l.amount_cents) AS cents, COUNT(*) AS n
     FROM lines l JOIN documents d ON d.document_id = l.document_id
     WHERE ${joined.sql} AND l.vendor_key = ?
     GROUP BY d.document_id ORDER BY cents DESC`,
  ).all(...joined.params, key) as Array<{ label: string; url: string | null; cents: number; n: number }>;
  const lines = db.prepare(
    `SELECT line_id, amount_cents, description_public, entity_name, check_date, voucher_batch_date, dac_raw
     FROM lines WHERE ${sql} ORDER BY amount_cents DESC LIMIT 40`,
  ).all(...paramsSql) as Array<{
    line_id: string;
    amount_cents: number;
    description_public: string;
    entity_name: string;
    check_date: string | null;
    voucher_batch_date: string | null;
    dac_raw: string | null;
  }>;

  return (
    <article className="space-y-6">
      <p className="text-sm">
        <Link className="font-semibold text-teal" href={withBasis("/explore", basis)}>Groups</Link>
        {" · "}
        <Link className="font-semibold text-teal" href="/methodology">Methodology</Link>
      </p>
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal">Vendor, not a category</p>
        <h1 className="mt-2 font-extrabold text-4xl">{display}</h1>
        <p className="mt-3 font-extrabold text-5xl">{dollars(total.cents)}</p>
        <p className="mt-3 max-w-3xl text-sm leading-6">
          In the screened public lines in this ledger, {dollars(total.cents)} was reported for this vendor key.
          Date basis: {basisLabel(basis)}. {total.n} lines. This is not unique spend, not a printed report total, and not complete coverage of that vendor or of any district.
        </p>
      </header>
      <SimpleList title="Printed payee forms collapsed into this key" rows={forms} />
      <SimpleList title="District on the line" rows={districts} />
      <SimpleList title="Month on the selected date basis" rows={months} />
      <section className="rounded-xl border border-teal/10 bg-page p-4 text-sm">
        <h2 className="font-semibold">Source documents</h2>
        <ul className="mt-3 space-y-2">
          {documents.map((row) => (
            <li key={row.label} className="flex flex-wrap justify-between gap-2">
              <span>{row.label}{row.url ? <> · <a className="font-semibold text-teal underline" href={row.url}>Official source</a></> : null}</span>
              <span>{dollars(row.cents)} · {row.n}</span>
            </li>
          ))}
        </ul>
      </section>
      <ul className="space-y-2">
        {lines.map((line) => (
          <li key={line.line_id} className="rounded-xl border border-teal/10 bg-page p-3 text-sm">
            <Link className="font-semibold text-teal underline" href={`/lines/${line.line_id}`}>{dollars(line.amount_cents)} · {line.description_public}</Link>
            <p className="text-xs text-teal/60">{line.entity_name} · {line.dac_raw || "no department text"} · {line.check_date ? `check date ${line.check_date}` : line.voucher_batch_date ? `batch date ${line.voucher_batch_date}` : "no confirmed date"}</p>
          </li>
        ))}
      </ul>
    </article>
  );
}

function SimpleList({ title, rows }: { title: string; rows: Array<{ label: string; cents: number; n: number }> }) {
  return (
    <section className="rounded-xl border border-teal/10 bg-page p-4">
      <h2 className="font-semibold">{title}</h2>
      <ul className="mt-3 space-y-1 text-sm">
        {rows.map((row) => (
          <li key={row.label} className="flex justify-between gap-3 border-b border-teal/5 py-1">
            <span>{row.label}</span>
            <span>{dollars(row.cents)} · {row.n}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
