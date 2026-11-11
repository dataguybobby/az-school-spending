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
    <figure className="rounded-xl border border-ink/10 bg-white p-4">
      <figcaption className="mb-3 text-sm font-semibold text-ink">{title}</figcaption>
      {bars.length === 0 ? (
        <p className="text-sm text-ink/70">{empty}</p>
      ) : (
        <svg viewBox={`0 0 ${width} ${height}`} role="img" className="h-56 w-full">
          <title>{title}</title>
          {bars.map((bar, index) => {
            const slot = width / bars.length;
            const barWidth = Math.max(slot - 14, 8);
            const barHeight = (Math.abs(bar.amount_cents) / max) * 150;
            const x = index * slot + 8;
            const y = 170 - barHeight;
            return (
              <g key={bar.label}>
                <rect x={x} y={y} width={barWidth} height={barHeight} rx="3" className="fill-copper" />
                <text x={x + barWidth / 2} y={188} textAnchor="middle" className="fill-ink text-[10px]">
                  {bar.label}
                </text>
                <title>{`${bar.label}: ${dollars(bar.amount_cents)}${bar.note ? ` (${bar.note})` : ""}`}</title>
              </g>
            );
          })}
        </svg>
      )}
      <p className="mt-2 text-xs text-ink/60">
        Months or categories with no indexed lines are omitted. A missing month is not zero spending.
      </p>
    </figure>
  );
}
