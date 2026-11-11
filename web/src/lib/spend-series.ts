export type SpendPoint = {
  month: string;
  amountCents: number | null;
};

export type EnrollmentMark = {
  schoolYear: string;
  headcount: number;
  july: string;
  october: string;
  june: string;
};

export type EnrollmentInput = {
  schoolYear: string;
  headcount: number | null;
  sameBasis: boolean;
  workbookLoaded: boolean;
  rowCount: number;
};

export function schoolYearForMonth(month: string): string {
  const year = Number(month.slice(0, 4));
  if (month.slice(5, 7) >= "07") return `${year}-${year + 1}`;
  return `${year - 1}-${year}`;
}

export function addMonths(month: string, count: number): string {
  const year = Number(month.slice(0, 4));
  const monthIndex = Number(month.slice(5, 7)) - 1 + count;
  const nextYear = year + Math.floor(monthIndex / 12);
  const nextMonth = ((monthIndex % 12) + 12) % 12;
  return `${String(nextYear).padStart(4, "0")}-${String(nextMonth + 1).padStart(2, "0")}`;
}

export function monthsBetween(start: string, end: string): string[] {
  if (start > end) return [];
  const months: string[] = [];
  let cursor = start;
  while (cursor <= end) {
    months.push(cursor);
    cursor = addMonths(cursor, 1);
  }
  return months;
}

export function spendWithGaps(indexedMonths: string[], sums: Map<string, number>, axis: string[]): SpendPoint[] {
  const indexed = new Set(indexedMonths);
  return axis.map((month) => ({
    month,
    amountCents: indexed.has(month) ? (sums.get(month) ?? 0) : null,
  }));
}

export function enrollmentMarks(rows: EnrollmentInput[]): EnrollmentMark[] {
  const marks: EnrollmentMark[] = [];
  for (const row of rows) {
    const start = Number(row.schoolYear.slice(0, 4));
    if (!row.sameBasis || start < 2017) continue;
    if (!row.workbookLoaded || row.rowCount !== 1) continue;
    if (row.headcount == null || row.headcount <= 0) continue;
    const end = String(start + 1).padStart(4, "0");
    marks.push({
      schoolYear: row.schoolYear,
      headcount: row.headcount,
      july: `${row.schoolYear.slice(0, 4)}-07`,
      october: `${row.schoolYear.slice(0, 4)}-10`,
      june: `${end}-06`,
    });
  }
  return marks.sort((left, right) => left.july.localeCompare(right.july) || left.schoolYear.localeCompare(right.schoolYear));
}

export function axisMonths(indexedMonths: string[], marks: EnrollmentMark[]): string[] {
  const bounds = [...indexedMonths];
  for (const mark of marks) {
    const overlaps = indexedMonths.some((month) => month >= mark.july && month <= mark.june);
    if (!overlaps) continue;
    bounds.push(mark.july, mark.october, mark.june);
  }
  if (bounds.length === 0) return [];
  const sorted = [...bounds].sort();
  return monthsBetween(sorted[0], sorted[sorted.length - 1]);
}

export function contiguousSpendSegments(points: SpendPoint[]): SpendPoint[][] {
  const segments: SpendPoint[][] = [];
  let current: SpendPoint[] = [];
  for (const point of points) {
    if (point.amountCents == null) {
      if (current.length > 0) segments.push(current);
      current = [];
      continue;
    }
    current.push(point);
  }
  if (current.length > 0) segments.push(current);
  return segments;
}
