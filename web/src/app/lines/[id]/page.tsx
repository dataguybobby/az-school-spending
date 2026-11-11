import Link from "next/link";
import { notFound } from "next/navigation";
import { HowToRead } from "@/components/how-to-read";
import { openDb } from "@/lib/db";
import { dollars } from "@/lib/utils";

export const dynamic = "force-dynamic";

type Line = Record<string, string | number | null>;

export default async function LinePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const db = openDb();
  const line = db.prepare("SELECT * FROM lines WHERE line_id = ?").get(id) as Line | undefined;
  if (!line) notFound();
  const document = db.prepare("SELECT * FROM documents WHERE document_id = ?").get(String(line.document_id)) as Line | undefined;
  return (
    <article className="space-y-6">
      <p><Link href="/" className="text-sm font-semibold text-teal">Back to search</Link></p>
      <header>
        <p className="text-sm font-semibold uppercase tracking-wide text-teal">Reported line</p>
        <h1 className="font-extrabold text-3xl">{dollars(Number(line.amount_cents))} · {line.vendor_raw}</h1>
        <p className="mt-2 max-w-3xl text-teal/80">{line.description_public}</p>
      </header>
      <section className="grid gap-4 md:grid-cols-3">
        <Card title="As printed" rows={[
          ["Vendor", line.vendor_raw],
          ["Description", line.description_public],
          ["Amount", dollars(Number(line.amount_cents))],
          ["DAC / department", line.dac_raw || "Not on this report"],
          ["Account code", line.account_code_raw || "Not on this report"],
          ["PO number", line.po_raw || "Blank on this row"],
        ]} />
        <Card title="Dates, kept separate" rows={[
          ["Check date", line.check_date || line.check_date_null_reason],
          ["Voucher batch date", line.voucher_batch_date || "Not a voucher batch date"],
          ["Batch date as printed", line.voucher_batch_date_raw || "—"],
          ["Batch number", line.voucher_batch_number || "—"],
          ["Native FY label", line.fiscal_year_label_native || "Not printed as a fiscal-year label"],
          ["Report window", line.period_label_native || "—"],
        ]} />
        <Card title="Inferred, not sourced as fact" rows={[
          ["Category", line.category],
          ["Confidence", line.category_confidence],
          ["Ruleset", line.category_ruleset],
          ["Evidence", line.category_evidence],
          ["Vendor match key", line.vendor_key],
          ["Flags", line.flags || "None"],
        ]} />
      </section>
      <section className="rounded-xl border border-teal/10 bg-page p-4 text-sm">
        <h2 className="font-semibold">Source locator</h2>
        <p className="mt-2">Page {line.source_page}, row {line.source_row}. {line.source_locator}.</p>
        <p className="mt-2">
          <a className="font-semibold text-teal underline" href={String(line.source_url)}>Official source document</a>
          {" · "}
          <Link className="font-semibold text-teal underline" href="/methodology">Methodology</Link>
        </p>
        {line.item_label ? (
          <p className="mt-2">
            Grouped from description text as “{line.item_label}” (evidence “{line.item_evidence}”, {line.item_method}, confidence {line.item_confidence}).
            {" "}
            <Link className="font-semibold text-teal underline" href={`/explore/items/${String(line.item_label).toLowerCase().replaceAll(" ", "-")}`}>Open the group</Link>
          </p>
        ) : null}
        <p className="mt-2">
          {line.amount_semantics}. {document ? `Reconciliation: ${document.reconciliation_status}. ` : ""}
          <HowToRead anchor="read-privacy" />
        </p>
      </section>
    </article>
  );
}

function Card({ title, rows }: { title: string; rows: Array<[string, unknown]> }) {
  return (
    <section className="rounded-xl border border-teal/10 bg-page p-4">
      <h2 className="font-semibold">{title}</h2>
      <dl className="mt-3 space-y-2 text-sm">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs uppercase tracking-wide text-teal/50">{label}</dt>
            <dd className="break-words">{String(value ?? "—")}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
