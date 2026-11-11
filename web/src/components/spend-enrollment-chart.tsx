import { dollars } from "@/lib/utils";
import { contiguousSpendSegments, type EnrollmentMark } from "@/lib/spend-series";
import type { SpendChart } from "@/lib/chart-data";

const SERIES = ["#0f5c66", "#e07a3d", "#c4922a", "#3d8a84", "#a34b32"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function SpendEnrollmentChart({ chart }: { chart: SpendChart }) {
  return (
    <section id="spend-over-time" className="rounded-xl border border-teal/10 bg-page p-4">
      <h2 className="font-semibold">Screened spend by month, with October 1 enrollment</h2>
      <p className="mt-1 max-w-3xl text-sm leading-6 text-teal/75">
        A gap is a month with no indexed document in this filter, not a month of zero spending. October 1 enrollment (ADE headcount, not ADM) is a separate series.
      </p>
      <p className="mt-2 max-w-3xl text-xs leading-5 text-teal/60">
        Solid lines are screened amounts on the selected date basis. A dashed step is the official October 1 headcount for that school year, from July 1 through June 30, with a marker on October 1. School years without a loaded workbook are not drawn. Counts from before 2017-2018 are not connected to the later series. This is not continuous coverage and not cost per pupil.
      </p>
      {chart.months.length === 0 ? (
        <p className="mt-4 text-sm text-teal/70">No indexed lines have a date on this basis inside the filter.</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <ChartSvg chart={chart} />
        </div>
      )}
      {chart.undated.length > 0 ? (
        <p className="mt-3 text-xs leading-5 text-teal/65">
          {chart.undated.map((row) => `${row.district}: ${row.lineCount.toLocaleString("en-US")} screened lines have no date on this basis and are not on the chart (${dollars(row.amountCents)}).`).join(" ")}
        </p>
      ) : null}
      <ChartTable chart={chart} />
    </section>
  );
}

function ChartSvg({ chart }: { chart: SpendChart }) {
  const width = Math.max(720, chart.months.length * 36 + 120);
  const height = 340;
  const left = 64;
  const right = 56;
  const top = 18;
  const bottom = 64;
  const innerWidth = width - left - right;
  const innerHeight = height - top - bottom;
  const slot = innerWidth / Math.max(chart.months.length, 1);
  const spendValues = chart.districts.flatMap((district) =>
    district.points.map((point) => point.amountCents).filter((value): value is number => value != null),
  );
  const spendMin = Math.min(0, ...spendValues);
  const spendMax = Math.max(0, ...spendValues, 1);
  const spendSpan = Math.max(spendMax - spendMin, 1);
  const enrollMax = Math.max(1, ...chart.districts.flatMap((district) => district.enrollment.map((mark) => mark.headcount)));
  const ySpend = (cents: number) => top + innerHeight - ((cents - spendMin) / spendSpan) * innerHeight;
  const yEnroll = (count: number) => top + innerHeight - (count / enrollMax) * innerHeight;
  const xCenter = (index: number) => left + index * slot + slot / 2;
  const monthIndex = new Map(chart.months.map((month, index) => [month, index]));

  return (
    <svg viewBox={`0 0 ${width} ${height}`} role="img" className="h-80 min-w-[720px]">
      <title>Screened spend by month and October 1 enrollment</title>
      <line x1={left} x2={width - right} y1={ySpend(0)} y2={ySpend(0)} className="stroke-teal/20" />
      {chart.months.map((month, index) => (
        <text key={month} x={xCenter(index)} y={height - 28} textAnchor="middle" className="fill-teal text-[9px]" transform={`rotate(-40 ${xCenter(index)} ${height - 28})`}>
          {formatMonth(month)}
        </text>
      ))}
      <text x="14" y={top + 10} className="fill-teal text-[10px]">{dollars(spendMax)}</text>
      <text x={width - right + 8} y={top + 10} className="fill-terracotta text-[10px]">{enrollMax.toLocaleString("en-US")}</text>
      {chart.districts.map((district, series) => {
        const color = SERIES[series % SERIES.length];
        const segments = contiguousSpendSegments(district.points);
        return (
          <g key={district.sourceId}>
            {segments.map((segment) => {
              const path = segment.map((point, index) => {
                const command = index === 0 ? "M" : "L";
                const at = monthIndex.get(point.month) ?? 0;
                return `${command} ${xCenter(at).toFixed(1)} ${ySpend(point.amountCents ?? 0).toFixed(1)}`;
              }).join(" ");
              return <path key={segment[0]?.month} d={path} fill="none" stroke={color} strokeWidth="2.5" />;
            })}
            {district.points.map((point) => {
              if (point.amountCents == null) return null;
              const at = monthIndex.get(point.month) ?? 0;
              return (
                <circle key={point.month} cx={xCenter(at)} cy={ySpend(point.amountCents)} r="3" fill={color}>
                  <title>{`${district.district} ${formatMonth(point.month)}: ${dollars(point.amountCents)}`}</title>
                </circle>
              );
            })}
            {district.enrollment.map((mark) => (
              <EnrollmentStep
                key={mark.schoolYear}
                mark={mark}
                color={color}
                monthIndex={monthIndex}
                slot={slot}
                xCenter={xCenter}
                y={yEnroll(mark.headcount)}
                left={left}
                rightEdge={width - right}
              />
            ))}
          </g>
        );
      })}
    </svg>
  );
}

function EnrollmentStep({
  mark,
  color,
  monthIndex,
  slot,
  xCenter,
  y,
  left,
  rightEdge,
}: {
  mark: EnrollmentMark;
  color: string;
  monthIndex: Map<string, number>;
  slot: number;
  xCenter: (index: number) => number;
  y: number;
  left: number;
  rightEdge: number;
}) {
  const start = monthIndex.get(mark.july);
  const end = monthIndex.get(mark.june);
  const october = monthIndex.get(mark.october);
  const x1 = start == null ? left : xCenter(start) - slot / 2;
  const x2 = end == null ? rightEdge : xCenter(end) + slot / 2;
  return (
    <g>
      <line x1={x1} x2={x2} y1={y} y2={y} stroke={color} strokeWidth="1.5" strokeDasharray="5 4" />
      {october == null ? null : (
        <circle cx={xCenter(october)} cy={y} r="4.5" fill="#fbf6ec" stroke={color} strokeWidth="2">
          <title>{`${mark.schoolYear} October 1 enrollment (ADE headcount, not ADM): ${mark.headcount.toLocaleString("en-US")}`}</title>
        </circle>
      )}
    </g>
  );
}

function ChartTable({ chart }: { chart: SpendChart }) {
  if (chart.months.length === 0) return null;
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-xs">
        <caption className="mb-2 text-left text-teal/70">
          A blank spend cell is a month with no indexed document, not zero spending. October 1 enrollment is the ADE headcount for the school year that contains the month, shown on each month from July through June. It is not a monthly count and not ADM.
        </caption>
        <thead className="border-b border-teal/10 uppercase tracking-wide text-teal/50">
          <tr>
            <th className="py-1 pr-2">Month</th>
            {chart.districts.map((district) => (
              <th key={district.sourceId} className="py-1 pr-2">{district.district}</th>
            ))}
            {chart.districts.map((district) => (
              <th key={`${district.sourceId}-enroll`} className="py-1 pr-2">{district.district} October 1 enrollment</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {chart.months.map((month, index) => (
            <tr key={month} className="border-b border-teal/5">
              <th className="py-1 pr-2 font-semibold" scope="row">{formatMonth(month)}</th>
              {chart.districts.map((district) => {
                const point = district.points[index];
                return <td key={district.sourceId} className="py-1 pr-2">{point?.amountCents == null ? "" : dollars(point.amountCents)}</td>;
              })}
              {chart.districts.map((district) => (
                <td key={`${district.sourceId}-enroll`} className="py-1 pr-2">{enrollmentAt(district.enrollment, month)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="mt-3 flex flex-wrap gap-3 text-xs">
        {chart.districts.map((district, index) => (
          <li key={district.sourceId} className="flex items-center gap-2">
            <span className="inline-block h-2 w-6 rounded-sm" style={{ background: SERIES[index % SERIES.length] }} />
            {district.district} screened amount
            <span className="inline-block h-0 w-6 border-t-2 border-dashed" style={{ borderColor: SERIES[index % SERIES.length] }} />
            October 1 enrollment
          </li>
        ))}
      </ul>
    </div>
  );
}

function enrollmentAt(marks: EnrollmentMark[], month: string): string {
  const mark = marks.find((item) => month >= item.july && month <= item.june);
  if (!mark) return "";
  return mark.headcount.toLocaleString("en-US");
}

function formatMonth(month: string): string {
  const index = Number(month.slice(5, 7)) - 1;
  return `${MONTHS[index] ?? month} ${month.slice(0, 4)}`;
}
