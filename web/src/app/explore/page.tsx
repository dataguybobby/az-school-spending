import Link from "next/link";
import { HowToRead } from "@/components/how-to-read";
import { basisLabel, withBasis } from "@/lib/basis";
import { openDb, where, type Filters } from "@/lib/db";
import { dollars } from "@/lib/utils";

export const dynamic = "force-dynamic";

type ItemGroup = { item_label: string; item_method: string | null; confidence: number | null; cents: number; n: number };
type VendorForm = { vendor_key: string; vendor_raw: string; cents: number; n: number };

export default async function ExplorePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const raw = await searchParams;
  const filters: Filters = { basis: raw.basis, start: raw.start, end: raw.end };
  const db = openDb();
  const filter = where(filters);
  const basis = filters.basis || "either";
  const items = db.prepare(
    `SELECT item_label, item_method, MIN(item_confidence) AS confidence, SUM(amount_cents) AS cents, COUNT(*) AS n
     FROM lines WHERE ${filter.sql} AND item_label IS NOT NULL
     GROUP BY item_label ORDER BY cents DESC`,
  ).all(...filter.params) as ItemGroup[];
  const forms = db.prepare(
    `SELECT vendor_key, vendor_raw, SUM(amount_cents) AS cents, COUNT(*) AS n
     FROM lines WHERE ${filter.sql} GROUP BY vendor_key, vendor_raw`,
  ).all(...filter.params) as VendorForm[];
  const vendors = rollVendors(forms).slice(0, 24);

  return (
    <div className="space-y-8">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal">Screened public lines</p>
        <h1 className="mt-2 font-extrabold text-4xl">Groups</h1>
        <p className="mt-3 text-base leading-7">
          Date basis: {basisLabel(basis)}. <HowToRead anchor="read-groups" />
        </p>
        <form className="mt-4 flex flex-wrap gap-2" action="/explore">
          <select name="basis" defaultValue={basis} className="rounded-md border border-teal/15 px-3 py-2 text-sm">
            <option value="either">Either labeled date</option>
            <option value="check_date">Check date only</option>
            <option value="voucher_batch_date">Voucher batch date only</option>
          </select>
          <button className="rounded-md bg-terracotta px-3 py-2 text-sm font-semibold text-white" type="submit">Apply basis</button>
        </form>
      </header>

      <section>
        <h2 className="font-extrabold text-2xl">Item groups</h2>
        <p className="mt-1 text-base">A reviewed phrase in the description.</p>
        {items.length === 0 ? <p className="mt-3 text-sm">No item group has lines on this date basis.</p> : (
          <ul className="mt-4 grid gap-3 md:grid-cols-2">
            {items.map((item) => (
              <li key={item.item_label} className="rounded-xl border border-teal/10 bg-page p-4">
                <Link className="font-extrabold text-3xl text-teal underline" href={withBasis(`/explore/items/${slug(item.item_label)}`, basis)}>
                  {dollars(item.cents)}
                </Link>
                <p className="mt-2 text-sm">
                  In the screened public lines in this ledger, {dollars(item.cents)} was reported on descriptions grouped as {item.item_label}.
                </p>
                <p className="mt-2 text-xs text-teal/60">
                  {item.n} lines · {item.item_method === "manual_override" ? "reviewer override" : "grouped from description text"}
                  {item.confidence == null ? "" : ` · confidence ${item.confidence}`}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="font-extrabold text-2xl">Vendors</h2>
        <p className="mt-1 text-base">Printed payee that appears most often. <HowToRead anchor="read-vendors" /></p>
        <ul className="mt-4 divide-y divide-teal/10 rounded-xl border border-teal/10 bg-page">
          {vendors.map((vendor) => (
            <li key={vendor.vendor_key} className="flex flex-wrap items-baseline justify-between gap-3 px-4 py-3 text-sm">
              <Link className="font-semibold text-teal underline" href={withBasis(`/explore/vendors/${vendor.vendor_key}`, basis)}>
                {vendor.label}
              </Link>
              <span>{dollars(vendor.cents)} · {vendor.n} lines{vendor.forms > 1 ? ` · ${vendor.forms} printed forms` : ""}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function slug(label: string): string {
  return label.toLowerCase().replace(/\s+/g, "-");
}

function rollVendors(rows: VendorForm[]) {
  const grouped = new Map<string, { label: string; cents: number; n: number; forms: number; best: number }>();
  for (const row of rows) {
    const current = grouped.get(row.vendor_key) ?? { label: row.vendor_raw, cents: 0, n: 0, forms: 0, best: -1 };
    current.cents += row.cents;
    current.n += row.n;
    current.forms += 1;
    if (row.n > current.best || (row.n === current.best && row.vendor_raw.length > current.label.length)) {
      current.label = row.vendor_raw;
      current.best = row.n;
    }
    grouped.set(row.vendor_key, current);
  }
  return [...grouped.entries()]
    .map(([vendor_key, row]) => ({ vendor_key, ...row }))
    .sort((left, right) => right.cents - left.cents);
}
