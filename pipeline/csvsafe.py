"""Spreadsheet formula-injection defense for CSV and XLSX cells."""

from __future__ import annotations

import csv
import io
import zipfile
from xml.sax.saxutils import escape

_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def sanitize_cell(value: object) -> str:
    """Prefix formula-like text so spreadsheet apps treat it as text.

    A leading apostrophe is the common CSV/XLSX neutralization. Amounts that
    are already plain numbers are left unchanged. Negative money strings that
    start with ``-`` are neutralized too; callers that want a numeric cell
    should pass a number and format it only after this check is skipped.
    """
    if value is None:
        return ""
    text = str(value)
    if text.startswith(_DANGEROUS) or text[:1] in _DANGEROUS:
        return "'" + text
    return text


def write_csv(rows: list[dict[str, object]], fieldnames: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: sanitize_cell(row.get(key)) for key in fieldnames})
    return buffer.getvalue()


def write_xlsx(rows: list[dict[str, object]], fieldnames: list[str]) -> bytes:
    """Minimal OOXML workbook. Every cell is an inline string, already sanitized."""

    def col_name(index: int) -> str:
        name = ""
        n = index
        while True:
            n, rem = divmod(n, 26)
            name = chr(65 + rem) + name
            if n == 0:
                break
            n -= 1
        return name

    sheet_rows = []
    all_rows = [fieldnames] + [[sanitize_cell(row.get(key)) for key in fieldnames] for row in rows]
    for r_index, values in enumerate(all_rows, start=1):
        cells = []
        for c_index, value in enumerate(values):
            ref = f"{col_name(c_index)}{r_index}"
            cells.append(
                f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{r_index}">{"".join(cells)}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="lines" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()
