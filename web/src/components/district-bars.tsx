import { HowToRead } from "@/components/how-to-read";
import { dollars } from "@/lib/utils";

type District = { entity_name: string; amount_cents: number; line_count: number; documents: number };

export function DistrictBars({ rows }: { rows: District[] }) {
  const max = Math.max(...rows.map((row) => Math.abs(row.amount_cents)), 1);
  return (
    <section className="rounded-xl border border-teal/10 bg-page p-4">
      <h2 className="font-semibold">Observed documents, side by side</h2>
      <p className="mt-1 text-base">
        Screened lines from indexed documents. <HowToRead anchor="read-coverage" />
      </p>
      {rows.length === 0 ? (
        <p className="mt-4 text-sm text-teal/70">No screened lines are in the default total.</p>
      ) : (
        <ul className="mt-4 space-y-3">
          {rows.map((row) => (
            <li key={row.entity_name}>
              <div className="flex items-baseline justify-between gap-3 text-base">
                <span className="font-semibold">{row.entity_name}</span>
                <span className="shrink-0">{dollars(row.amount_cents)}</span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-ink/5">
                <div
                  className="h-2 rounded-full bg-terracotta"
                  style={{ width: `${Math.max((Math.abs(row.amount_cents) / max) * 100, 2)}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-teal/55">
                {row.documents} observed document{row.documents === 1 ? "" : "s"} · {row.line_count.toLocaleString()} screened lines
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
