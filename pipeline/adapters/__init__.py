"""Document adapters. Only families exercised on real files are implemented."""

from pipeline.adapters.susd_ap import parse_susd_ap_pdf
from pipeline.adapters.voucher import parse_voucher_summary_pdf

ADAPTERS = {
    "susd_ap_report_pdf": parse_susd_ap_pdf,
    "diligent_voucher_account_summary": parse_voucher_summary_pdf,
}

UNSUPPORTED_FAMILIES = (
    "boarddocs_pdf_attachment",
    "district_hosted_html",
    "district_hosted_csv",
    "district_hosted_xls",
    "govly_public_award_html",
    "ade_xlsx_download",
)
