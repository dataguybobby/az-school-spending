"""Item phrases resolved from public description text.

Groups are not budget codes and not official categories. A match is a reviewed
phrase, with the matched span kept as evidence. Broad tokens such as "ball"
are not rules. Dollar figures printed as not-to-exceed ceilings are not spend.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_PHRASES: tuple[tuple[str, float, re.Pattern[str]], ...] = (
    ("stress balls", 0.86, re.compile(r"stress\s+balls?", re.I)),
)

_CEILING = re.compile(
    r"\b(?:not\s+to\s+exceed|n\.?t\.?e\.?|nte)\b[^$\n]{0,40}\$\s*\d",
    re.I,
)


def load_item_overrides(path: Path | None) -> dict[str, dict[str, object]]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    found: dict[str, dict[str, object]] = {}
    for row in payload.get("overrides", []):
        key = str(row.get("line_id") or "")
        if key:
            found[key] = row
    return found


def resolve_item(description: str | None, line_id: str, overrides: dict[str, dict[str, object]] | None = None) -> dict[str, object]:
    """Return the public item fields for one line. Amounts are not parsed here."""
    override = (overrides or {}).get(line_id)
    if override:
        return {
            "item_label": str(override["label"]),
            "item_evidence": str(override.get("evidence") or "manual override"),
            "item_method": "manual_override",
            "item_confidence": float(override.get("confidence", 1)),
        }
    text = re.sub(r"\s+", " ", description or "").strip()
    for label, confidence, pattern in _PHRASES:
        match = pattern.search(text)
        if match is None:
            continue
        return {
            "item_label": label,
            "item_evidence": match.group(0),
            "item_method": "description_phrase",
            "item_confidence": confidence,
        }
    return {
        "item_label": None,
        "item_evidence": None,
        "item_method": None,
        "item_confidence": None,
    }


def group_amount_cents(rows: list[dict[str, object]]) -> int:
    """Sum stored line amounts. Ceiling text in a description is not an amount."""
    return sum(int(row["amount_cents"]) for row in rows)


def ceiling_mention(description: str | None) -> bool:
    return bool(_CEILING.search(description or ""))


def choose_vendor_display(forms: list[tuple[str, int]]) -> str:
    """Prefer the raw vendor string that appears most often, then the longer one."""
    if not forms:
        return ""
    ranked = sorted(forms, key=lambda item: (-item[1], -len(item[0]), item[0]))
    return ranked[0][0]
