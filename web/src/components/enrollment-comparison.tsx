import Link from "next/link";
import { dollars } from "@/lib/utils";
import { formatIsoDate, type ComparisonStatus } from "@/lib/enrollment-match";
import type { ComparisonRecord } from "@/lib/enrollment";

export function EnrollmentComparison({
  rows,
  basisName,
  filterNote,
}: {
  rows: ComparisonRecord[];
  basisName: string;
  filterNote?: string | null;
}) {
  return (
    <section className="rounded-xl border border-teal/10 bg-page p-4">
      <h2 className="font-semibold">October 1 enrollment beside this index</h2>
      <p className="mt-1 max-w-3xl text-sm leading-6 text-teal/75">
        Reported amount in this index per enrolled student. October 1 enrollment is a headcount, not ADM. It is not cost per pupil and not total district spending.
      </p>
      <p className="mt-2 max-w-3xl text-xs leading-5 text-teal/65">
        Date basis: {basisName}. School year YYYY-(YYYY+1) uses spending dated July 1, YYYY through June 30, YYYY+1. School year 2025-2026 uses 2025-07-01 through 2026-06-30.
        {" "}
        <Link className="font-semibold text-teal underline" href="/enrollment">Full October 1 series</Link>
      </p>
      {filterNote ? <p className="mt-2 max-w-3xl text-xs leading-5 text-teal/65">{filterNote}</p> : null}
      {rows.length === 0 ? (
        <p className="mt-4 text-sm text-teal/70">No screened lines in this filter are paired with an October 1 count.</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {rows.map((row) => (
            <li key={`${row.sourceId}-${row.schoolYear ?? "undated"}-${row.status}`} className="rounded-lg border border-teal/10 px-3 py-3">
              <ComparisonBody row={row} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function ComparisonBody({ row }: { row: ComparisonRecord }) {
  return (
    <article>
      <h3 className="font-semibold">{row.district}</h3>
      <p className="text-xs font-semibold uppercase tracking-wide text-teal/50">{comparisonStatusLabel(row.status)}</p>
      <p className="mt-1 text-sm text-teal/80">{statusText(row)}</p>
      {row.schoolYear ? (
        <p className="mt-2 text-xs leading-5 text-teal/60">
          School year {row.schoolYear}
          {row.october1Date ? ` · ${formatIsoDate(row.october1Date)}` : ""}
          {row.spendingWindowStart && row.spendingWindowEnd
            ? ` · spending window ${formatIsoDate(row.spendingWindowStart)} through ${formatIsoDate(row.spendingWindowEnd)}`
            : ""}
        </p>
      ) : null}
      <dl className="mt-2 grid gap-1 text-sm md:grid-cols-2">
        <div>
          <dt className="text-xs uppercase tracking-wide text-teal/50">October 1 enrollment</dt>
          <dd>{enrollmentFigure(row)}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-teal/50">Screened amount in this index</dt>
          <dd>
            {row.screenedAmountCents == null
              ? "Not in this index"
              : `${dollars(row.screenedAmountCents)} · ${row.screenedLineCount.toLocaleString("en-US")} lines`}
          </dd>
        </div>
        {row.reportedCentsPerEnrolledStudent != null ? (
          <div className="md:col-span-2">
            <dt className="text-xs uppercase tracking-wide text-teal/50">{row.label}</dt>
            <dd className="font-semibold">{dollars(row.reportedCentsPerEnrolledStudent)}</dd>
          </div>
        ) : null}
      </dl>
      {row.spendingFirstDate && row.spendingLastDate ? (
        <p className="mt-2 text-xs leading-5 text-teal/60">
          Indexed dates in this school year: {formatIsoDate(row.spendingFirstDate)} through {formatIsoDate(row.spendingLastDate)}. These dates are the screened lines in this index, not a full school year.
        </p>
      ) : null}
      {row.officialSourceUrl ? (
        <p className="mt-2 text-xs">
          <a className="font-semibold text-teal underline" href={row.officialSourceUrl}>ADE October 1 workbook</a>
        </p>
      ) : null}
    </article>
  );
}

function enrollmentFigure(row: ComparisonRecord): string {
  if (row.october1Enrollment != null) return row.october1Enrollment.toLocaleString("en-US");
  switch (row.status) {
    case "reported_per_enrolled_student":
      return "Not published";
    case "no_enrollment_workbook":
      return "No workbook for this school year";
    case "suppressed_enrollment":
      return "Suppressed";
    case "no_dated_spending":
    case "not_in_spending_index":
      return "Not paired";
    case "multiple_official_rows":
      return "Not summed";
    case "not_comparable_basis":
      return "Not used as a denominator";
    case "no_lea_link":
      return "Not linked";
    case "lea_not_in_workbook":
      return "Not in that workbook";
    case "no_positive_enrollment":
      return "Not used as a denominator";
    default: {
      const unreachable: never = row.status;
      return unreachable;
    }
  }
}

function statusText(row: ComparisonRecord): string {
  switch (row.status) {
    case "reported_per_enrolled_student":
      return "Official October 1 headcount for this school year, beside the screened lines whose dates fall in that same July-June window.";
    case "no_enrollment_workbook":
      return row.enrollmentNullReason ?? "No October 1 workbook is loaded for this school year.";
    case "suppressed_enrollment":
      return row.enrollmentNullReason ?? "ADE suppressed this October 1 total. It stays null.";
    case "no_dated_spending":
      return row.enrollmentNullReason ?? "No date on this basis, so no school year is assigned.";
    case "not_in_spending_index":
      return row.enrollmentNullReason ?? "This district is not in the spending index.";
    case "multiple_official_rows":
      return row.enrollmentNullReason ?? "More than one official total is printed. Those rows are not summed.";
    case "not_comparable_basis":
      return row.enrollmentNullReason ?? "This year is not on the 2017-2018 and later basis.";
    case "no_lea_link":
      return row.enrollmentNullReason ?? "No ADE entity id is linked for this source.";
    case "lea_not_in_workbook":
      return row.enrollmentNullReason ?? "This entity id is not in that workbook.";
    case "no_positive_enrollment":
      return row.enrollmentNullReason ?? "The printed headcount is not used as a denominator.";
    default: {
      const unreachable: never = row.status;
      return unreachable;
    }
  }
}

export function comparisonStatusLabel(status: ComparisonStatus): string {
  switch (status) {
    case "reported_per_enrolled_student":
      return "Year-matched";
    case "no_enrollment_workbook":
      return "No workbook for that school year";
    case "suppressed_enrollment":
      return "Suppressed";
    case "no_dated_spending":
      return "No date on this basis";
    case "not_in_spending_index":
      return "Not in the spending index";
    case "multiple_official_rows":
      return "Multiple official rows";
    case "not_comparable_basis":
      return "Different basis";
    case "no_lea_link":
      return "No entity link";
    case "lea_not_in_workbook":
      return "Entity not in workbook";
    case "no_positive_enrollment":
      return "No positive headcount";
    default: {
      const unreachable: never = status;
      return unreachable;
    }
  }
}
