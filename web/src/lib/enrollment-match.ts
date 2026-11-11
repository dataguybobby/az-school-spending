export type ComparisonStatus =
  | "reported_per_enrolled_student"
  | "no_enrollment_workbook"
  | "suppressed_enrollment"
  | "no_dated_spending"
  | "not_in_spending_index"
  | "multiple_official_rows"
  | "not_comparable_basis"
  | "no_lea_link"
  | "lea_not_in_workbook"
  | "no_positive_enrollment";

export const PER_STUDENT_LABEL = "reported amount in this index per enrolled student";

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

export function schoolYearForDate(isoDate: string): string {
  const year = Number(isoDate.slice(0, 4));
  if (isoDate.slice(5) >= "07-01") return `${year}-${year + 1}`;
  return `${year - 1}-${year}`;
}

export function spendingWindow(schoolYear: string): { start: string; end: string } {
  const start = Number(schoolYear.slice(0, 4));
  return { start: `${start}-07-01`, end: `${start + 1}-06-30` };
}

export function october1Date(schoolYear: string): string {
  return `${schoolYear.slice(0, 4)}-10-01`;
}

export function reportedCentsPerEnrolledStudent(amountCents: number, enrollment: number): number | null {
  if (!Number.isInteger(amountCents) || !Number.isInteger(enrollment) || enrollment <= 0) return null;
  const sign = amountCents < 0 ? -1 : 1;
  const rounded = Math.floor((Math.abs(amountCents) + Math.floor(enrollment / 2)) / enrollment);
  return sign * rounded;
}

export function formatIsoDate(isoDate: string): string {
  const year = Number(isoDate.slice(0, 4));
  const month = Number(isoDate.slice(5, 7));
  const day = Number(isoDate.slice(8, 10));
  return `${MONTHS[month - 1]} ${day}, ${year}`;
}

export function formatHeadcount(value: number | null): string {
  if (value == null) return "Not published";
  return value.toLocaleString("en-US");
}
