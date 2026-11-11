import { HowToRead } from "@/components/how-to-read";
import { dollars } from "@/lib/utils";
import { axisTicks, contiguousSpendSegments, labelStepFor, monthsToLabel, monthsWithSpend, type EnrollmentMark, type SpendPoint } from "@/lib/spend-series";
import type { DistrictSpend, SpendChart } from "@/lib/chart-data";

const SERIES = ["#0f5c66", "#e07a3d", "#c4922a", "#3d8a84", "#a34b32"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const SPEND_AXIS = "Screened spend per month ($)";
const ENROLL_AXIS = "ADE headcount";

export function SpendEnrollmentChart({ chart }: { chart: SpendChart }) {
  const valued = monthsWithSpend(chart.months, chart.districts.map((district) => district.points));
  return (
    <section id="spend-over-time" className="rounded-xl border border-teal/10 bg-page p-4">
      <h2 className="font-semibold">Screened spend by month, with October 1 enrollment</h2>
      <p className="mt-1 text-base leading-6">
        A gap is a month with no indexed document. <HowToRead anchor="read-gaps" />
      </p>
      {chart.districts.length === 0 ? (
        <p className="mt-4 text-sm text-teal/70">No indexed lines have a date on this basis inside the filter.</p>
      ) : (
        <div className="mt-4 space-y-4">
          {chart.districts.map((district, index) => (
            <DistrictPanel key={district.sourceId} district={district} color={SERIES[index % SERIES.length]} />
          ))}
        </div>
      )}
      {chart.undated.length > 0 ? (
        <p className="mt-3 text-xs leading-5 text-teal/65">
          {chart.undated.map((row) => `${row.district}: ${row.lineCount.toLocaleString("en-US")} screened lines have no date on this basis and are not on the chart (${dollars(row.amountCents)}).`).join(" ")}
        </p>
      ) : null}
      <ChartTable chart={chart} months={valued} />
      {valued.length !== chart.months.length ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-semibold text-teal">Show all months, including months with no indexed document</summary>
          <ChartTable chart={chart} months={chart.months} />
        </details>
      ) : null}
    </section>
  );
}

function DistrictPanel({ district, color }: { district: DistrictSpend; color: string }) {
  const width = 760;
  const height = 280;
  const left = 92;
  const right = 108;
  const top = 36;
  const bottom = 48;
  const innerWidth = width - left - right;
  const innerHeight = height - top - bottom;
  const months = district.points.map((point) => point.month);
  const slot = innerWidth / Math.max(months.length, 1);
  const spendValues = district.points.map((point) => point.amountCents).filter((value): value is number => value != null);
  const spendTicks = axisTicks(Math.min(0, ...spendValues, 0), Math.max(...spendValues, 1), 4);
  const spendFloor = spendTicks[0] ?? 0;
  const spendCeil = spendTicks[spendTicks.length - 1] ?? 1;
  const enrollTicks = district.enrollment.length === 0 ? [] : axisTicks(0, Math.max(...district.enrollment.map((mark) => mark.headcount)), 4);
  const enrollCeil = enrollTicks[enrollTicks.length - 1] || 1;
  const ySpend = (cents: number) => top + innerHeight - ((cents - spendFloor) / Math.max(spendCeil - spendFloor, 1)) * innerHeight;
  const yEnroll = (count: number) => top + innerHeight - (count / enrollCeil) * innerHeight;
  const xCenter = (index: number) => left + index * slot + slot / 2;
  const monthIndex = new Map(months.map((month, index) => [month, index]));
  const labelStep = labelStepFor(months.length, 6);
  const labeled = monthsToLabel(district.points);
  const shortName = shortDistrict(district.district);

  return (
    <article className="overflow-x-auto rounded-lg border border-teal/10 p-3">
      <h3 className="font-semibold" style={{ color }}>{district.district}</h3>
      <p className="text-sm text-teal/70">
        <span className="mr-3 inline-flex items-center gap-1"><span className="inline-block h-2 w-5 rounded-sm" style={{ background: color }} />Screened spend</span>
        {district.enrollment.length > 0 ? (
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-0 w-5 border-t-2 border-dashed" style={{ borderColor: color }} />
            {shortName} October 1 enrollment (ADE headcount)
          </span>
        ) : (
          <span>No October 1 enrollment workbook overlaps these indexed months.</span>
        )}
      </p>
      <div className="mt-2 overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" className="district-chart">
        <title>{`${district.district} screened spend per month and October 1 enrollment`}</title>
        <text x="16" y={top + innerHeight / 2} textAnchor="middle" className="fill-teal text-[13px]" transform={`rotate(-90 16 ${top + innerHeight / 2})`}>
          {SPEND_AXIS}
        </text>
        {district.enrollment.length > 0 ? (
          <text x={width - 16} y={top + innerHeight / 2} textAnchor="middle" className="fill-teal text-[13px]" transform={`rotate(90 ${width - 16} ${top + innerHeight / 2})`}>
            {ENROLL_AXIS}
          </text>
        ) : null}
        {spendTicks.map((tick) => (
          <g key={`spend-${tick}`}>
            <line x1={left} x2={width - right} y1={ySpend(tick)} y2={ySpend(tick)} className="stroke-teal/15" />
            <text x={left - 8} y={ySpend(tick) + 4} textAnchor="end" className="fill-teal text-[13px]">{compactDollars(tick)}</text>
          </g>
        ))}
        {enrollTicks.map((tick) => (
          <text key={`enroll-${tick}`} x={width - right + 8} y={yEnroll(tick) + 4} className="fill-teal text-[13px]">
            {tick.toLocaleString("en-US")}
          </text>
        ))}
        {months.map((month, index) => index % labelStep === 0 ? (
          <text key={month} x={xCenter(index)} y={height - 14} textAnchor="middle" className="fill-teal text-[13px]">
            {formatMonth(month)}
          </text>
        ) : null)}
        {contiguousSpendSegments(district.points).map((segment) => (
          <SpendSegment
            key={segment[0]?.month}
            segment={segment}
            color={color}
            monthIndex={monthIndex}
            xCenter={xCenter}
            ySpend={ySpend}
            district={district.district}
            labeled={labeled}
            plotLeft={left}
            plotRight={width - right}
          />
        ))}
        {district.enrollment.map((mark) => (
          <EnrollmentStep
            key={mark.schoolYear}
            mark={mark}
            color={color}
            label={`${shortName} ${mark.headcount.toLocaleString("en-US")}`}
            monthIndex={monthIndex}
            slot={slot}
            xCenter={xCenter}
            y={yEnroll(mark.headcount)}
            plotLeft={left}
            plotRight={width - right}
          />
        ))}
      </svg>
      </div>
    </article>
  );
}

function SpendSegment({
  segment,
  color,
  monthIndex,
  xCenter,
  ySpend,
  district,
  labeled,
  plotLeft,
  plotRight,
}: {
  segment: SpendPoint[];
  color: string;
  monthIndex: Map<string, number>;
  xCenter: (index: number) => number;
  ySpend: (cents: number) => number;
  district: string;
  labeled: Set<string>;
  plotLeft: number;
  plotRight: number;
}) {
  const isolated = segment.length === 1;
  const path = segment.map((point, index) => {
    const at = monthIndex.get(point.month) ?? 0;
    return `${index === 0 ? "M" : "L"} ${xCenter(at).toFixed(1)} ${ySpend(point.amountCents ?? 0).toFixed(1)}`;
  }).join(" ");
  return (
    <g>
      {isolated ? null : <path d={path} fill="none" stroke={color} strokeWidth="2.5" />}
      {segment.map((point) => {
        const at = monthIndex.get(point.month) ?? 0;
        const cx = xCenter(at);
        const cy = ySpend(point.amountCents ?? 0);
        return (
          <g key={point.month}>
            <circle cx={cx} cy={cy} r={isolated ? 8 : 4} fill={color} stroke="#fbf6ec" strokeWidth={isolated ? 2 : 0}>
              <title>{`${district} ${formatMonth(point.month)}: ${dollars(point.amountCents)}`}</title>
            </circle>
            {labeled.has(point.month) ? (
              <text
                x={cx < plotLeft + 72 ? cx + 10 : cx > plotRight - 72 ? cx - 10 : cx}
                y={Math.max(cy - 16, 18)}
                textAnchor={cx < plotLeft + 72 ? "start" : cx > plotRight - 72 ? "end" : "middle"}
                className="text-[13px]"
                fill={color}
              >
                {exactDollars(point.amountCents ?? 0)}
              </text>
            ) : null}
          </g>
        );
      })}
    </g>
  );
}

function EnrollmentStep({
  mark,
  color,
  label,
  monthIndex,
  slot,
  xCenter,
  y,
  plotLeft,
  plotRight,
}: {
  mark: EnrollmentMark;
  color: string;
  label: string;
  monthIndex: Map<string, number>;
  slot: number;
  xCenter: (index: number) => number;
  y: number;
  plotLeft: number;
  plotRight: number;
}) {
  const start = monthIndex.get(mark.july);
  const end = monthIndex.get(mark.june);
  const october = monthIndex.get(mark.october);
  const x1 = start == null ? plotLeft : xCenter(start) - slot / 2;
  const x2 = end == null ? plotRight : xCenter(end) + slot / 2;
  const labelX = Math.min(x2 - 4, plotRight - 4);
  return (
    <g>
      <line x1={x1} x2={x2} y1={y} y2={y} stroke={color} strokeWidth="1.75" strokeDasharray="6 4" />
      {october == null ? null : (
        <circle cx={xCenter(october)} cy={y} r="5.5" fill="#fbf6ec" stroke={color} strokeWidth="2.5">
          <title>{`${label}. October 1 enrollment (ADE headcount, not ADM).`}</title>
        </circle>
      )}
      <text x={labelX} y={y - 8} textAnchor="end" fill={color} className="text-[13px]">
        {label}
      </text>
    </g>
  );
}

function ChartTable({ chart, months }: { chart: SpendChart; months: string[] }) {
  if (months.length === 0) return null;
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-base">
        <caption className="mb-2 text-left text-teal/80">
          A blank cell is a gap: no indexed document that month. October 1 enrollment (ADE headcount) is the school-year count, not a monthly count.
        </caption>
        <thead className="border-b border-teal/10 uppercase tracking-wide text-teal/50">
          <tr>
            <th className="py-1 pr-2">Month</th>
            {chart.districts.map((district) => (
              <th key={district.sourceId} className="py-1 pr-2">{district.district}</th>
            ))}
            {chart.districts.map((district) => (
              <th key={`${district.sourceId}-enroll`} className="py-1 pr-2">{shortDistrict(district.district)} October 1 enrollment</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {months.map((month) => (
            <tr key={month} className="border-b border-teal/5">
              <th className="py-1 pr-2 font-semibold" scope="row">{formatMonth(month)}</th>
              {chart.districts.map((district) => {
                const amount = spendAt(district.points, month);
                return <td key={district.sourceId} className="py-1 pr-2">{amount == null ? "" : dollars(amount)}</td>;
              })}
              {chart.districts.map((district) => (
                <td key={`${district.sourceId}-enroll`} className="py-1 pr-2">{enrollmentAt(district.enrollment, month)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function spendAt(points: SpendPoint[], month: string): number | null {
  const point = points.find((item) => item.month === month);
  return point ? point.amountCents : null;
}

function enrollmentAt(marks: EnrollmentMark[], month: string): string {
  const mark = marks.find((item) => month >= item.july && month <= item.june);
  if (!mark) return "";
  return mark.headcount.toLocaleString("en-US");
}

function shortDistrict(name: string): string {
  return name
    .replace(/ Unified School District.*/, "")
    .replace(/ Unified District.*/, "")
    .replace(/ School District.*/, "");
}

function exactDollars(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  return `${sign}$${Math.round(Math.abs(cents) / 100).toLocaleString("en-US")}`;
}

function compactDollars(cents: number): string {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents) / 100;
  if (abs >= 1_000_000) {
    const digits = abs >= 10_000_000 ? 1 : 2;
    return `${sign}$${(abs / 1_000_000).toFixed(digits)}M`;
  }
  if (abs >= 10_000) return `${sign}$${Math.round(abs / 1_000)}k`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(1)}k`;
  return `${sign}$${Math.round(abs)}`;
}

function formatMonth(month: string): string {
  const index = Number(month.slice(5, 7)) - 1;
  return `${MONTHS[index] ?? month} ${month.slice(2, 4)}`;
}
