export function basisLabel(basis: string | undefined): string {
  if (basis === "check_date") return "check date on the AP row";
  if (basis === "voucher_batch_date") return "voucher batch date (not a check date)";
  return "check date when present, otherwise voucher batch date";
}

export function withBasis(path: string, basis: string | undefined): string {
  if (!basis || basis === "either") return path;
  return `${path}?basis=${encodeURIComponent(basis)}`;
}
