"""Payee and description privacy classification.

Unknown and personal rows are withheld from the public index. Business vendors
stay public only when the description also passes.
"""

from __future__ import annotations

import re

BUSINESS_TOKENS = {
    "ACADEMY", "ACCOUNTING", "ALARM", "AMERICA", "AMERICAN", "APPAREL", "ARIZONA",
    "ART", "ARTS", "ASSOC", "ASSOCIATION", "ATHLETIC", "ATHLETICS", "AUDIO", "AUDIT",
    "AUDITING", "AUTO", "AUTOMOTIVE", "AWARDS", "BANK", "BAKERY", "BAND", "BENEFITS",
    "BEVERAGE", "BEVERAGES", "BOOK", "BOOKS", "BOOKSTORE", "BOOSTER", "BUILDERS",
    "BUILDING", "BULBS", "BUS", "CABLE", "CAFE", "CAMERA", "CAMERAS", "CAPITAL",
    "CATERING", "CENTER", "CENTERS", "CENTRE", "CHARTER", "CHEMICAL", "CHEMICALS",
    "CITY", "CLEANING", "CLINIC", "CO", "COFFEE", "COLLEGE", "COMMERCIAL",
    "COMMUNICATIONS", "COMPANY", "COMPANIES", "CONSTRUCTION", "CONSULTING",
    "CONTRACTOR", "CONTRACTORS", "CONTROL", "COOPERATIVE", "CORP", "CORPORATION",
    "COUNTY", "COUNSELING", "CRAFT", "CRAFTS", "CUSTODIAL", "DAIRY", "DBA", "DENTAL",
    "DEPARTMENT", "DEPOT", "DEPT", "DESIGN", "DEVELOPERS", "DEVELOPMENT", "DISPOSAL",
    "DISTRICT", "DISTRIBUTOR", "DISTRIBUTORS", "EDUCATION", "EDUCATIONAL", "ELECTRIC",
    "ELECTRICAL", "EMPLOYMENT", "ENERGY", "ENTERPRISE", "ENTERPRISES", "ENVIRONMENTAL",
    "EQUIPMENT", "ESCROW", "FEDERAL", "FINANCE", "FINANCIAL", "FLAG", "FLAGS", "FLEET",
    "FOOD", "FOODS", "FOUNDATION", "FREIGHT", "GAS", "GOVERNMENT", "GOVT", "GRAPHICS",
    "GRILL", "GROUP", "GROUPS", "HARDWARE", "HEALTH", "HOLDING", "HOLDINGS", "HOMES",
    "HOSPITAL", "HOTEL", "HOUSING", "HVAC", "INC", "INCORPORATED", "INDUSTRIAL",
    "INDUSTRIES", "INDUSTRY", "INSTITUTE", "INSTRUMENT", "INSTRUMENTS", "INSURANCE",
    "INTERNATIONAL", "JANITORIAL", "KITCHEN", "LAB", "LABS", "LABORATORY", "LAUNDRY",
    "LAW", "LEARNING", "LEASING", "LEGAL", "LIBRARY", "LIGHTING", "LIMITED", "LINEN",
    "LINES", "LLC", "LLP", "LP", "LC", "LOGISTICS", "MAINTENANCE", "MANAGEMENT",
    "MARKET", "MARKETING", "MARKETS", "MATERIAL", "MATERIALS", "MEATS", "MECHANICAL",
    "MEDIA", "MEDICAL", "MGMT", "MOTORS", "MOTOR", "MUSEUM", "MUSIC", "NATIONAL",
    "NETWORK", "NURSING", "OFFICE", "OPTICAL", "OUTLET", "PACKAGING", "PAINTING",
    "PAPER", "PARK", "PARKS", "PARTNERS", "PARTNERSHIP", "PAYROLL", "PC", "PEST",
    "PERFORMANCE", "PERSONNEL", "PETROLEUM", "PHARMACY", "PHOTO", "PHOTOGRAPHY",
    "PIZZA", "PLLC", "PLUMBING", "POWER", "PRINT", "PRINTERS", "PRINTING", "PRODUCE",
    "PRODUCT", "PRODUCTS", "PROFESSIONAL", "PROFESSIONALS", "PROMOTIONS", "PROPANE",
    "PROPERTIES", "PROPERTY", "PUBLIC", "PUBLISHERS", "PUBLISHING", "REALTY",
    "RECEIPTING", "RECREATION", "RECYCLING", "RENTAL", "RENTALS", "REPAIR", "REPAIRS",
    "RESTAURANT", "RETAIL", "RETIREMENT", "ROOFING", "SAFETY", "SANITARY",
    "SANITATION", "SCHOOL", "SCIENCE", "SECTOR", "SECURITY", "SERVICE", "SERVICES",
    "SHIPPING", "SIGNS", "SOFTWARE", "SOLAR", "SOLUTION", "SOLUTIONS", "SPORTS",
    "STAFFING", "STAGE", "STATE", "STORE", "STORES", "STUDIO", "STUDIOS", "SUPPLY",
    "SUPPLIES", "SYSTEM", "SYSTEMS", "TECH", "TECHNOLOGY", "THEATER", "THEATRE",
    "THERAPY", "TIRE", "TIRES", "TITLE", "TRANSPORT", "TRANSPORTATION", "TROPHY",
    "TROPHIES", "UNIFORM", "UNIFORMS", "UNITED", "UNIVERSITY", "UTILITY", "UTILITIES",
    "VIDEO", "VISION", "VISUAL", "WASTE", "WATER", "WHOLESALE", "WIRELESS", "WRAPS",
}

_EMAIL = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
_PHONE = re.compile(r"(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s])\d{3}[-.\s]\d{4}")
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_ADDRESS = re.compile(
    r"\b\d{1,6}\s+[A-Z0-9.'\-]+\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|BLVD|CT|COURT|WAY|PL|PLACE)\b",
    re.I,
)
_LONG_ID = re.compile(r"\b\d{9,}\b")
_PERSONAL_CONTEXT = re.compile(
    r"\b(reimburse\w*|mileage|orientation pay|student name|parent of|guardian|home address|date of birth)\b",
    re.I,
)
_ROLE_NAME = re.compile(
    r"\b(student|teacher|employee|parent|child|pupil)\b[^.\n]{0,48}\b[A-Z][a-z]+\s+[A-Z][a-z]+\b"
)
_AUTHORIZED_USER = re.compile(r"authori[sz]ed\s+users?", re.I)
_IEP_OR_ESY = re.compile(r"\b(IEP|ESY)s?\b", re.I)
_SENSITIVE_MEDICAL = re.compile(
    r"\b(medicaid|diagnosis|prescription|psychiatric|psychotherapy)\b",
    re.I,
)
_COMMA_NAME = re.compile(
    r"[A-Z][A-Z'’\-]+,\s*[A-Z][A-Z'’\-\.]+(?:\s+[A-Z][A-Z'’\-\.]+){0,3}"
)


def vendor_class(vendor: str | None) -> str:
    """Classify a payee. ``unknown`` is withheld, the same as a personal payee."""
    raw = re.sub(r"\s+", " ", (vendor or "")).strip()
    if not raw:
        return "unknown"
    upper = raw.upper()
    tokens = re.findall(r"[A-Z0-9&']+", upper)
    business = any(token in BUSINESS_TOKENS for token in tokens)
    if _COMMA_NAME.fullmatch(upper) and not business:
        return "personal_payee"
    if business:
        return "safe_business_vendor"
    if any(any(ch.isdigit() for ch in token) for token in tokens):
        return "safe_business_vendor"
    if any(len(token) == 1 for token in tokens) and 2 <= len(tokens) <= 4:
        return "personal_payee"
    if len(tokens) == 1 or len(tokens) >= 4:
        return "safe_business_vendor"
    return "unknown"


def assess_row(vendor: str | None, description: str | None) -> tuple[str, list[str]]:
    """Return ``(privacy_class, reasons)``.

    A business payee is still withheld when the vendor or description carries
    contact data, a long identifier, or personal-reimbursement / student context.
    Sensitive text that OCR glued onto the vendor is quarantined with the row.
    """
    reasons: list[str] = []
    payee = vendor_class(vendor)
    if payee == "personal_payee":
        reasons.append("payee_name_pattern")
    elif payee == "unknown":
        reasons.append("payee_unclassified")
    text = f"{vendor or ''} {description or ''}".strip()
    if _EMAIL.search(text) or _PHONE.search(text) or _SSN.search(text) or _ADDRESS.search(text):
        reasons.append("description_contact_or_address")
    if _LONG_ID.search(text):
        reasons.append("description_long_identifier")
    if _PERSONAL_CONTEXT.search(text):
        reasons.append("description_personal_context")
    if _ROLE_NAME.search(text):
        reasons.append("description_role_and_name")
    if _AUTHORIZED_USER.search(text):
        reasons.append("description_authorized_user")
    if _IEP_OR_ESY.search(text):
        reasons.append("description_iep_or_esy")
    if _SENSITIVE_MEDICAL.search(text):
        reasons.append("description_sensitive_medical")
    if payee == "safe_business_vendor" and not reasons:
        return "safe_business_vendor", []
    if payee == "personal_payee" and not any(reason.startswith("description") for reason in reasons):
        return "personal_payee", reasons
    if reasons and payee == "safe_business_vendor":
        return "mixed", reasons
    if payee == "personal_payee":
        return "personal_payee", reasons
    return "unknown", reasons or ["unclassified"]


def public_allowed(privacy_class: str) -> bool:
    return privacy_class == "safe_business_vendor"
