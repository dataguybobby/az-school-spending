import { dollars } from "@/lib/utils";
import { formatShare, NO_CATEGORY_PRINTED, OTHER_AS_PRINTED, type PieSlice } from "@/lib/printed-slices";
import type { DistrictPie } from "@/lib/chart-data";

const FILLS = ["#0f5c66", "#e07a3d", "#c4922a", "#3d8a84", "#a34b32", "#6e8b3d", "#1f4e5a", "#8a6a2f"];
const PIE_WORDING = "Each pie is one district's screened lines, grouped by the category text printed on that source. Different districts are not merged into one taxonomy. A slice with no printed category is labeled No category printed.";

export function CategoryPies({ pies }: { pies: DistrictPie[] }) {
  return (
    <section id="category-pies" className="rounded-xl border border-teal/10 bg-page p-4">
      <h2 className="font-semibold">Printed category, one district at a time</h2>
      <p className="mt-1 max-w-3xl text-sm leading-6 text-teal/75">
        {PIE_WORDING}
      </p>
      <p className="mt-2 max-w-3xl text-xs leading-5 text-teal/60">
        Voucher rows use the account description printed beside the account code. The Scottsdale accounts payable report has no account code; its pie uses the DAC column as printed. The inferred category is not used here. Amazon is a vendor, not a category. Slices under 2 percent are grouped as Other (as printed).
      </p>
      {pies.length === 0 ? (
        <p className="mt-4 text-sm text-teal/70">No screened lines in this filter.</p>
      ) : (
        <div className="mt-4 grid gap-4 lg:grid-cols-2">
          {pies.map((pie) => <DistrictPieChart key={pie.sourceId} pie={pie} />)}
        </div>
      )}
    </section>
  );
}

function DistrictPieChart({ pie }: { pie: DistrictPie }) {
  const colors = colorMap(pie.slices);
  const wedges = pie.slices.filter((slice) => slice.amountCents > 0);
  const wedgeTotal = wedges.reduce((sum, slice) => sum + slice.amountCents, 0);
  return (
    <article className="rounded-lg border border-teal/10 p-3">
      <h3 className="font-semibold">{pie.district}</h3>
      <p className="text-xs text-teal/60">{pie.fieldLabel} · {dollars(pie.totalCents)}</p>
      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
        <PieSvg title={`${pie.district} ${pie.fieldLabel}`} slices={wedges} total={wedgeTotal} colors={colors} />
        <ul className="min-w-0 flex-1 space-y-1 text-xs">
          {pie.slices.map((slice) => (
            <li key={slice.label} className="flex items-start justify-between gap-2">
              <span className="flex min-w-0 items-start gap-2">
                <span className="mt-0.5 inline-block h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: colors.get(slice.label) }} />
                <span className="break-words">{slice.label}</span>
              </span>
              <span className="shrink-0">{dollars(slice.amountCents)} · {formatShare(slice.share)}</span>
            </li>
          ))}
        </ul>
      </div>
      <SliceTable pie={pie} />
    </article>
  );
}

function PieSvg({ title, slices, total, colors }: { title: string; slices: PieSlice[]; total: number; colors: Map<string, string> }) {
  const size = 180;
  const center = size / 2;
  const radius = 72;
  let angle = -Math.PI / 2;
  return (
    <svg viewBox={`0 0 ${size} ${size}`} role="img" className="h-40 w-40 shrink-0">
      <title>{title}</title>
      {slices.length === 0 || total <= 0 ? (
        <circle cx={center} cy={center} r={radius} className="fill-teal/10" />
      ) : slices.length === 1 ? (
        <circle cx={center} cy={center} r={radius} fill={colors.get(slices[0].label)}>
          <title>{`${slices[0].label}: ${dollars(slices[0].amountCents)} ${formatShare(slices[0].share)}`}</title>
        </circle>
      ) : (
        slices.map((slice) => {
          const sweep = (slice.amountCents / total) * Math.PI * 2;
          const start = angle;
          const end = angle + sweep;
          angle = end;
          const path = wedgePath(center, center, radius, start, end);
          return (
            <path key={slice.label} d={path} fill={colors.get(slice.label)}>
              <title>{`${slice.label}: ${dollars(slice.amountCents)} ${formatShare(slice.share)}`}</title>
            </path>
          );
        })
      )}
    </svg>
  );
}

function SliceTable({ pie }: { pie: DistrictPie }) {
  const other = pie.slices.find((slice) => slice.label === OTHER_AS_PRINTED);
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="w-full text-left text-xs">
        <caption className="mb-1 text-left text-teal/60">{pie.fieldLabel}. Share uses the screened total for this district in the filter.</caption>
        <thead className="border-b border-teal/10 uppercase tracking-wide text-teal/50">
          <tr>
            <th className="py-1 pr-2">Printed label</th>
            <th className="py-1 pr-2">Amount</th>
            <th className="py-1 pr-2">Share</th>
            <th className="py-1">Lines</th>
          </tr>
        </thead>
        <tbody>
          {pie.slices.map((slice) => (
            <tr key={slice.label} className="border-b border-teal/5">
              <td className="py-1 pr-2">{slice.label}</td>
              <td className="py-1 pr-2">{dollars(slice.amountCents)}</td>
              <td className="py-1 pr-2">{formatShare(slice.share)}</td>
              <td className="py-1">{slice.lineCount.toLocaleString("en-US")}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {other && other.members.length > 1 ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs font-semibold text-teal">Labels inside Other (as printed)</summary>
          <table className="mt-1 w-full text-left text-xs">
            <thead className="border-b border-teal/10 uppercase tracking-wide text-teal/50">
              <tr>
                <th className="py-1 pr-2">Printed label</th>
                <th className="py-1 pr-2">Amount</th>
                <th className="py-1">Share</th>
              </tr>
            </thead>
            <tbody>
              {other.members.map((member) => (
                <tr key={member.label} className="border-b border-teal/5">
                  <td className="py-1 pr-2">{member.label}</td>
                  <td className="py-1 pr-2">{dollars(member.amountCents)}</td>
                  <td className="py-1">{formatShare(pie.totalCents === 0 ? null : member.amountCents / pie.totalCents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      ) : null}
    </div>
  );
}

function colorMap(slices: PieSlice[]): Map<string, string> {
  const colors = new Map<string, string>();
  let named = 0;
  for (const slice of slices) {
    if (slice.label === NO_CATEGORY_PRINTED) colors.set(slice.label, "#5c5346");
    else if (slice.label === OTHER_AS_PRINTED) colors.set(slice.label, "#d9d0c1");
    else colors.set(slice.label, FILLS[named++ % FILLS.length]);
  }
  return colors;
}

function wedgePath(cx: number, cy: number, radius: number, start: number, end: number): string {
  const x1 = cx + radius * Math.cos(start);
  const y1 = cy + radius * Math.sin(start);
  const x2 = cx + radius * Math.cos(end);
  const y2 = cy + radius * Math.sin(end);
  const large = end - start > Math.PI ? 1 : 0;
  return `M ${cx} ${cy} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${radius} ${radius} 0 ${large} 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z`;
}
