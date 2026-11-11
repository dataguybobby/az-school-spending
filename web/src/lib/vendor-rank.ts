export type VendorSort = "amount" | "lines" | "districts" | "vendor" | "first" | "last";
export type SortDirection = "asc" | "desc";
export type DateBasis = "check_date" | "voucher_batch_date" | "either";

export type DistrictPay = {
  district: string;
  amountCents: number;
  lineCount: number;
  firstDate: string | null;
  lastDate: string | null;
};

export type VendorRank = {
  vendorKey: string;
  printedName: string;
  otherPrintedNames: string[];
  amountCents: number;
  lineCount: number;
  districtCount: number;
  firstDate: string | null;
  lastDate: string | null;
  districts: DistrictPay[];
};

export function vendorSort(value: string | undefined): VendorSort {
  switch (value) {
    case "lines":
    case "districts":
    case "vendor":
    case "first":
    case "last":
    case "amount":
      return value;
    default:
      return "amount";
  }
}

export function sortDirection(value: string | undefined): SortDirection {
  return value === "asc" ? "asc" : "desc";
}

export function dateExpr(basis: DateBasis): string {
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

export function pickPrintedName(forms: Array<{ name: string; lines: number }>): { printed: string; others: string[] } {
  const sorted = [...forms].sort((left, right) => right.lines - left.lines || right.name.length - left.name.length || left.name.localeCompare(right.name));
  return {
    printed: sorted[0]?.name ?? "",
    others: sorted.slice(1).map((form) => form.name),
  };
}

export function vendorOrder(sort: VendorSort, direction: SortDirection): (left: VendorRank, right: VendorRank) => number {
  const sign = direction === "asc" ? 1 : -1;
  return (left, right) => {
    const compared = compareVendor(left, right, sort);
    if (compared !== 0) return compared * sign;
    return left.vendorKey.localeCompare(right.vendorKey);
  };
}

function compareVendor(left: VendorRank, right: VendorRank, sort: VendorSort): number {
  switch (sort) {
    case "amount":
      return left.amountCents - right.amountCents;
    case "lines":
      return left.lineCount - right.lineCount;
    case "districts":
      return left.districtCount - right.districtCount;
    case "vendor":
      return left.printedName.localeCompare(right.printedName);
    case "first":
      return compareDate(left.firstDate, right.firstDate);
    case "last":
      return compareDate(left.lastDate, right.lastDate);
    default: {
      const unreachable: never = sort;
      return unreachable;
    }
  }
}

function compareDate(left: string | null, right: string | null): number {
  if (left == null && right == null) return 0;
  if (left == null) return 1;
  if (right == null) return -1;
  return left.localeCompare(right);
}
