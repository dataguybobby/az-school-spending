import Link from "next/link";
import { PageToc } from "@/components/page-toc";
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
    <article className="space-y-8 text-base leading-7">
      <header>
        <p className="text-sm font-semibold uppercase tracking-[0.14em] text-teal">How this ledger is built</p>
        <h1 className="mt-2 font-extrabold text-4xl">Methodology</h1>
        <p className="mt-3 text-lg">
          Phoenix Dataworks publishes AZ School Spending. The <Link className="font-semibold text-teal underline" href="/dictionary">data dictionary</Link> lists each source, transformation, and aggregation in this snapshot.
          {" "}
          <Link className="font-semibold text-teal underline" href="/about">About this site</Link>.
        </p>
      </header>
      <PageToc items={[
        { href: "#caveats", label: "Caveats" },
        { href: "#read-totals", label: "Totals" },
        { href: "#read-dates", label: "Dates" },
        { href: "#read-gaps", label: "Gaps" },
        { href: "#read-privacy", label: "Privacy" },
        { href: "#read-categories", label: "Categories" },
        { href: "#read-vendors", label: "Vendors" },
        { href: "#read-enrollment", label: "Enrollment" },
        { href: "#read-coverage", label: "Coverage" },
        { href: "#read-groups", label: "Groups" },
        { href: "#source-documents", label: "Documents" },
      ]} />

      <section id="caveats" className="space-y-6">
        <h2 className="font-extrabold text-3xl">Caveats & how to read this data</h2>

        <section id="read-totals" className="rounded-xl border border-teal/10 bg-page p-5">
          <h3 className="font-extrabold text-2xl">Totals</h3>
          <p className="mt-2">
            This figure is the sum of screened public lines on that date basis. It is not unique spend, not the printed report total, not proof a payment settled, and not a census of districts or of Arizona schools.
          </p>
          <p className="mt-2">
            A line is a reported accounts-payable amount or a vouchered amount from an official board document. The amount is what that document printed for the line. It is not proof the payment settled, cleared a bank, or was the final price.
          </p>
        </section>

        <section id="read-dates" className="rounded-xl border border-teal/10 bg-page p-5">
          <h3 className="font-extrabold text-2xl">Dates</h3>
          <p className="mt-2">
            Dates follow the basis you select: check date, voucher batch date, or either labeled date. A voucher batch date is not a check date. Lines with no date on the selected basis stay out of a dated filter. They are not treated as zero.
          </p>
        </section>

        <section id="read-gaps" className="rounded-xl border border-teal/10 bg-page p-5">
          <h3 className="font-extrabold text-2xl">Gaps</h3>
          <p className="mt-2">
            A gap on a chart, or a blank month in a table, means no indexed document for that district in that month. It is not a month of zero spending. The line is not drawn through the gap, and the month is not filled with a number.
          </p>
          <p className="mt-2">
            A small labeled point is a real screened amount. Queen Creek May 2026 is one of those months: the indexed voucher document includes lines dated in May, and the amount is much smaller than the neighboring months.
          </p>
        </section>

        <section id="read-privacy" className="rounded-xl border border-teal/10 bg-page p-5">
          <h3 className="font-extrabold text-2xl">Privacy</h3>
          <p className="mt-2">
            Only screened public lines are in the index. A row stays out when the payee looks personal or unknown, or when the text contains a student name, a street address, a check number, or IEP, ESY, medicaid, diagnosis, or prescription language. Those rows are withheld. Hiding a column is not the control. Raw PDFs are not republished, and check numbers are not shown.
          </p>
        </section>

        <section id="read-categories" className="rounded-xl border border-teal/10 bg-page p-5">
          <h3 className="font-extrabold text-2xl">Categories</h3>
          <p className="mt-2">
            Each pie is one district, grouped by the category text printed on that source. Voucher rows use the account description printed beside the account code. The Scottsdale accounts payable report has no account code, so its pie uses the DAC column as printed. Districts are not merged into one taxonomy. A slice with no printed category is labeled “No category printed.” Slices under 2 percent are grouped as “Other (as printed).”
          </p>
          <p className="mt-2">
            Inferred category, not a budget code. The inferred category is a separate label from the ruleset <span className="font-semibold">phoenix-k12-neutral-2026.11.11</span>. Unclassified is the default. Metered natural gas, water, sewer, and electricity are utilities. An account title printed on the row is stronger evidence than item text. These labels are not USFR codes. Amazon is a vendor, not a category. Department or DAC text is as printed, not a verified school location.
          </p>
        </section>

        <section id="read-vendors" className="rounded-xl border border-teal/10 bg-page p-5">
          <h3 className="font-extrabold text-2xl">Vendors</h3>
          <p className="mt-2">
            Vendor totals are the amount paid to that vendor by indexed districts (reported / vouchered). They are not vendor revenue and not a vendor’s total sales. Coverage is not continuous. The printed payee is the name that appears most often. Vendor keys collapse spacing and punctuation. Personal and unknown payees are not listed. This is not unique spend, not a printed report total, and not complete coverage of that vendor or of any district.
          </p>
        </section>

        <section id="read-enrollment" className="rounded-xl border border-teal/10 bg-page p-5">
          <h3 className="font-extrabold text-2xl">October 1 enrollment</h3>
          <p className="mt-2">
            October 1 enrollment (ADE headcount) is a headcount of students enrolled on that day. It is not ADM, and it is not part of the screened spending total. A per-student figure is a reported amount in this index per enrolled student. It is not cost per pupil and not total district spending.
          </p>
          <p className="mt-2">
            School year YYYY-(YYYY+1) pairs with spending dated July 1, YYYY through June 30, YYYY+1. School year 2025-2026 pairs with 2025-07-01 through 2026-06-30. The project coverage window still starts 2024-07-01.
          </p>
          <p className="mt-2">
            An asterisk or a blank Total stays null. District totals for 2010-2011 through 2016-2017 are not on the same basis as 2017-2018 onward and are not a continuous series. 2010-2011 has no single all-students LEA total, and those residence pairs are not summed. 2011-2012 through 2016-2017 are district-of-residence subtotals ADE printed in the school tab. A blank or asterisk statewide total stays null and is not a denominator. School years without a loaded workbook are not drawn. Counts from before 2017-2018 are not connected to the later series.
          </p>
          <p className="mt-2">
            <Link className="font-semibold text-teal underline" href="/enrollment">Open the enrollment comparison</Link>.
          </p>
        </section>

        <section id="read-coverage" className="rounded-xl border border-teal/10 bg-page p-5">
          <h3 className="font-extrabold text-2xl">Coverage</h3>
          <p className="mt-2">
            This is not an official government site. The index covers administrative Maricopa and Pinal districts that have been indexed, from July 1, 2024 onward: Chandler, Higley, Paradise Valley, Queen Creek, and Scottsdale. It is not a census of Arizona schools, not every Phoenix school, and not a district’s full year. No coverage percentage is shown.
          </p>
          <p className="mt-2">
            The spending total uses only observed documents whose parsed detail lines reconciled to the printed total on that same document. An unindexed file is not zero spending. Searched with no source is a limited search result, not proof that no ledger exists. Unsearched means no query was recorded. Administrative county is not service geography. AZDOR site counts and county directory names are not an active-district denominator.
          </p>
          <p className="mt-2">
            When two Scottsdale report headers share a calendar date but the parsed check dates do not overlap, both documents stay in the default sum. A shared check date would be kept out of the default total, the charts, and the CSV. The project coverage window starts 2024-07-01. The ingest does not delete a public line only because its date is earlier.
          </p>
        </section>

        <section id="read-groups" className="rounded-xl border border-teal/10 bg-page p-5">
          <h3 className="font-extrabold text-2xl">Groups</h3>
          <p className="mt-2">
            Item groups are reviewed phrases in the public description, such as “stress balls.” They are sums of screened public lines, not unique spend, not printed report totals, and not complete district or statewide coverage. They are not budget codes. The line amount is the spend. A not-to-exceed figure printed in a description is not the spend total. Broad words such as “ball” are not groups.
          </p>
        </section>
      </section>

      <section id="source-documents">
        <h2 className="font-extrabold text-2xl">Source documents</h2>
        <p className="mt-2">
          Indexed documents are in the spending total. Fetched documents that did not reconcile are listed after them.
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
