export const NO_CATEGORY_PRINTED = "No category printed";
export const OTHER_AS_PRINTED = "Other (as printed)";
export const SMALL_SLICE_SHARE = 0.02;

export type PrintedCategoryField = "account_description" | "dac" | "none";

export type RawSlice = {
  label: string;
  amountCents: number;
  lineCount: number;
};

export type PieSlice = {
  label: string;
  amountCents: number;
  lineCount: number;
  share: number | null;
  members: RawSlice[];
};

export function printedCategoryField(hasAccountCode: boolean, hasDac: boolean): PrintedCategoryField {
  if (hasAccountCode) return "account_description";
  if (hasDac) return "dac";
  return "none";
}

export function printedFieldLabel(field: PrintedCategoryField): string {
  switch (field) {
    case "account_description":
      return "Account description as printed";
    case "dac":
      return "DAC as printed";
    case "none":
      return NO_CATEGORY_PRINTED;
    default: {
      const unreachable: never = field;
      return unreachable;
    }
  }
}

export function groupPrintedSlices(rows: RawSlice[]): PieSlice[] {
  const total = rows.reduce((sum, row) => sum + row.amountCents, 0);
  const absTotal = rows.reduce((sum, row) => sum + Math.abs(row.amountCents), 0);
  const named: RawSlice[] = [];
  let missing: RawSlice | null = null;
  for (const row of rows) {
    const label = row.label.trim() === "" ? NO_CATEGORY_PRINTED : row.label;
    if (label === NO_CATEGORY_PRINTED) {
      missing = missing
        ? { label, amountCents: missing.amountCents + row.amountCents, lineCount: missing.lineCount + row.lineCount }
        : { label, amountCents: row.amountCents, lineCount: row.lineCount };
      continue;
    }
    named.push({ label, amountCents: row.amountCents, lineCount: row.lineCount });
  }
  const kept: RawSlice[] = [];
  const small: RawSlice[] = [];
  for (const row of named) {
    const tiny = absTotal > 0 && Math.abs(row.amountCents) / absTotal < SMALL_SLICE_SHARE;
    if (tiny) small.push(row);
    else kept.push(row);
  }
  kept.sort((left, right) => right.amountCents - left.amountCents || left.label.localeCompare(right.label));
  const slices: PieSlice[] = kept.map((row) => toSlice(row, total, [row]));
  if (missing) slices.push(toSlice(missing, total, [missing]));
  if (small.length > 0) {
    small.sort((left, right) => right.amountCents - left.amountCents || left.label.localeCompare(right.label));
    const other = small.reduce(
      (sum, row) => ({
        label: OTHER_AS_PRINTED,
        amountCents: sum.amountCents + row.amountCents,
        lineCount: sum.lineCount + row.lineCount,
      }),
      { label: OTHER_AS_PRINTED, amountCents: 0, lineCount: 0 },
    );
    slices.push(toSlice(other, total, small));
  }
  return slices;
}

function toSlice(row: RawSlice, total: number, members: RawSlice[]): PieSlice {
  return {
    label: row.label,
    amountCents: row.amountCents,
    lineCount: row.lineCount,
    share: total === 0 ? null : row.amountCents / total,
    members,
  };
}

export function formatShare(share: number | null): string {
  if (share == null || Number.isNaN(share)) return "";
  return `${(share * 100).toFixed(1)}%`;
}
