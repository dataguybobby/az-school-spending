"""Exact decimal-to-cents conversion. Floats are not used for amounts."""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

_TOKEN = re.compile(r"-?\(?\$?\(?-?\$?\d{1,3}(?:,\d{3})*\.\d{2}\)?\)?")


def parse_cents(raw: str | None) -> int | None:
    """Parse one printed dollar amount to signed integer cents.

    Accepts ``$1,110.24``, ``76,386.44``, ``($4.24)``, and ``-($122.36)``.
    Returns None when the text is not a single money amount. Dollar signs and
    spaces that printers insert between the symbol and the digits are ignored.
    """
    if raw is None:
        return None
    compact = raw.strip().replace(" ", "")
    if not compact or compact == "$":
        return None
    if compact.startswith("$"):
        compact = compact[1:]
    match = _TOKEN.fullmatch(compact if compact.startswith(("-", "(")) else compact)
    if match is None:
        # Column text may be "$" plus a number that was concatenated.
        found = _TOKEN.fullmatch(compact)
        if found is None:
            return None
    negative = False
    cleaned = compact.replace("$", "").replace(",", "")
    if cleaned.startswith("-"):
        negative = True
        cleaned = cleaned[1:]
    while cleaned.startswith("(") and cleaned.endswith(")"):
        negative = True
        cleaned = cleaned[1:-1]
    if cleaned.startswith("$"):
        cleaned = cleaned[1:]
    if not re.fullmatch(r"\d+\.\d{2}", cleaned):
        return None
    cents = int((Decimal(cleaned) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return -cents if negative else cents


def cents_to_decimal(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    value = abs(int(cents))
    return f"{sign}{value // 100}.{value % 100:02d}"
