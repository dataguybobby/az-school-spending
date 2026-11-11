import { dollars } from "@/lib/utils";

type Slice = { label: string; amount_cents: number; lines: number };

type Rect = Slice & { x: number; y: number; w: number; h: number };

export function VendorTreemap({ slices }: { slices: Slice[] }) {
  const width = 640;
  const height = 280;
  const rects = layout(slices.filter((slice) => slice.amount_cents > 0), 0, 0, width, height, true);
  return (
    <figure className="rounded-xl border border-teal/10 bg-page p-4">
      <figcaption className="text-sm font-semibold">Screened vendor spending in this filter</figcaption>
      <p className="mt-1 text-xs leading-5 text-teal/60">
        Area is the sum of screened public lines for that vendor. Other screened vendors are grouped. This is not unique spend and not a printed report total.
      </p>
      {rects.length === 0 ? (
        <p className="mt-4 text-sm text-teal/70">No positive screened amounts in this filter.</p>
      ) : (
        <svg viewBox={`0 0 ${width} ${height}`} role="img" className="mt-3 h-72 w-full">
          <title>Vendor treemap of screened public lines</title>
          {rects.map((rect, index) => (
            <g key={rect.label}>
              <rect
                x={rect.x + 1}
                y={rect.y + 1}
                width={Math.max(rect.w - 2, 0)}
                height={Math.max(rect.h - 2, 0)}
                rx="4"
                className={index % 2 === 0 ? "fill-terracotta" : "fill-gold"}
              />
              {rect.w > 72 && rect.h > 36 ? (
                <text x={rect.x + 8} y={rect.y + 18} className={index % 2 === 0 ? "fill-cream text-[11px]" : "fill-teal text-[11px]"}>
                  {rect.label.slice(0, 28)}
                </text>
              ) : null}
              {rect.w > 72 && rect.h > 52 ? (
                <text x={rect.x + 8} y={rect.y + 34} className={index % 2 === 0 ? "fill-cream text-[10px]" : "fill-teal text-[10px]"}>
                  {dollars(rect.amount_cents)}
                </text>
              ) : null}
              <title>{`${rect.label}: ${dollars(rect.amount_cents)} across ${rect.lines} lines`}</title>
            </g>
          ))}
        </svg>
      )}
    </figure>
  );
}

function layout(slices: Slice[], x: number, y: number, w: number, h: number, vertical: boolean): Rect[] {
  if (slices.length === 0 || w <= 0 || h <= 0) return [];
  if (slices.length === 1) return [{ ...slices[0], x, y, w, h }];
  const total = slices.reduce((sum, slice) => sum + slice.amount_cents, 0);
  if (total <= 0) return [];
  let cursor = 0;
  let split = 1;
  for (let index = 0; index < slices.length - 1; index += 1) {
    cursor += slices[index].amount_cents;
    split = index + 1;
    if (cursor >= total / 2) break;
  }
  const left = slices.slice(0, split);
  const right = slices.slice(split);
  const leftSum = left.reduce((sum, slice) => sum + slice.amount_cents, 0);
  const fraction = leftSum / total;
  if (vertical) {
    const leftWidth = w * fraction;
    return [
      ...layout(left, x, y, leftWidth, h, false),
      ...layout(right, x + leftWidth, y, w - leftWidth, h, false),
    ];
  }
  const leftHeight = h * fraction;
  return [
    ...layout(left, x, y, w, leftHeight, true),
    ...layout(right, x, y + leftHeight, w, h - leftHeight, true),
  ];
}
