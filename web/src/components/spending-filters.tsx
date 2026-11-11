import { ButtonLink } from "@/components/ui/button";
import type { Filters, SortDirection, SortKey } from "@/lib/db";

const ADVANCED = ["category", "confidence", "dac", "account"] as const;
const IGNORED = new Set(["page", "sort", "direction"]);

export function filtersAreOpen(raw: Record<string, string | undefined>): boolean {
  return Object.entries(raw).some(([key, value]) => Boolean(value) && !IGNORED.has(key));
}

export function SpendingFilters({
  raw,
  filters,
  basis,
  sorting,
  entities,
}: {
  raw: Record<string, string | undefined>;
  filters: Filters;
  basis: string;
  sorting: { sort: SortKey; direction: SortDirection };
  entities: Array<{ entity_name: string; source_id: string }>;
}) {
  const advancedOpen = ADVANCED.some((key) => Boolean(raw[key]));
  return (
    <details className="rounded-xl border border-teal/10 bg-page" open={filtersAreOpen(raw)}>
      <summary className="cursor-pointer px-4 py-3 text-base font-semibold">Filter / search</summary>
      <form className="grid gap-3 border-t border-teal/10 p-4 md:grid-cols-4" action="/">
        {sorting.sort !== "date" || sorting.direction !== "desc" ? (
          <div className="hidden">
            <input type="hidden" name="sort" value={sorting.sort} />
            <input type="hidden" name="direction" value={sorting.direction} />
          </div>
        ) : null}
        <label className="text-base md:col-span-2">Description or vendor
          <input name="q" defaultValue={filters.q || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <label className="text-base">Date basis
          <select name="basis" defaultValue={basis} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2">
            <option value="either">Either labeled date</option>
            <option value="check_date">Check date only</option>
            <option value="voucher_batch_date">Voucher batch date only</option>
          </select>
        </label>
        <label className="text-base">District
          <select name="source" defaultValue={filters.source || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2">
            <option value="">All indexed</option>
            {entities.map((entity) => <option key={entity.source_id} value={entity.source_id}>{entity.entity_name}</option>)}
          </select>
        </label>
        <label className="text-base">From
          <input type="date" name="start" defaultValue={filters.start || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <label className="text-base">Through
          <input type="date" name="end" defaultValue={filters.end || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <label className="text-base md:col-span-2">Vendor contains
          <input name="vendor" defaultValue={filters.vendor || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
        </label>
        <details className="rounded-lg border border-teal/10 p-3 md:col-span-4" open={advancedOpen}>
          <summary className="cursor-pointer font-semibold">Advanced</summary>
          <div className="mt-3 grid gap-3 md:grid-cols-4">
            <label className="text-base">Inferred category
              <select name="category" defaultValue={filters.category || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2">
                <option value="">Any</option>
                {["unclassified","utilities","communications","insurance","instructional_materials","technology","facilities","transport","food","professional_services","student_support","staff_activities"].map((item) => (
                  <option key={item} value={item}>{item.replaceAll("_", " ")}</option>
                ))}
              </select>
            </label>
            <label className="text-base">Category match strength
              <input name="confidence" defaultValue={filters.confidence || ""} placeholder="0 to 1" className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
            </label>
            <label className="text-base">Department text, as printed
              <input name="dac" defaultValue={filters.dac || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
            </label>
            <label className="text-base">Account code
              <input name="account" defaultValue={filters.account || ""} className="mt-1 w-full rounded-md border border-teal/15 px-3 py-2" />
            </label>
          </div>
        </details>
        <div className="flex flex-wrap items-end gap-2 md:col-span-4">
          <button className="rounded-md bg-terracotta px-3 py-2 text-base font-semibold text-white" type="submit">Apply</button>
          <ButtonLink href="/?basis=check_date&start=2025-07-01" variant="ghost">Check dates from July 1, 2025</ButtonLink>
        </div>
      </form>
    </details>
  );
}
