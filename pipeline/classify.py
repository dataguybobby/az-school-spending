"""Neutral spending categories. Amazon is a vendor, never a category.

Item text is weak evidence. Account titles printed by the district are stronger
and still not a sourced USFR codebook. Unclassified is the default.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RULESET_VERSION = "phoenix-k12-neutral-2026.11.11"

# Longer needles are checked by score, not by list order alone.
_RULES: list[tuple[str, float, str, str]] = [
    ("technology", 0.72, "SUPPLIES-TECHNOLOGY", "account title says technology supplies"),
    ("technology", 0.7, "TECHNOLOGY HARDWARE", "account title says technology hardware"),
    ("technology", 0.68, "TECHNOLOGY - RELATED", "account title says technology-related"),
    ("technology", 0.62, "SOFTWARE", "description mentions software"),
    ("technology", 0.55, "CHROMEBOOK", "item text mentions a chromebook"),
    ("technology", 0.55, "LAPTOP", "item text mentions a laptop"),
    ("technology", 0.55, "IPAD", "item text mentions an iPad"),
    ("technology", 0.5, "PRINTER", "item text mentions a printer"),
    ("facilities", 0.74, "REPAIRS & MAINTENANCE", "account title says repairs and maintenance"),
    ("facilities", 0.74, "REPAIRS AND MAINTENANCE", "account title says repairs and maintenance"),
    ("facilities", 0.7, "CUSTODIAL", "description says custodial"),
    ("facilities", 0.62, "HVAC", "description mentions HVAC"),
    ("transport", 0.7, "STUDENT TRANSPORTATION", "account title says student transportation"),
    ("transport", 0.64, "CHARTER BUS", "description says charter bus"),
    ("food", 0.72, "FOOD SERVICE", "description says food service"),
    ("food", 0.66, "CAFETERIA", "description mentions cafeteria"),
    ("professional_services", 0.7, "PROFESSIONAL SERVICES", "account title says professional services"),
    ("professional_services", 0.68, "TECHNICAL SERVICES", "account title says technical services"),
    ("professional_services", 0.68, "AUDIT SERVICES", "account title says audit services"),
    ("professional_services", 0.55, "DUES AND FEES", "account title says dues and fees"),
    ("professional_services", 0.55, "DUES & FEES", "account title says dues and fees"),
    ("instructional_materials", 0.5, "TEXTBOOK", "item text mentions a textbook"),
    ("instructional_materials", 0.48, "PENCIL", "item text mentions pencils"),
    ("instructional_materials", 0.48, "NOTEBOOK", "item text mentions notebooks"),
    ("instructional_materials", 0.46, "FOLDER", "item text mentions folders"),
    ("instructional_materials", 0.46, "COPY PAPER", "item text mentions copy paper"),
    ("instructional_materials", 0.44, "MARKER", "item text mentions markers"),
    ("instructional_materials", 0.44, "ERASER", "item text mentions erasers"),
    ("instructional_materials", 0.42, "STICKY NOTE", "item text mentions sticky notes"),
    ("student_support", 0.4, "STRESS BALL", "item text only; purpose is not proven"),
    ("student_support", 0.4, "SQUISH", "item text only; purpose is not proven"),
    ("student_support", 0.38, "STICKER", "item text only; purpose is not proven"),
    ("student_support", 0.42, "TUITION", "account title says tuition"),
    ("staff_activities", 0.4, "STAFF APPRECIATION", "description mentions staff appreciation"),
    ("utilities", 0.86, "NATURAL GAS", "description says natural gas"),
    ("utilities", 0.86, "WATER/SEWAGE", "description says water and sewage"),
    ("utilities", 0.86, "WATER/SEWER", "description says water and sewer"),
    ("utilities", 0.82, ";GAS,", "metered gas charge"),
    ("utilities", 0.82, ";WATER,", "metered water charge"),
    ("utilities", 0.82, ";SEWER,", "metered sewer charge"),
    ("utilities", 0.82, ";ELECTRICITY,", "metered electricity charge"),
    ("utilities", 0.8, "THERMS#", "gas use measured in therms"),
    ("utilities", 0.8, "KWH#", "electricity measured in kilowatt hours"),
    ("utilities", 0.78, "GALLONS#", "water use measured in gallons"),
    ("communications", 0.8, ";TELEPHONE,", "metered telephone charge"),
    ("communications", 0.74, "CELL PHONE", "description says cell phone service"),
    ("food", 0.7, "OAK CATERING", "description names a catering order"),
    ("food", 0.68, "ADULT CATERING", "description says adult catering"),
    ("food", 0.66, "FOOD/CATERING", "description says food or catering"),
    ("transport", 0.74, "DIESEL FUEL", "description says diesel fuel"),
    ("transport", 0.72, "YELLOW FLEET", "description says yellow fleet parts"),
    ("transport", 0.66, "VEHICLE PARTS", "description says vehicle parts"),
    ("instructional_materials", 0.7, "INSTRUCTIONAL AID", "description says instructional aids"),
    ("instructional_materials", 0.64, "COPIER PAPER", "description says copier paper"),
    ("facilities", 0.72, "BLDG MAINT", "description says building maintenance"),
    ("facilities", 0.7, "BLDG IMP", "description says building improvement"),
    ("facilities", 0.7, "SEWER LID", "description says a sewer lid repair"),
    ("facilities", 0.68, "REPAIR/MAINT", "description says repair and maintenance"),
    ("insurance", 0.8, "INSURANCE", "description says insurance"),
]


def _load_overrides(path: Path | None) -> dict[str, dict[str, object]]:
    if path is None or not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    found: dict[str, dict[str, object]] = {}
    for row in payload.get("overrides", []):
        key = str(row.get("line_id") or "")
        if key:
            found[key] = row
    return found


def classify_text(description: str | None, account_code: str | None = None) -> dict[str, object]:
    haystack = f"{description or ''}\n{account_code or ''}".upper()
    best: tuple[float, str, str, str] | None = None
    for category, confidence, needle, evidence in _RULES:
        if needle in haystack:
            if best is None or confidence > best[0] or (confidence == best[0] and len(needle) > len(best[3])):
                best = (confidence, category, evidence, needle)
    if best is None:
        return {
            "category": "unclassified",
            "category_confidence": 0.0,
            "category_ruleset": RULESET_VERSION,
            "category_evidence": "no rule matched",
            "category_source": "ruleset",
        }
    confidence, category, evidence, needle = best
    return {
        "category": category,
        "category_confidence": confidence,
        "category_ruleset": RULESET_VERSION,
        "category_evidence": f"{evidence}; needle={needle}",
        "category_source": "ruleset",
    }


def apply_override(result: dict[str, object], line_id: str, overrides: dict[str, dict[str, object]]) -> dict[str, object]:
    override = overrides.get(line_id)
    if not override:
        return result
    updated = dict(result)
    updated["category"] = str(override["category"])
    updated["category_confidence"] = float(override.get("confidence", 1))
    updated["category_evidence"] = str(override.get("evidence", "manual override"))
    updated["category_source"] = "manual_override"
    updated["category_ruleset"] = RULESET_VERSION
    return updated


def load_overrides(path: Path | None) -> dict[str, dict[str, object]]:
    return _load_overrides(path)
