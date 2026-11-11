import Link from "next/link";
import { EnrollmentComparison } from "@/components/enrollment-comparison";
import { basisLabel } from "@/lib/basis";
import { openDb } from "@/lib/db";
import { loadComparisons, loadFocusEnrollment, loadUnmatchedCharters, loadWorkbooks } from "@/lib/enrollment";
import { formatHeadcount, formatIsoDate } from "@/lib/enrollment-match";

export const dynamic = "force-dynamic";

const DISTRICTS = [
  "Chandler Unified",
  "Higley Unified",
  "Queen Creek Unified",
  "Scottsdale Unified",
  "Paradise Valley Unified",
] as const;

export default function EnrollmentPage() {
  const db = openDb();
  const comparisons = loadComparisons(db, {});
  const focus = loadFocusEnrollment(db);
  const workbooks = loadWorkbooks(db);
  const unmatched = loadUnmatchedCharters(db);
  const comparable = focus.filter((row) => row.sameBasis && row.leaIdMatches);
  const residenceYears = [...new Set(focus.filter((row) => !row.sameBasis && row.schoolYear !== "2010-2011" && row.leaIdMatches).map((row) => row.schoolYear))];
  const residence = focus.filter((row) => !row.sameBasis && row.schoolYear !== "2010-2011" && row.leaIdMatches);
  const pairs2010 = focus.filter((row) => row.schoolYear === "2010-2011");
  const comparableYears = [...new Set(comparable.map((row) => row.schoolYear))];

  return (
    <article className="space-y-8 text-sm leading-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal">ADE Accountability</p>
        <h1 className="mt-2 font-extrabold text-4xl">October 1 enrollment</h1>
        <p className="mt-3 max-w-3xl">
          This is the official Arizona Department of Education headcount of students enrolled on October 1. It is not ADM.
          The spending figure beside it is a reported amount in this index per enrolled student. The index is an AP and voucher extract.
        </p>
        <p className="mt-2 max-w-3xl text-teal/75">
          School year 2025-2026 pairs with spending dated July 1, 2025 through June 30, 2026. The project coverage window still starts July 1, 2024.
          {" "}
          <Link className="font-semibold text-teal underline" href="/dictionary">Data dictionary</Link>
          {" · "}
          <Link className="font-semibold text-teal underline" href="/methodology">Methodology</Link>
        </p>
      </header>

      <EnrollmentComparison rows={comparisons} basisName={basisLabel("either")} />

      <section>
        <h2 className="font-extrabold text-2xl">LEA of enrollment, 2017-2018 onward</h2>
        <p className="mt-2 max-w-3xl text-teal/75">
          These counts come from the LEA by Grade tab. They are the series that can be read together. A cell is the printed Total for that entity id.
        </p>
        <SeriesTable years={comparableYears} rows={comparable} />
      </section>

      <section>
        <h2 className="font-extrabold text-2xl">Earlier files, different basis</h2>
        <p className="mt-2 max-w-3xl">
          District totals for 2010-2011 through 2016-2017 are not on the same basis as 2017-2018 onward and are not a continuous series.
        </p>
        <p className="mt-2 max-w-3xl text-teal/75">
          2011-2012 through 2016-2017 are district-of-residence subtotals ADE printed in the school tab. They can include resident students attending schools outside the LEA.
        </p>
        <SeriesTable years={residenceYears} rows={residence} />
        <h3 className="mt-6 font-semibold">2010-2011 has no single all-students LEA total</h3>
        <p className="mt-1 max-w-3xl text-teal/75">
          ADE printed one subtotal for each attending LEA and district-of-residence pair. Rows are not added together.
        </p>
        <div className="mt-3 overflow-x-auto rounded-xl border border-teal/10 bg-page">
          <table className="w-full min-w-[720px] text-left text-xs">
            <caption className="px-3 py-2 text-left text-sm text-teal/70">2010-2011 residence pairs, as printed</caption>
            <thead className="border-b border-teal/10 uppercase tracking-wide text-teal/60">
              <tr>
                <th className="px-3 py-2">District</th>
                <th className="px-3 py-2">Residence id</th>
                <th className="px-3 py-2">October 1 count</th>
                <th className="px-3 py-2">What ADE printed</th>
              </tr>
            </thead>
            <tbody>
              {pairs2010.map((row) => (
                <tr key={`${row.focusDistrict}-${row.leaEntityId}`} className="border-b border-teal/5 align-top">
                  <td className="px-3 py-2">{row.focusDistrict}<div className="text-teal/50">{row.leaName}</div></td>
                  <td className="px-3 py-2">{row.leaEntityId}{row.leaIdMatches ? " · matches this district" : ""}</td>
                  <td className="px-3 py-2">{formatHeadcount(row.october1Enrollment)}</td>
                  <td className="px-3 py-2">{row.focusNote}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="font-extrabold text-2xl">Statewide total, as printed</h2>
        <p className="mt-2 max-w-3xl text-teal/75">A blank or asterisk statewide total stays null. It is not a denominator for this index.</p>
        <div className="mt-3 overflow-x-auto rounded-xl border border-teal/10 bg-page">
          <table className="w-full min-w-[640px] text-left text-xs">
            <thead className="border-b border-teal/10 uppercase tracking-wide text-teal/60">
              <tr>
                <th className="px-3 py-2">School year</th>
                <th className="px-3 py-2">October 1</th>
                <th className="px-3 py-2">Statewide total</th>
                <th className="px-3 py-2">Workbook</th>
              </tr>
            </thead>
            <tbody>
              {workbooks.map((row) => (
                <tr key={row.schoolYear} className="border-b border-teal/5 align-top">
                  <td className="px-3 py-2">{row.schoolYear}</td>
                  <td className="px-3 py-2">{formatIsoDate(`${row.schoolYear.slice(0, 4)}-10-01`)}</td>
                  <td className="px-3 py-2">
                    {row.statewideTotal == null ? (row.statewideNullReason ?? "Not published") : row.statewideTotal.toLocaleString("en-US")}
                  </td>
                  <td className="px-3 py-2">
                    <a className="font-semibold text-teal underline" href={row.officialSourceUrl}>Official file</a>
                    <div className="mt-1 break-all font-mono text-[10px] text-teal/50">{row.sha256}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-xl border border-teal/10 bg-page p-4">
        <h2 className="font-semibold">Charter names that are not these districts</h2>
        <p className="mt-1 text-teal/75">These LEAs contain a focus city in the name. They are not added to Chandler, Higley, Queen Creek, Scottsdale, or Paradise Valley.</p>
        <ul className="mt-3 columns-1 gap-x-6 text-xs md:columns-2">
          {unmatched.map((name) => <li key={name} className="mb-1">{name}</li>)}
        </ul>
      </section>
    </article>
  );
}

function SeriesTable({
  years,
  rows,
}: {
  years: string[];
  rows: Array<{ focusDistrict: string; schoolYear: string; october1Enrollment: number | null; suppressionOrNullReason: string | null }>;
}) {
  return (
    <div className="mt-3 overflow-x-auto rounded-xl border border-teal/10 bg-page">
      <table className="w-full min-w-[760px] text-left text-xs">
        <thead className="border-b border-teal/10 uppercase tracking-wide text-teal/60">
          <tr>
            <th className="px-3 py-2">School year</th>
            {DISTRICTS.map((district) => <th key={district} className="px-3 py-2">{district}</th>)}
          </tr>
        </thead>
        <tbody>
          {years.map((year) => (
            <tr key={year} className="border-b border-teal/5">
              <th className="px-3 py-2 font-semibold" scope="row">{year}</th>
              {DISTRICTS.map((district) => {
                const match = rows.find((row) => row.schoolYear === year && row.focusDistrict === district);
                return (
                  <td key={district} className="px-3 py-2" title={match?.suppressionOrNullReason ?? undefined}>
                    {match ? formatHeadcount(match.october1Enrollment) : "Not published"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
