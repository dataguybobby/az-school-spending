import Link from "next/link";
import { HowToRead } from "@/components/how-to-read";
import { basisLabel } from "@/lib/basis";
import { openDb, type Filters } from "@/lib/db";
import { dollars } from "@/lib/utils";
import { loadVendorLeaderboard, vendorPageSize } from "@/lib/vendor-leaderboard";
import {
  sortDirection,
  vendorOrder,
  vendorSort,
  type SortDirection,
  type VendorRank,
  type VendorSort,
} from "@/lib/vendor-rank";

export const dynamic = "force-dynamic";

const LABEL = "Amount paid to vendor by indexed districts (reported / vouchered)";
const TOP = 25;

export default async function VendorsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const raw = await searchParams;
  const filters: Filters = { source: raw.source, basis: raw.basis, start: raw.start, end: raw.end };
  const basis = filters.basis || "either";
  const sorting = { sort: vendorSort(raw.sort), direction: sortDirection(raw.direction) };
  const search = raw.q || "";
  const showAll = raw.all === "1";
  const page = Math.max(Number(raw.page || "1"), 1);
  const db = openDb();
  const districts = db.prepare(
    "SELECT DISTINCT source_id, entity_name FROM lines WHERE in_default_aggregate = 1 ORDER BY entity_name",
  ).all() as Array<{ source_id: string; entity_name: string }>;
  const ranked = loadVendorLeaderboard(db, filters, search).sort(vendorOrder(sorting.sort, sorting.direction));
  const pageSize = vendorPageSize();
  const pages = Math.max(Math.ceil(ranked.length / pageSize), 1);
  const visible = showAll ? ranked.slice((page - 1) * pageSize, page * pageSize) : ranked.slice(0, TOP);
  const exportQuery = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    if (value && key !== "page") exportQuery.set(key, value);
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal">Screened public lines</p>
        <h1 className="mt-2 font-extrabold text-4xl leading-tight">{LABEL}</h1>
        <p className="mt-3 text-base leading-7">
          {showAll ? "All" : `Top ${Math.min(TOP, ranked.length)} of`} {ranked.length.toLocaleString("en-US")} vendor groups on date basis {basisLabel(basis)}.{" "}
          {ranked.length > TOP ? (
            <Link className="font-semibold text-teal underline" href={viewHref(raw, !showAll)}>{showAll ? "Top 25" : "Show all"}</Link>
          ) : null}
          {" "}
          <HowToRead anchor="read-vendors" />
        </p>
      </header>

      <form className="grid gap-3 rounded-xl border border-teal/10 bg-page p-4 md:grid-cols-4" action="/vendors">
        {sorting.sort !== "amount" || sorting.direction !== "desc" ? (
          <div className="hidden">
            <input type="hidden" name="sort" value={sorting.sort} />
            <input type="hidden" name="direction" value={sorting.direction} />
          </div>
        ) : null}
        <label className="text-sm md:col-span-2">Vendor name
          <input name="q" defaultValue={search} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <label className="text-sm">Date basis
          <select name="basis" defaultValue={basis} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2">
            <option value="either">Either labeled date</option>
            <option value="check_date">Check date only</option>
            <option value="voucher_batch_date">Voucher batch date only</option>
          </select>
        </label>
        <label className="text-sm">District
          <select name="source" defaultValue={filters.source || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2">
            <option value="">All indexed</option>
            {districts.map((district) => <option key={district.source_id} value={district.source_id}>{district.entity_name}</option>)}
          </select>
        </label>
        <label className="text-sm">From
          <input type="date" name="start" defaultValue={filters.start || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <label className="text-sm">Through
          <input type="date" name="end" defaultValue={filters.end || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <div className="flex flex-wrap items-end gap-2 md:col-span-2">
          <button className="rounded-md bg-terracotta px-3 py-2 text-sm font-semibold text-white" type="submit">Apply</button>
          <a className="rounded-md border border-teal/20 px-3 py-2 text-sm font-semibold text-teal" href={`/api/export/vendors?${exportQuery.toString()}`}>Download CSV</a>
        </div>
      </form>

      {visible.length === 0 ? (
        <p className="text-sm text-teal/70">No screened vendor lines match this filter.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-teal/10 bg-page">
          <table className="w-full min-w-[860px] text-left text-base">
            <thead className="border-b border-teal/10 text-sm uppercase tracking-wide text-teal/60">
              <tr>
                <SortHeader label="Vendor" column="vendor" sorting={sorting} raw={raw} />
                <SortHeader label="Amount paid" column="amount" sorting={sorting} raw={raw} />
                <SortHeader label="Lines" column="lines" sorting={sorting} raw={raw} />
                <SortHeader label="Districts" column="districts" sorting={sorting} raw={raw} />
                <SortHeader label="First date" column="first" sorting={sorting} raw={raw} />
                <SortHeader label="Last date" column="last" sorting={sorting} raw={raw} />
              </tr>
            </thead>
            <tbody>
              {visible.map((vendor) => <VendorRow key={vendor.vendorKey} vendor={vendor} basis={basis} />)}
            </tbody>
          </table>
        </div>
      )}

      <nav className="flex flex-wrap items-center gap-3 text-base" aria-label="Vendor pages">
        {showAll ? (
          <>
            <span>All vendors. Page {Math.min(page, pages)} of {pages}.</span>
            {page > 1 ? <Link className="font-semibold text-teal underline" href={pageHref(raw, page - 1)}>Previous</Link> : null}
            {page < pages ? <Link className="font-semibold text-teal underline" href={pageHref(raw, page + 1)}>Next</Link> : null}
            <Link className="font-semibold text-teal underline" href={viewHref(raw, false)}>Top 25</Link>
          </>
        ) : (
          <span>
            Top {Math.min(TOP, ranked.length)} of {ranked.length.toLocaleString("en-US")}.
            {ranked.length > TOP ? <> <Link className="font-semibold text-teal underline" href={viewHref(raw, true)}>Show all</Link></> : null}
          </span>
        )}
      </nav>
    </div>
  );
}

function VendorRow({ vendor, basis }: { vendor: VendorRank; basis: string }) {
  const href = basis === "either" ? `/explore/vendors/${vendor.vendorKey}` : `/explore/vendors/${vendor.vendorKey}?basis=${basis}`;
  return (
    <tr className="border-b border-teal/5 align-top">
      <td className="px-3 py-3">
        <Link className="font-semibold text-teal underline" href={href}>{vendor.printedName}</Link>
        {vendor.otherPrintedNames.length > 0 ? (
          <p className="mt-1 text-xs text-teal/60">Grouped as {vendor.vendorKey}. Also printed: {vendor.otherPrintedNames.join("; ")}</p>
        ) : null}
        <details className="mt-2 text-xs">
          <summary className="cursor-pointer font-semibold text-teal">Per-district breakdown</summary>
          <ul className="mt-2 space-y-1">
            {vendor.districts.map((row) => (
              <li key={row.district}>
                {row.district}: {dollars(row.amountCents)} · {row.lineCount.toLocaleString("en-US")} lines
                {row.firstDate ? ` · ${row.firstDate}` : ""}
                {row.lastDate && row.lastDate !== row.firstDate ? ` through ${row.lastDate}` : ""}
              </li>
            ))}
          </ul>
        </details>
      </td>
      <td className="px-3 py-3 font-semibold">{dollars(vendor.amountCents)}</td>
      <td className="px-3 py-3">{vendor.lineCount.toLocaleString("en-US")}</td>
      <td className="px-3 py-3">{vendor.districtCount.toLocaleString("en-US")}</td>
      <td className="px-3 py-3">{vendor.firstDate || ""}</td>
      <td className="px-3 py-3">{vendor.lastDate || ""}</td>
    </tr>
  );
}

function SortHeader({
  label,
  column,
  sorting,
  raw,
}: {
  label: string;
  column: VendorSort;
  sorting: { sort: VendorSort; direction: SortDirection };
  raw: Record<string, string | undefined>;
}) {
  const active = sorting.sort === column;
  const next: SortDirection = active && sorting.direction === "desc" ? "asc" : "desc";
  return (
    <th scope="col" aria-sort={active ? (sorting.direction === "asc" ? "ascending" : "descending") : "none"} className="px-3 py-2">
      <Link className={active ? "font-semibold text-teal underline" : "underline decoration-teal/30"} href={sortHref(raw, column, next)}>
        {label}
        {active ? (sorting.direction === "asc" ? " ↑" : " ↓") : ""}
      </Link>
    </th>
  );
}

function sortHref(raw: Record<string, string | undefined>, sort: VendorSort, direction: SortDirection): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    if (!value || key === "sort" || key === "direction" || key === "page") continue;
    params.set(key, value);
  }
  if (!(sort === "amount" && direction === "desc")) {
    params.set("sort", sort);
    params.set("direction", direction);
  }
  const query = params.toString();
  return query ? `/vendors?${query}` : "/vendors";
}

function viewHref(raw: Record<string, string | undefined>, showAll: boolean): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    if (!value || key === "page" || key === "all") continue;
    params.set(key, value);
  }
  if (showAll) params.set("all", "1");
  const query = params.toString();
  return query ? `/vendors?${query}` : "/vendors";
}

function pageHref(raw: Record<string, string | undefined>, page: number): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(raw)) {
    if (!value || key === "page") continue;
    params.set(key, value);
  }
  if (page > 1) params.set("page", String(page));
  const query = params.toString();
  return query ? `/vendors?${query}` : "/vendors";
}
