import Link from "next/link";
import dictionary from "@/data/dictionary.json";
import { dollars } from "@/lib/utils";

export const dynamic = "force-static";

type DocumentRow = (typeof dictionary.documents)[number];
type SourceRow = (typeof dictionary.sources)[number];

export default function DictionaryPage() {
  const indexed = dictionary.documents.filter((row) => row.in_public_index);
  const held = dictionary.documents.filter((row) => !row.in_public_index);
  const searched = dictionary.sources.filter((row) => row.dictionary_status === "searched_not_ingested");

  return (
    <article className="space-y-8 text-sm leading-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal">Living map of this ledger</p>
        <h1 className="mt-2 font-extrabold text-4xl">Data dictionary</h1>
        <p className="mt-3 max-w-3xl">
          Phoenix Dataworks publishes AZ School Spending. This page is generated from the public snapshot and the registry.
          It is not an official government site. {dictionary.geography}
        </p>
        <p className="mt-2 max-w-3xl text-teal/80">
          {dictionary.snapshot.wording} The current screened total is {dollars(dictionary.snapshot.screened_amount_cents)} across {dictionary.snapshot.screened_line_count.toLocaleString()} lines.
          {" "}
          <Link className="font-semibold text-teal underline" href="/methodology">Methodology</Link>
        </p>
      </header>

      <section className="rounded-xl border border-teal/10 bg-page p-5">
        <h2 className="font-extrabold text-2xl">Scope</h2>
        <p className="mt-2">{dictionary.scope.window_enforcement}</p>
        <p className="mt-2 text-teal/75">Amount tag on every public line: {dictionary.amount_semantics}.</p>
      </section>

      <section>
        <h2 className="font-extrabold text-2xl">Sources in the public index</h2>
        <div className="mt-3 space-y-3">
          {indexed.map((row) => <DocumentCard key={row.document_id} row={row} />)}
        </div>
      </section>

      <section>
        <h2 className="font-extrabold text-2xl">Fetched, not indexed</h2>
        <p className="mt-1 text-teal/75">An unindexed file is not zero spending. Paradise Valley stays here until a printed total can be reconciled.</p>
        <div className="mt-3 space-y-3">
          {held.map((row) => <DocumentCard key={row.document_id} row={row} />)}
        </div>
      </section>

      <section>
        <h2 className="font-extrabold text-2xl">Searched, no vendor ledger ingested</h2>
        <ul className="mt-3 space-y-3">
          {searched.map((row) => <SourceCard key={row.source_id} row={row} />)}
        </ul>
      </section>

      <section className="rounded-xl border border-teal/10 bg-page p-5">
        <h2 className="font-extrabold text-2xl">Transformations</h2>
        <ol className="mt-3 space-y-3">
          {dictionary.transformations.map((row) => (
            <li key={row.id}>
              <p className="font-semibold">{row.id}</p>
              <p>{row.step}</p>
              <p className="text-xs text-teal/60">{row.code}</p>
            </li>
          ))}
        </ol>
      </section>

      <section>
        <h2 className="font-extrabold text-2xl">Aggregations</h2>
        <p className="mt-1 text-teal/75">DAC or department text is as printed, not a verified school location. Amazon is a vendor, not a category. The site does not label waste or fraud.</p>
        <div className="mt-3 space-y-3">
          {dictionary.aggregations.map((row) => (
            <article key={row.id} className="rounded-xl border border-teal/10 bg-page p-4">
              <h3 className="font-semibold">{row.id}</h3>
              <p>{row.public_wording}</p>
              <dl className="mt-2 grid gap-1 text-xs text-teal/70">
                <div>Grain: {row.grain}</div>
                <div>Filter: {row.filter}</div>
                <div>Date basis: {row.date_basis}</div>
                <div>Code: {row.surface}</div>
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-teal/10 bg-page p-5">
        <h2 className="font-extrabold text-2xl">Enrollment, not yet ingested</h2>
        <p className="mt-2">{dictionary.enrollment.note}</p>
        <p className="mt-2">
          <a className="font-semibold text-teal underline" href={dictionary.enrollment.official_url}>Official ADE page</a>
          {" · "}status {dictionary.enrollment.status}
          {" · "}HTTP {dictionary.enrollment.http_status}
          {" · "}headcount {dictionary.enrollment.headcount == null ? "null" : dictionary.enrollment.headcount}
          {" · "}{dictionary.enrollment.null_reason}
        </p>
      </section>

      <section>
        <h2 className="font-extrabold text-2xl">Registry rows</h2>
        <p className="mt-1 text-teal/75">{dictionary.sources.length} registry rows are in this snapshot. A row without a hash was not fetched as a document file.</p>
        <div className="mt-3 overflow-x-auto rounded-xl border border-teal/10 bg-page">
          <table className="w-full min-w-[760px] text-left text-xs">
            <thead className="border-b border-teal/10 uppercase tracking-wide text-teal/60">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Class</th>
                <th className="px-3 py-2">URL</th>
              </tr>
            </thead>
            <tbody>
              {dictionary.sources.map((row) => (
                <tr key={row.source_id} className="border-b border-teal/5 align-top">
                  <td className="px-3 py-2">{row.district_or_dataset}<div className="text-teal/50">{row.source_id}</div></td>
                  <td className="px-3 py-2">{row.dictionary_status}</td>
                  <td className="px-3 py-2">{row.document_class}</td>
                  <td className="px-3 py-2">
                    {row.official_url ? <a className="font-semibold text-teal underline" href={row.official_url}>Official page</a> : row.official_url_null_reason}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </article>
  );
}

function DocumentCard({ row }: { row: DocumentRow }) {
  return (
    <article className="rounded-xl border border-teal/10 bg-page p-4">
      <h3 className="font-semibold">{row.district || row.document_id}</h3>
      <p className="text-teal/70">{row.document_class} · {row.in_public_index ? "in the public index" : "not in the public index"}</p>
      <p className="mt-2">{row.period_as_printed_or_stored || row.period_null_reason}</p>
      <p className="mt-2">
        {row.official_url ? <a className="font-semibold text-teal underline" href={row.official_url}>Official source document</a> : "No official URL stored"}
      </p>
      <dl className="mt-2 grid gap-1 text-xs text-teal/70 md:grid-cols-2">
        <div className="md:col-span-2 break-all">SHA-256 {row.sha256}</div>
        <div>{row.reconciliation_status} · {row.parsed_outcome}</div>
        <div>Public lines {row.public_line_count ?? 0} · withheld {row.withheld_count ?? 0}</div>
        <div>Printed total {row.printed_total_cents == null ? (row.printed_total_null_reason || "null") : dollars(row.printed_total_cents)}</div>
      </dl>
      {row.coverage_note ? <p className="mt-2 text-teal/75">{row.coverage_note}</p> : null}
    </article>
  );
}

function SourceCard({ row }: { row: SourceRow }) {
  return (
    <li className="rounded-xl border border-teal/10 bg-page p-4">
      <p className="font-semibold">{row.district_or_dataset}</p>
      <p className="text-teal/70">{row.document_class} · {row.dictionary_status} · {row.access_status}</p>
      <p className="mt-2">{row.sha256_null_reason}</p>
      {row.official_url ? <p className="mt-2"><a className="font-semibold text-teal underline" href={row.official_url}>Official page</a></p> : <p>{row.official_url_null_reason}</p>}
    </li>
  );
}
