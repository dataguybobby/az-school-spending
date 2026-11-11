import { EnrollmentComparison } from "@/components/enrollment-comparison";
import { HowToRead } from "@/components/how-to-read";
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
    <article className="space-y-8 text-base leading-7">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-teal">ADE Accountability</p>
        <h1 className="mt-2 font-extrabold text-4xl">October 1 enrollment (ADE headcount)</h1>
        <p className="mt-3">
          Reported amount in this index per enrolled student. <HowToRead anchor="read-enrollment" />
        </p>
      </header>

      <EnrollmentComparison rows={comparisons} basisName={basisLabel("either")} />

      <section>
        <h2 className="font-extrabold text-2xl">LEA of enrollment, 2017-2018 onward</h2>
        <p className="mt-2">LEA by Grade tab. A cell is the printed Total for that entity id.</p>
        <SeriesTable years={comparableYears} rows={comparable} />
      </section>

      <section>
        <h2 className="font-extrabold text-2xl">Earlier files, different basis</h2>
        <p className="mt-2">2010-2011 through 2016-2017 use a different basis. <HowToRead anchor="read-enrollment" /></p>
        <SeriesTable years={residenceYears} rows={residence} />
        <h3 className="mt-6 font-semibold">2010-2011 residence pairs, as printed</h3>
        <div className="mt-3 overflow-x-auto rounded-xl border border-teal/10 bg-page">
          <table className="w-full min-w-[720px] text-left text-base">
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
        <p className="mt-2">A blank or asterisk stays null.</p>
        <div className="mt-3 overflow-x-auto rounded-xl border border-teal/10 bg-page">
          <table className="w-full min-w-[640px] text-left text-base">
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
        <p className="mt-1">These names are not added to the five districts.</p>
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
      <table className="w-full min-w-[760px] text-left text-base">
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
