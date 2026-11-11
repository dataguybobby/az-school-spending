import fs from "node:fs";
import path from "node:path";
import { openDb } from "@/lib/db";

export const dynamic = "force-dynamic";

type Source = Record<string, string | number | null>;

export default async function SourcesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const db = openDb();
  const status = params.status || "";
  const q = (params.q || "").toLowerCase();
  const sources = db.prepare("SELECT * FROM sources ORDER BY source_status, entity_name").all() as Source[];
  const filtered = sources.filter((source) => {
    if (status && source.source_status !== status) return false;
    if (!q) return true;
    return `${source.entity_name} ${source.source_id} ${source.lea_ctds || ""}`.toLowerCase().includes(q);
  });
  const counts = db.prepare("SELECT source_status, COUNT(*) AS n FROM sources GROUP BY source_status ORDER BY n DESC").all() as Array<{ source_status: string; n: number }>;
  const ingestion = db.prepare("SELECT ingestion_status, COUNT(*) AS n FROM sources GROUP BY ingestion_status").all() as Array<{ ingestion_status: string; n: number }>;
  const backlog = readBacklog(params.backlog || "");

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-teal/10 bg-page p-5">
        <h1 className="font-extrabold text-3xl">Source catalog</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-teal/80">
          Registry status and ingestion status are different. Confirmed means a line-item document was identified. Indexed means this run parsed it and the lines matched a printed total.
          Searched with no source is a limited search result, not proof that no ledger exists. Unsearched means no query was recorded. This is not a complete metro census, and no coverage percentage is shown.
        </p>
        <p className="mt-3 text-sm">
          AZDOR 2026 snapshot: 1,449 site rows and 395 distinct CTDS holder IDs, including closed sites. County directories list 57 Maricopa and 21 Pinal institutional names. None of those numbers is an active-district denominator. Administrative county is not service geography. No Pinal ledger is confirmed beyond Queen Creek administrative metadata.
        </p>
      </section>
      <SourceDocuments />
      <section className="grid gap-3 md:grid-cols-2">
        <ul className="rounded-xl border border-teal/10 bg-page p-4 text-sm">
          {counts.map((row) => <li key={row.source_status} className="flex justify-between border-b border-teal/5 py-1"><span>{row.source_status}</span><span>{row.n}</span></li>)}
        </ul>
        <ul className="rounded-xl border border-teal/10 bg-page p-4 text-sm">
          {ingestion.map((row) => <li key={row.ingestion_status} className="flex justify-between border-b border-teal/5 py-1"><span>{row.ingestion_status}</span><span>{row.n}</span></li>)}
        </ul>
      </section>
      <form className="flex flex-wrap gap-2" action="/sources">
        <input name="q" defaultValue={params.q || ""} placeholder="Entity, id, or CTDS" className="rounded-md border border-teal/15 px-3 py-2" />
        <select name="status" defaultValue={status} className="rounded-md border border-teal/15 px-3 py-2">
          <option value="">All registry statuses</option>
          {counts.map((row) => <option key={row.source_status}>{row.source_status}</option>)}
        </select>
        <button className="rounded-md bg-terracotta px-3 py-2 text-sm font-semibold text-white" type="submit">Filter</button>
      </form>
      <div className="overflow-x-auto rounded-xl border border-teal/10 bg-page">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead className="border-b border-teal/10 text-xs uppercase tracking-wide text-teal/60">
            <tr>
              <th className="px-3 py-2">Entity</th>
              <th className="px-3 py-2">Registry status</th>
              <th className="px-3 py-2">Adapter family</th>
              <th className="px-3 py-2">Discovery</th>
              <th className="px-3 py-2">Ingestion</th>
              <th className="px-3 py-2">Admin county label</th>
              <th className="px-3 py-2">CTDS</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((source) => (
              <tr key={String(source.source_id)} className="border-b border-teal/5 align-top">
                <td className="px-3 py-2">
                  <div className="font-semibold">{source.entity_name}</div>
                  <div className="text-xs text-teal/50">{source.entity_type} · {source.document_class}</div>
                </td>
                <td className="px-3 py-2">{source.source_status}</td>
                <td className="px-3 py-2">{source.adapter_family}</td>
                <td className="px-3 py-2">{source.discovery_state}</td>
                <td className="px-3 py-2">{source.ingestion_status}</td>
                <td className="px-3 py-2">{source.admin_county || "Not labeled"}</td>
                <td className="px-3 py-2">{source.lea_ctds || "Not joined"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <section className="rounded-xl border border-teal/10 bg-page p-4">
        <h2 className="font-semibold">CTDS backlog</h2>
        <p className="mt-1 text-sm text-teal/70">Unmatched rows stay unsearched. A name here was not automatically treated as unavailable.</p>
        <form className="mt-3 flex gap-2" action="/sources">
          <input name="backlog" defaultValue={params.backlog || ""} placeholder="Search backlog name or CTDS" className="rounded-md border border-teal/15 px-3 py-2" />
          <button className="rounded-md border border-teal/15 px-3 py-2 text-sm font-semibold" type="submit">Search backlog</button>
        </form>
        <ul className="mt-3 space-y-1 text-sm">
          {backlog.map((row) => (
            <li key={row.id}>{row.id} · {row.name} · {row.county} · {row.status}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function SourceDocuments() {
  const db = openDb();
  const documents = db.prepare(
    `SELECT d.document_id, s.entity_name, d.url, d.indexed, d.parsed_outcome, d.public_line_count
     FROM documents d LEFT JOIN sources s ON s.source_id = d.source_id
     ORDER BY d.indexed DESC, s.entity_name`,
  ).all() as Array<{ document_id: string; entity_name: string | null; url: string | null; indexed: number; parsed_outcome: string | null; public_line_count: number | null }>;
  return (
    <section className="rounded-xl border border-teal/10 bg-page p-4 text-sm">
      <h2 className="font-semibold">Official documents in this snapshot</h2>
      <p className="mt-1 text-teal/70">Links open the district or board page. Raw PDFs are not hosted here. An unindexed file is not zero spending.</p>
      <ul className="mt-3 space-y-2">
        {documents.map((row) => (
          <li key={row.document_id}>
            <span className="font-semibold">{row.indexed ? "Indexed" : "Not indexed"}</span>
            {" · "}{row.entity_name || row.document_id}
            {" · "}{row.parsed_outcome}
            {" · "}{row.public_line_count ?? 0} public lines
            {row.url ? <> · <a className="font-semibold text-teal underline" href={row.url}>Official source</a></> : null}
          </li>
        ))}
      </ul>
      <p className="mt-3"><a className="font-semibold text-teal underline" href="/methodology">Full source list and methodology</a></p>
    </section>
  );
}

function readBacklog(query: string): Array<{ id: string; name: string; county: string; status: string }> {
  const file = path.resolve(process.cwd(), "../registry/v2/coverage_worklist_2026_candidates.csv");
  if (!fs.existsSync(file)) return [];
  const lines = fs.readFileSync(file, "utf8").split(/\r?\n/).slice(1).filter(Boolean);
  const needle = query.toLowerCase();
  const rows = [];
  for (const line of lines) {
    const [id, name, , , , , , , , county, , status] = splitCsv(line);
    if (needle && !`${id} ${name}`.toLowerCase().includes(needle)) continue;
    rows.push({ id, name, county, status });
    if (rows.length >= 25) break;
  }
  return rows;
}

function splitCsv(line: string): string[] {
  const cells: string[] = [];
  let current = "";
  let quoted = false;
  for (const char of line) {
    if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      cells.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  cells.push(current);
  return cells;
}
