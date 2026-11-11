import type { DatabaseSync } from "node:sqlite";
import { dateBasis, where, type DateBasis, type Filters } from "@/lib/db";
import {
  october1Date,
  reportedCentsPerEnrolledStudent,
  spendingWindow,
  type ComparisonStatus,
  PER_STUDENT_LABEL,
} from "@/lib/enrollment-match";

export type { ComparisonStatus } from "@/lib/enrollment-match";
export { PER_STUDENT_LABEL } from "@/lib/enrollment-match";

const SCHOOL_YEAR_CASE = `CASE
    WHEN substr(tx_date, 6, 5) >= '07-01'
      THEN substr(tx_date, 1, 4) || '-' || (CAST(substr(tx_date, 1, 4) AS INTEGER) + 1)
    ELSE (CAST(substr(tx_date, 1, 4) AS INTEGER) - 1) || '-' || substr(tx_date, 1, 4)
  END`;

export type ComparisonRecord = {
  sourceId: string;
  district: string;
  leaEntityId: string | null;
  dateBasis: DateBasis;
  schoolYear: string | null;
  october1Date: string | null;
  spendingWindowStart: string | null;
  spendingWindowEnd: string | null;
  october1Enrollment: number | null;
  enrollmentAsPrinted: string | null;
  enrollmentNullReason: string | null;
  screenedLineCount: number;
  screenedAmountCents: number | null;
  spendingFirstDate: string | null;
  spendingLastDate: string | null;
  reportedCentsPerEnrolledStudent: number | null;
  status: ComparisonStatus;
  label: string;
  officialSourceUrl: string | null;
  sourceSha256: string | null;
};

export type FocusEnrollment = {
  focusDistrict: string;
  schoolYear: string;
  leaName: string;
  leaEntityId: string;
  october1Enrollment: number | null;
  totalAsPrinted: string;
  suppressionOrNullReason: string | null;
  focusNote: string;
  sameBasis: boolean;
  leaIdMatches: boolean;
  seriesBasis: string;
};

export type WorkbookEnrollment = {
  schoolYear: string;
  sha256: string;
  officialSourceUrl: string;
  spendingWindowStart: string;
  spendingWindowEnd: string;
  sameBasis: boolean;
  statewideTotal: number | null;
  statewideTotalAsPrinted: string | null;
  statewideNullReason: string | null;
  labelEvidence: string;
};

type SpendGroup = {
  source_id: string;
  entity_name: string;
  school_year: string | null;
  amount_cents: number;
  line_count: number;
  first_date: string | null;
  last_date: string | null;
};

type IndexLea = {
  source_id: string;
  entity_name: string;
  lea_entity_id: string;
  display_order: number;
};

type EnrollmentHit = {
  total_oct1_enrollment: number | null;
  total_as_printed: string;
  suppression_or_null_reason: string | null;
};

type WorkbookHit = {
  school_year: string;
  official_source_url: string;
  sha256: string;
};

function txExpr(basis: DateBasis): string {
  switch (basis) {
    case "check_date":
      return "check_date";
    case "voucher_batch_date":
      return "voucher_batch_date";
    case "either":
      return "COALESCE(check_date, voucher_batch_date)";
    default: {
      const unreachable: never = basis;
      return unreachable;
    }
  }
}

export function hasNarrowingFilter(filters: Filters): boolean {
  return Boolean(
    filters.q || filters.vendor || filters.category || filters.confidence || filters.dac || filters.account || filters.start || filters.end,
  );
}

export function loadComparisons(db: DatabaseSync, filters: Filters): ComparisonRecord[] {
  const basis = dateBasis(filters.basis);
  const leas = db.prepare(
    "SELECT source_id, entity_name, lea_entity_id, display_order FROM october1_index_leas ORDER BY display_order",
  ).all() as IndexLea[];
  const workbooks = new Map(
    (db.prepare("SELECT school_year, official_source_url, sha256 FROM october1_workbooks").all() as WorkbookHit[]).map(
      (row) => [row.school_year, row],
    ),
  );
  const visible = filters.source ? leas.filter((lea) => lea.source_id === filters.source) : leas;
  if (!hasNarrowingFilter(filters)) {
    return comparisonsFromViews(db, basis, visible, leas, workbooks, filters.source);
  }
  return comparisonsFromFilter(db, filters, basis, visible, workbooks);
}

function comparisonsFromViews(
  db: DatabaseSync,
  basis: DateBasis,
  visible: IndexLea[],
  allLeas: IndexLea[],
  workbooks: Map<string, WorkbookHit>,
  sourceFilter: string | undefined,
): ComparisonRecord[] {
  const dated = db.prepare(
    `SELECT source_id, entity_name, school_year, amount_cents, line_count, first_date, last_date
     FROM october1_screened_by_school_year WHERE date_basis = ?`,
  ).all(basis) as SpendGroup[];
  const undated = new Map(
    (db.prepare(
      "SELECT source_id, entity_name, line_count, amount_cents FROM october1_screened_undated WHERE date_basis = ?",
    ).all(basis) as Array<{ source_id: string; entity_name: string; line_count: number; amount_cents: number }>).map(
      (row) => [row.source_id, row],
    ),
  );
  const linked = new Set(allLeas.map((lea) => lea.source_id));
  const records: ComparisonRecord[] = [];
  for (const lea of visible) {
    const ownDated = dated
      .filter((row) => row.source_id === lea.source_id)
      .sort((left, right) => String(left.school_year).localeCompare(String(right.school_year)));
    const screened = db.prepare(
      "SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents), 0) AS cents FROM lines WHERE source_id = ? AND in_default_aggregate = 1",
    ).get(lea.source_id) as { n: number; cents: number };
    if (screened.n === 0) {
      records.push(record({
        lea,
        basis,
        status: "not_in_spending_index",
        reason: "This district is not in the spending index. An unindexed file is not zero spending.",
        lineCount: 0,
        amountCents: null,
      }));
      continue;
    }
    if (ownDated.length === 0) {
      const missing = undated.get(lea.source_id);
      records.push(record({
        lea,
        basis,
        status: "no_dated_spending",
        reason: "No date is stored on this basis, so no school year is assigned. The native fiscal-year label is not used.",
        lineCount: missing?.line_count ?? screened.n,
        amountCents: missing?.amount_cents ?? screened.cents,
      }));
      continue;
    }
    for (const row of ownDated) {
      records.push(datedRecord(db, lea, basis, row, workbooks));
    }
    const missing = undated.get(lea.source_id);
    if (missing && missing.line_count > 0) {
      records.push(record({
        lea,
        basis,
        status: "no_dated_spending",
        reason: "These screened lines have no date on this basis and are not assigned to a school year.",
        lineCount: missing.line_count,
        amountCents: missing.amount_cents,
      }));
    }
  }
  const extras = [...new Set(dated.map((row) => row.source_id).filter((sourceId) => !linked.has(sourceId) && (!sourceFilter || sourceId === sourceFilter)))].sort();
  for (const sourceId of extras) {
    for (const row of dated.filter((item) => item.source_id === sourceId)) {
      records.push(record({
        lea: { source_id: sourceId, entity_name: row.entity_name, lea_entity_id: "", display_order: 0 },
        basis,
        schoolYear: row.school_year,
        status: "no_lea_link",
        reason: "No ADE entity id is linked for this source. Enrollment is not guessed from the name.",
        lineCount: row.line_count,
        amountCents: row.amount_cents,
        firstDate: row.first_date,
        lastDate: row.last_date,
        leaEntityId: null,
      }));
    }
  }
  return records;
}

function comparisonsFromFilter(
  db: DatabaseSync,
  filters: Filters,
  basis: DateBasis,
  leas: IndexLea[],
  workbooks: Map<string, WorkbookHit>,
): ComparisonRecord[] {
  const filter = where(filters);
  const grouped = db.prepare(
    `SELECT source_id, entity_name, school_year, SUM(amount_cents) AS amount_cents, COUNT(*) AS line_count,
            MIN(tx_date) AS first_date, MAX(tx_date) AS last_date
     FROM (
       SELECT source_id, entity_name, amount_cents, tx_date, ${SCHOOL_YEAR_CASE} AS school_year
       FROM (
         SELECT source_id, entity_name, amount_cents, ${txExpr(basis)} AS tx_date
         FROM lines
         WHERE ${filter.sql}
       )
     )
     GROUP BY source_id, entity_name, school_year
     ORDER BY entity_name, school_year`,
  ).all(...filter.params) as SpendGroup[];
  const bySource = new Map<string, SpendGroup[]>();
  for (const row of grouped) {
    const list = bySource.get(row.source_id) ?? [];
    list.push(row);
    bySource.set(row.source_id, list);
  }
  const records: ComparisonRecord[] = [];
  const seen = new Set<string>();
  for (const lea of leas) {
    seen.add(lea.source_id);
    for (const row of bySource.get(lea.source_id) ?? []) {
      if (row.school_year == null) {
        records.push(record({
          lea,
          basis,
          status: "no_dated_spending",
          reason: "These screened lines have no date on this basis and are not assigned to a school year.",
          lineCount: row.line_count,
          amountCents: row.amount_cents,
        }));
        continue;
      }
      records.push(datedRecord(db, lea, basis, row, workbooks));
    }
  }
  for (const [sourceId, rows] of bySource) {
    if (seen.has(sourceId)) continue;
    for (const row of rows) {
      records.push(record({
        lea: { source_id: sourceId, entity_name: row.entity_name, lea_entity_id: "", display_order: 0 },
        basis,
        schoolYear: row.school_year,
        status: row.school_year == null ? "no_dated_spending" : "no_lea_link",
        reason: row.school_year == null
          ? "These screened lines have no date on this basis and are not assigned to a school year."
          : "No ADE entity id is linked for this source. Enrollment is not guessed from the name.",
        lineCount: row.line_count,
        amountCents: row.amount_cents,
        firstDate: row.first_date,
        lastDate: row.last_date,
        leaEntityId: null,
      }));
    }
  }
  return records;
}

function datedRecord(
  db: DatabaseSync,
  lea: IndexLea,
  basis: DateBasis,
  row: SpendGroup,
  workbooks: Map<string, WorkbookHit>,
): ComparisonRecord {
  const schoolYear = String(row.school_year);
  const classified = classifyYear(db, lea.lea_entity_id, schoolYear, workbooks.has(schoolYear));
  const workbook = workbooks.get(schoolYear);
  return record({
    lea,
    basis,
    schoolYear,
    status: classified.status,
    reason: classified.reason,
    enrollment: classified.enrollment,
    printed: classified.printed,
    lineCount: row.line_count,
    amountCents: row.amount_cents,
    firstDate: row.first_date,
    lastDate: row.last_date,
    officialSourceUrl: classified.status === "no_enrollment_workbook" ? null : workbook?.official_source_url ?? null,
    sourceSha256: classified.status === "no_enrollment_workbook" ? null : workbook?.sha256 ?? null,
  });
}

function classifyYear(
  db: DatabaseSync,
  leaEntityId: string,
  schoolYear: string,
  workbookLoaded: boolean,
): { status: ComparisonStatus; enrollment: number | null; printed: string | null; reason: string | null } {
  const start = Number(schoolYear.slice(0, 4));
  if (start < 2017) {
    const rows = enrollmentHits(db, leaEntityId, schoolYear, 0);
    return {
      status: "not_comparable_basis",
      enrollment: rows.length === 1 ? rows[0].total_oct1_enrollment : null,
      printed: rows.length === 1 ? rows[0].total_as_printed : null,
      reason: "This October 1 file is not the 2017-2018 and later LEA-of-enrollment basis. It is not used as a denominator.",
    };
  }
  if (!workbookLoaded) {
    return {
      status: "no_enrollment_workbook",
      enrollment: null,
      printed: null,
      reason: `No October 1 enrollment workbook is loaded for school year ${schoolYear}.`,
    };
  }
  const rows = enrollmentHits(db, leaEntityId, schoolYear, 1);
  if (rows.length === 0) {
    return {
      status: "lea_not_in_workbook",
      enrollment: null,
      printed: null,
      reason: "This entity id is not in the October 1 workbook for that school year.",
    };
  }
  if (rows.length > 1) {
    return {
      status: "multiple_official_rows",
      enrollment: null,
      printed: null,
      reason: "More than one official total is printed for this LEA and year. Those rows are not summed.",
    };
  }
  const hit = rows[0];
  if (hit.total_oct1_enrollment == null) {
    return {
      status: "suppressed_enrollment",
      enrollment: null,
      printed: hit.total_as_printed,
      reason: hit.suppression_or_null_reason,
    };
  }
  if (hit.total_oct1_enrollment <= 0) {
    return {
      status: "no_positive_enrollment",
      enrollment: hit.total_oct1_enrollment,
      printed: hit.total_as_printed,
      reason: "The printed October 1 total is not a positive headcount, so it is not used as a denominator.",
    };
  }
  return {
    status: "reported_per_enrolled_student",
    enrollment: hit.total_oct1_enrollment,
    printed: hit.total_as_printed,
    reason: null,
  };
}

function enrollmentHits(db: DatabaseSync, leaEntityId: string, schoolYear: string, sameBasis: number): EnrollmentHit[] {
  return db.prepare(
    `SELECT total_oct1_enrollment, total_as_printed, suppression_or_null_reason
     FROM october1_enrollment
     WHERE lea_entity_id = ? AND school_year = ? AND same_basis_as_2017_18_plus = ?
     ORDER BY source_row`,
  ).all(leaEntityId, schoolYear, sameBasis) as EnrollmentHit[];
}

function record(input: {
  lea: IndexLea;
  basis: DateBasis;
  status: ComparisonStatus;
  reason: string | null;
  lineCount: number;
  amountCents: number | null;
  schoolYear?: string | null;
  enrollment?: number | null;
  printed?: string | null;
  firstDate?: string | null;
  lastDate?: string | null;
  officialSourceUrl?: string | null;
  sourceSha256?: string | null;
  leaEntityId?: string | null;
}): ComparisonRecord {
  const schoolYear = input.schoolYear ?? null;
  const enrollment = input.enrollment ?? null;
  const window = schoolYear ? spendingWindow(schoolYear) : null;
  const perStudent = input.status === "reported_per_enrolled_student" && enrollment != null && input.amountCents != null
    ? reportedCentsPerEnrolledStudent(input.amountCents, enrollment)
    : null;
  return {
    sourceId: input.lea.source_id,
    district: input.lea.entity_name,
    leaEntityId: input.leaEntityId === undefined ? input.lea.lea_entity_id : input.leaEntityId,
    dateBasis: input.basis,
    schoolYear,
    october1Date: schoolYear ? october1Date(schoolYear) : null,
    spendingWindowStart: window?.start ?? null,
    spendingWindowEnd: window?.end ?? null,
    october1Enrollment: enrollment,
    enrollmentAsPrinted: input.printed ?? null,
    enrollmentNullReason: input.reason,
    screenedLineCount: input.lineCount,
    screenedAmountCents: input.amountCents,
    spendingFirstDate: input.firstDate ?? null,
    spendingLastDate: input.lastDate ?? null,
    reportedCentsPerEnrolledStudent: perStudent,
    status: input.status,
    label: PER_STUDENT_LABEL,
    officialSourceUrl: input.officialSourceUrl ?? null,
    sourceSha256: input.sourceSha256 ?? null,
  };
}

export function loadFocusEnrollment(db: DatabaseSync): FocusEnrollment[] {
  return (db.prepare(
    `SELECT focus_district, school_year, lea_name, lea_entity_id, total_oct1_enrollment, total_as_printed,
            suppression_or_null_reason, focus_note, same_basis_as_2017_18_plus, lea_id_matches_known_entity_id, series_basis
     FROM october1_focus
     ORDER BY school_year, focus_district, lea_entity_id, source_row`,
  ).all() as Array<Record<string, string | number | null>>).map((row) => ({
    focusDistrict: String(row.focus_district),
    schoolYear: String(row.school_year),
    leaName: String(row.lea_name),
    leaEntityId: String(row.lea_entity_id),
    october1Enrollment: row.total_oct1_enrollment == null ? null : Number(row.total_oct1_enrollment),
    totalAsPrinted: String(row.total_as_printed),
    suppressionOrNullReason: row.suppression_or_null_reason == null ? null : String(row.suppression_or_null_reason),
    focusNote: String(row.focus_note),
    sameBasis: Number(row.same_basis_as_2017_18_plus) === 1,
    leaIdMatches: Number(row.lea_id_matches_known_entity_id) === 1,
    seriesBasis: String(row.series_basis),
  }));
}

export function loadWorkbooks(db: DatabaseSync): WorkbookEnrollment[] {
  return (db.prepare(
    `SELECT school_year, sha256, official_source_url, spending_window_start, spending_window_end,
            same_basis_as_2017_18_plus, statewide_total, statewide_total_as_printed, statewide_null_reason,
            school_year_label_evidence
     FROM october1_workbooks ORDER BY school_year`,
  ).all() as Array<Record<string, string | number | null>>).map((row) => ({
    schoolYear: String(row.school_year),
    sha256: String(row.sha256),
    officialSourceUrl: String(row.official_source_url),
    spendingWindowStart: String(row.spending_window_start),
    spendingWindowEnd: String(row.spending_window_end),
    sameBasis: Number(row.same_basis_as_2017_18_plus) === 1,
    statewideTotal: row.statewide_total == null ? null : Number(row.statewide_total),
    statewideTotalAsPrinted: row.statewide_total_as_printed == null ? null : String(row.statewide_total_as_printed),
    statewideNullReason: row.statewide_null_reason == null ? null : String(row.statewide_null_reason),
    labelEvidence: String(row.school_year_label_evidence),
  }));
}

export function loadUnmatchedCharters(db: DatabaseSync): string[] {
  return (db.prepare(
    "SELECT charter_name FROM october1_unmatched_charters ORDER BY display_order, charter_name",
  ).all() as Array<{ charter_name: string }>).map((row) => row.charter_name);
}
