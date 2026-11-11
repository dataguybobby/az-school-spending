import type { DatabaseSync } from "node:sqlite";
import { monthExpr, where, type Filters } from "@/lib/db";
import {
  groupPrintedSlices,
  printedCategoryField,
  printedFieldLabel,
  NO_CATEGORY_PRINTED,
  type PieSlice,
  type PrintedCategoryField,
  type RawSlice,
} from "@/lib/printed-slices";
import {
  axisMonths,
  enrollmentMarks,
  monthsBetween,
  spendWithGaps,
  type EnrollmentMark,
  type SpendPoint,
} from "@/lib/spend-series";

export type DistrictPie = {
  sourceId: string;
  district: string;
  field: PrintedCategoryField;
  fieldLabel: string;
  totalCents: number;
  slices: PieSlice[];
};

export type DistrictSpend = {
  sourceId: string;
  district: string;
  points: SpendPoint[];
  enrollment: EnrollmentMark[];
};

export type SpendChart = {
  months: string[];
  districts: DistrictSpend[];
  undated: Array<{ district: string; lineCount: number; amountCents: number }>;
};

type GroupRow = {
  source_id: string;
  entity_name: string;
  has_account: number;
  description_public: string | null;
  dac_raw: string | null;
  amount_cents: number;
  line_count: number;
};

export function loadDistrictPies(db: DatabaseSync, filters: Filters): DistrictPie[] {
  const filter = where(filters);
  const rows = db.prepare(
    `SELECT source_id, entity_name,
            CASE WHEN IFNULL(account_code_raw, '') <> '' THEN 1 ELSE 0 END AS has_account,
            description_public, dac_raw,
            SUM(amount_cents) AS amount_cents, COUNT(*) AS line_count
     FROM lines
     WHERE ${filter.sql}
     GROUP BY source_id, entity_name, has_account, description_public, dac_raw`,
  ).all(...filter.params) as GroupRow[];
  const bySource = new Map<string, GroupRow[]>();
  for (const row of rows) {
    const list = bySource.get(row.source_id) ?? [];
    list.push(row);
    bySource.set(row.source_id, list);
  }
  const order = new Map(
    (db.prepare("SELECT source_id, display_order FROM october1_index_leas").all() as Array<{ source_id: string; display_order: number }>).map(
      (row) => [row.source_id, row.display_order],
    ),
  );
  const pies: DistrictPie[] = [];
  for (const [sourceId, group] of bySource) {
    const hasAccount = group.some((row) => row.has_account === 1);
    const hasDac = group.some((row) => (row.dac_raw ?? "").trim() !== "");
    const field = printedCategoryField(hasAccount, hasDac);
    const combined = new Map<string, RawSlice>();
    for (const row of group) {
      const label = sliceLabel(field, row);
      const current = combined.get(label) ?? { label, amountCents: 0, lineCount: 0 };
      current.amountCents += row.amount_cents;
      current.lineCount += row.line_count;
      combined.set(label, current);
    }
    const raw = [...combined.values()];
    const totalCents = raw.reduce((sum, row) => sum + row.amountCents, 0);
    pies.push({
      sourceId,
      district: group[0]?.entity_name ?? sourceId,
      field,
      fieldLabel: printedFieldLabel(field),
      totalCents,
      slices: groupPrintedSlices(raw),
    });
  }
  pies.sort((left, right) => (order.get(left.sourceId) ?? 99) - (order.get(right.sourceId) ?? 99) || left.district.localeCompare(right.district));
  return pies;
}

function sliceLabel(field: PrintedCategoryField, row: GroupRow): string {
  switch (field) {
    case "account_description":
      return (row.description_public ?? "").trim() || NO_CATEGORY_PRINTED;
    case "dac":
      return (row.dac_raw ?? "").trim() || NO_CATEGORY_PRINTED;
    case "none":
      return NO_CATEGORY_PRINTED;
    default: {
      const unreachable: never = field;
      return unreachable;
    }
  }
}

export function loadSpendChart(db: DatabaseSync, filters: Filters): SpendChart {
  const filter = where(filters);
  const coverage = where({ basis: filters.basis, source: filters.source, start: filters.start, end: filters.end });
  const month = monthExpr(filters.basis);
  const indexed = db.prepare(
    `SELECT source_id, entity_name, ${month} AS month
     FROM lines
     WHERE ${coverage.sql} AND ${month} IS NOT NULL AND ${month} <> ''
     GROUP BY source_id, entity_name, month`,
  ).all(...coverage.params) as Array<{ source_id: string; entity_name: string; month: string }>;
  const sums = db.prepare(
    `SELECT source_id, entity_name, ${month} AS month, SUM(amount_cents) AS amount_cents
     FROM lines
     WHERE ${filter.sql} AND ${month} IS NOT NULL AND ${month} <> ''
     GROUP BY source_id, entity_name, month`,
  ).all(...filter.params) as Array<{ source_id: string; entity_name: string; month: string; amount_cents: number }>;
  const tx = filters.basis === "check_date"
    ? "check_date"
    : filters.basis === "voucher_batch_date"
      ? "voucher_batch_date"
      : "COALESCE(check_date, voucher_batch_date)";
  const undated = db.prepare(
    `SELECT entity_name, COUNT(*) AS line_count, SUM(amount_cents) AS amount_cents
     FROM lines
     WHERE ${filter.sql} AND ${tx} IS NULL
     GROUP BY entity_name
     ORDER BY entity_name`,
  ).all(...filter.params) as Array<{ entity_name: string; line_count: number; amount_cents: number }>;
  const byDistrict = new Map<string, { sourceId: string; district: string; indexed: string[]; sums: Map<string, number> }>();
  for (const row of indexed) {
    const current = byDistrict.get(row.source_id) ?? {
      sourceId: row.source_id,
      district: row.entity_name,
      indexed: [],
      sums: new Map<string, number>(),
    };
    current.indexed.push(row.month);
    byDistrict.set(row.source_id, current);
  }
  for (const row of sums) {
    const current = byDistrict.get(row.source_id);
    if (!current) continue;
    current.sums.set(row.month, row.amount_cents);
  }
  const enrollmentBySource = loadEnrollmentMarks(db);
  const districts: DistrictSpend[] = [...byDistrict.values()].map((district) => {
    const marks = (enrollmentBySource.get(district.sourceId) ?? []).filter((mark) =>
      district.indexed.some((month) => month >= mark.july && month <= mark.june),
    );
    const months = axisMonths(district.indexed, marks);
    return {
      sourceId: district.sourceId,
      district: district.district,
      points: spendWithGaps(district.indexed, district.sums, months),
      enrollment: marks,
    };
  });
  const order = new Map(
    (db.prepare("SELECT source_id, display_order FROM october1_index_leas").all() as Array<{ source_id: string; display_order: number }>).map(
      (row) => [row.source_id, row.display_order],
    ),
  );
  districts.sort((left, right) => (order.get(left.sourceId) ?? 99) - (order.get(right.sourceId) ?? 99) || left.district.localeCompare(right.district));
  const covered = districts.flatMap((district) => district.points.map((point) => point.month)).sort();
  const months = covered.length === 0 ? [] : monthsBetween(covered[0], covered[covered.length - 1]);
  return {
    months,
    districts,
    undated: undated.map((row) => ({ district: row.entity_name, lineCount: row.line_count, amountCents: row.amount_cents })),
  };
}

function loadEnrollmentMarks(db: DatabaseSync): Map<string, EnrollmentMark[]> {
  const workbooks = new Set(
    (db.prepare("SELECT school_year FROM october1_workbooks").all() as Array<{ school_year: string }>).map((row) => row.school_year),
  );
  const rows = db.prepare(
    `SELECT i.source_id, e.school_year,
            COUNT(*) AS row_count,
            CASE WHEN COUNT(*) = 1 THEN MIN(e.total_oct1_enrollment) ELSE NULL END AS total_oct1_enrollment,
            MAX(e.same_basis_as_2017_18_plus) AS same_basis_as_2017_18_plus
     FROM october1_index_leas i
     JOIN october1_enrollment e ON e.lea_entity_id = i.lea_entity_id
     GROUP BY i.source_id, e.school_year`,
  ).all() as Array<{
    source_id: string;
    school_year: string;
    total_oct1_enrollment: number | null;
    same_basis_as_2017_18_plus: number;
    row_count: number;
  }>;
  const grouped = new Map<string, EnrollmentMark[]>();
  const bySource = new Map<string, typeof rows>();
  for (const row of rows) {
    const list = bySource.get(row.source_id) ?? [];
    list.push(row);
    bySource.set(row.source_id, list);
  }
  for (const [sourceId, sourceRows] of bySource) {
    grouped.set(sourceId, enrollmentMarks(sourceRows.map((row) => ({
      schoolYear: row.school_year,
      headcount: row.total_oct1_enrollment,
      sameBasis: row.same_basis_as_2017_18_plus === 1,
      workbookLoaded: workbooks.has(row.school_year),
      rowCount: row.row_count,
    }))));
  }
  return grouped;
}
