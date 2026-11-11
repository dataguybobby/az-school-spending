import { dollars } from "@/lib/utils";

type Bar = { label: string; amount_cents: number; note?: string };

export function BarChart({
  title,
  bars,
  empty,
}: {
  title: string;
  bars: Bar[];
  empty: string;
}) {
  const width = 640;
  const height = 220;
  const max = Math.max(...bars.map((bar) => Math.abs(bar.amount_cents)), 1);
  return (
    <figure className="rounded-xl border border-teal/10 bg-page p-4">
      <figcaption className="mb-3 text-sm font-semibold text-teal">{title}</figcaption>
      {bars.length === 0 ? (
        <p className="text-sm text-teal/70">{empty}</p>
      ) : (
        <svg viewBox={`0 0 ${width} ${height}`} role="img" className="h-56 w-full">
          <title>{title}</title>
          <line x1="8" x2={width - 8} y1="170" y2="170" className="stroke-teal/20" />
          {bars.map((bar, index) => {
            const slot = width / bars.length;
            const barWidth = Math.max(slot - 14, 8);
            const barHeight = (Math.abs(bar.amount_cents) / max) * 150;
            const x = index * slot + 8;
            const y = 170 - barHeight;
            return (
              <g key={bar.label}>
                <rect x={x} y={y} width={barWidth} height={barHeight} rx="3" className="fill-terracotta" />
                <text x={x + barWidth / 2} y={188} textAnchor="middle" className="fill-teal text-[10px]">
                  {bar.label}
                </text>
                <title>{`${bar.label}: ${dollars(bar.amount_cents)}${bar.note ? ` (${bar.note})` : ""}`}</title>
              </g>
            );
          })}
        </svg>
      )}
      <ul className="mt-3 grid gap-1 text-xs text-teal/70 sm:grid-cols-2">
        {bars.map((bar) => (
          <li key={`${bar.label}-${bar.note || ""}`} className="flex justify-between gap-2">
            <span>{bar.note || bar.label}</span>
            <span>{dollars(bar.amount_cents)}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-teal/60">
        Categories are inferred. Months or categories with no indexed lines are omitted. A missing month is not zero spending.
      </p>
    </figure>
  );
}
