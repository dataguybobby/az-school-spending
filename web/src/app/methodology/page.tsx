import Link from "next/link";
import { openDb } from "@/lib/db";
import { dollars } from "@/lib/utils";

export const dynamic = "force-dynamic";

type DocumentRow = {
  document_id: string;
  entity_name: string | null;
  period_label_native: string | null;
  url: string | null;
  sha256: string | null;
  parser_id: string | null;
  parser_version: string | null;
  reconciliation_status: string | null;
  parsed_outcome: string | null;
  public_line_count: number | null;
  withheld_count: number | null;
  printed_total_cents: number | null;
  printed_total_null_reason: string | null;
  indexed: number;
  coverage_note: string | null;
  fiscal_note: string | null;
};

export default async function MethodologyPage() {
  const db = openDb();
  const documents = db.prepare(
    `SELECT d.document_id, s.entity_name, d.period_label_native, d.url, d.sha256, d.parser_id, d.parser_version,
            d.reconciliation_status, d.parsed_outcome, d.public_line_count, d.withheld_count,
            d.printed_total_cents, d.printed_total_null_reason, d.indexed, d.coverage_note
     FROM documents d
     LEFT JOIN sources s ON s.source_id = d.source_id
     ORDER BY d.indexed DESC, s.entity_name, d.document_id`,
  ).all() as DocumentRow[];
  const indexed = documents.filter((row) => row.indexed === 1);
  const held = documents.filter((row) => row.indexed !== 1);

  return (
    <article className="space-y-8 text-sm leading-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-teal">How to read this ledger</p>
        <h1 className="mt-2 font-extrabold text-4xl">Methodology</h1>
        <p className="mt-3 max-w-3xl text-base">
          Phoenix Dataworks publishes AZ School Spending. It is not an official government site, and it is not a district or state report.
        </p>
      </header>

      <section className="rounded-xl border border-teal/10 bg-page p-5">
        <h2 className="font-extrabold text-2xl">What a line means</h2>
        <p className="mt-2 max-w-3xl">
          A line is a reported accounts-payable amount or a vouchered amount taken from an official board document.
          The amount is what that document printed for the line. It is not proof that a payment settled, cleared a bank, or was the final price.
        </p>
      </section>

      <section className="rounded-xl border border-teal/10 bg-page p-5">
        <h2 className="font-extrabold text-2xl">What is in the public index</h2>
        <p className="mt-2 max-w-3xl">
          Only screened public lines. A row stays out when the payee looks personal or unknown, or when the text contains a student name, a street address, a check number, or IEP, ESY, medicaid, diagnosis, or prescription language.
          Those rows are quarantined. Hiding a column is not enough. Raw PDFs are not republished. Each indexed document links to the official board page instead.
        </p>
      </section>

      <section className="rounded-xl border border-teal/10 bg-page p-5">
        <h2 className="font-extrabold text-2xl">Coverage</h2>
        <p className="mt-2 max-w-3xl">
          The spending total uses only observed documents whose parsed detail lines reconciled to the printed total on that same document.
          This is not a census of Arizona schools, not a census of Phoenix schools, and not a district’s full year.
          Dates follow the basis you select: check date, or voucher batch date. A voucher batch date is not a check date.
          Lines with no date on the selected basis stay out of a dated filter. They are not treated as zero.
          When two Scottsdale report headers share a calendar date but the parsed check dates do not overlap, both documents stay in the default sum.
          A shared check date would be kept out of the default total, the charts, and the CSV. That overlap note is on the spending page when one exists.
        </p>
      </section>

      <section className="rounded-xl border border-teal/10 bg-page p-5">
        <h2 className="font-extrabold text-2xl">Categories</h2>
        <p className="mt-2 max-w-3xl">
          Categories use the ruleset <span className="font-semibold">phoenix-k12-neutral-2026.11.06</span>.
          An account title printed on the row is stronger evidence than item text. Unclassified is the default.
          A match on item text is weak, and it does not prove why the district bought the item.
          Amazon is a vendor, not a category. These labels are not USFR codes.
        </p>
      </section>

      <section className="rounded-xl border border-teal/10 bg-page p-5">
        <h2 className="font-extrabold text-2xl">Item and vendor groups</h2>
        <p className="mt-2 max-w-3xl">
          Vendor keys collapse spacing and punctuation so obvious reprints of the same payee can be summed. The display name is the raw payee string that appears most often for that key.
          Item groups are a separate layer. A reviewed phrase in the public description, such as “stress balls,” can group those lines.
          The group stores the canonical label, the matched evidence span, the method, and a confidence. It is resolved from description text, not from an official budget code.
          Broad words such as “ball” are not groups. A not-to-exceed or ceiling figure printed in a description is not the spend total. The line amount is.
          Low-confidence and phrase groups stay labeled as grouped from description text.
          <Link className="ml-1 font-semibold text-teal underline" href="/explore">Open the groups</Link>.
        </p>
      </section>

      <section>
        <h2 className="font-extrabold text-2xl">Source documents</h2>
        <p className="mt-2 max-w-3xl">
          Indexed documents are in the spending total. Fetched documents that did not reconcile are listed after them. An unindexed file is not zero spending.
        </p>
        <DocumentList title="Indexed" rows={indexed} />
        <DocumentList title="Fetched, not indexed" rows={held} />
      </section>
    </article>
  );
}

function DocumentList({ title, rows }: { title: string; rows: DocumentRow[] }) {
  return (
    <div className="mt-4 space-y-3">
      <h3 className="font-semibold">{title}</h3>
      {rows.length === 0 ? <p>None in this snapshot.</p> : rows.map((row) => (
        <article key={row.document_id} className="rounded-xl border border-teal/10 bg-page p-4">
          <h4 className="font-semibold">{row.entity_name || row.document_id}</h4>
          <p className="text-teal/70">{row.period_label_native || "No native period label on this file"} · {row.document_id}</p>
          <p className="mt-2">
            {row.url ? (
              <a className="font-semibold text-teal underline" href={row.url}>Official source document</a>
            ) : "No official URL stored"}
          </p>
          <dl className="mt-2 grid gap-1 text-xs text-teal/70 md:grid-cols-2">
            <div>SHA-256 <span className="font-mono text-teal">{row.sha256}</span></div>
            <div>Parser {row.parser_id} {row.parser_version}</div>
            <div>Reconciliation {row.reconciliation_status} · {row.parsed_outcome}</div>
            <div>
              Printed total {row.printed_total_cents == null ? (row.printed_total_null_reason || "not extracted") : dollars(row.printed_total_cents)}
            </div>
            <div>Public lines {row.public_line_count ?? 0}</div>
            <div>Withheld {row.withheld_count ?? 0}</div>
          </dl>
          {row.coverage_note ? <p className="mt-2 text-teal/70">{row.coverage_note}</p> : null}
        </article>
      ))}
    </div>
  );
}
