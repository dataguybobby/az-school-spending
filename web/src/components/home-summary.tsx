import Link from "next/link";
import { dollars } from "@/lib/utils";
import type { ComparisonRecord } from "@/lib/enrollment";

type Vendor = { vendor_raw: string; amount_cents: number; line_count: number };
type District = { entity_name: string; amount_cents: number; line_count: number; documents: number };

export function HomeSummary({
  vendors,
  districts,
  comparisons,
}: {
  vendors: Vendor[];
  districts: District[];
  comparisons: ComparisonRecord[];
}) {
  const perStudent = latestPerStudent(comparisons);
  return (
    <section className="grid gap-4 md:grid-cols-3">
      <article className="rounded-xl border border-teal/10 bg-page p-4">
        <h2 className="font-semibold">Top vendors</h2>
        <ul className="mt-3 space-y-2 text-base">
          {vendors.slice(0, 3).map((vendor) => (
            <li key={vendor.vendor_raw} className="flex items-baseline justify-between gap-3">
              <span>{vendor.vendor_raw}</span>
              <span className="shrink-0 font-semibold">{dollars(vendor.amount_cents)}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3">
          <Link className="font-semibold text-teal underline" href="/vendors">Vendor leaderboard</Link>
        </p>
      </article>
      <article className="rounded-xl border border-teal/10 bg-page p-4">
        <h2 className="font-semibold">Spend by district</h2>
        <ul className="mt-3 space-y-2 text-base">
          {districts.map((district) => (
            <li key={district.entity_name} className="flex items-baseline justify-between gap-3">
              <span>{shortDistrict(district.entity_name)}</span>
              <span className="shrink-0 font-semibold">{dollars(district.amount_cents)}</span>
            </li>
          ))}
        </ul>
      </article>
      <article className="rounded-xl border border-teal/10 bg-page p-4">
        <h2 className="font-semibold">Per enrolled student</h2>
        <p className="mt-1 text-sm text-teal/70">Reported amount in this index per enrolled student</p>
        {perStudent.length === 0 ? (
          <p className="mt-3 text-base">No year-matched comparison in this filter.</p>
        ) : (
          <ul className="mt-3 space-y-2 text-base">
            {perStudent.map((row) => (
              <li key={row.sourceId} className="flex items-baseline justify-between gap-3">
                <span>{shortDistrict(row.district)} <span className="text-teal/60">{row.schoolYear}</span></span>
                <span className="shrink-0 font-semibold">{dollars(row.reportedCentsPerEnrolledStudent)}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-3">
          <Link className="font-semibold text-teal underline" href="/enrollment">October 1 enrollment (ADE headcount)</Link>
        </p>
      </article>
    </section>
  );
}

function latestPerStudent(rows: ComparisonRecord[]): ComparisonRecord[] {
  const latest = new Map<string, ComparisonRecord>();
  for (const row of rows) {
    if (row.reportedCentsPerEnrolledStudent == null || !row.schoolYear) continue;
    const current = latest.get(row.sourceId);
    if (!current || row.schoolYear > (current.schoolYear ?? "")) latest.set(row.sourceId, row);
  }
  return [...latest.values()];
}

function shortDistrict(name: string): string {
  return name
    .replace(/ Unified School District.*/, "")
    .replace(/ Unified District.*/, "")
    .replace(/ School District.*/, "");
}
