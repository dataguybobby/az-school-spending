"""Documents this run is allowed to fetch. Hashes come from the v2 manifest."""

from __future__ import annotations

DOCUMENTS = [
    {
        "document_id": "susd_ap_2025-07-01_2025-08-19",
        "source_id": "susd_diligent_ap_report",
        "url": "https://susd.community.diligentoneplatform.com/document/b31fb6f1-672f-4543-b3a1-7455dff1773c/",
        "sha256": "3fb1de5547e7c7b4e822149ebcdc92994b9694586a5d32f6d756fe06f8d6d5c6",
        "adapter": "susd_ap_report_pdf",
        "manifest": "v2",
    },
    {
        "document_id": "susd_ap_2025-08-20_2025-09-17",
        "source_id": "susd_diligent_ap_report",
        "url": "https://susd.community.diligentoneplatform.com/document/078f4f57-1e1c-45ed-ae1e-c011747e476f/",
        "sha256": "92b5b4b9a22fb3f660b6f097c935dea519fe30331f4c30ae1b2b761518f59cfe",
        "adapter": "susd_ap_report_pdf",
        "manifest": "additional_public_url",
    },
    {
        "document_id": "susd_ap_2025-09-18_2025-10-27",
        "source_id": "susd_diligent_ap_report",
        "url": "https://susd.community.diligentoneplatform.com/document/792fd39d-83ee-4f82-a3c8-4bf444750a93/",
        "sha256": "42398b5e2742fc0c1377da402c854af17adf269b8cf6b3de92783097fd271cbe",
        "adapter": "susd_ap_report_pdf",
        "manifest": "additional_public_url",
    },
    {
        "document_id": "susd_ap_2025-10-27_2025-11-13",
        "source_id": "susd_diligent_ap_report",
        "url": "https://susd.community.diligentoneplatform.com/document/4cc33210-1ba8-4e9d-9946-95fcf4a50d61/",
        "sha256": "d72ec317de5a38a79d8d9c85a34856fe7913d6fc14a4fee6ac33cdc0ba726828",
        "adapter": "susd_ap_report_pdf",
        "manifest": "v2",
    },
    {
        "document_id": "susd_ap_2025-11-14_2025-12-02",
        "source_id": "susd_diligent_ap_report",
        "url": "https://susd.community.diligentoneplatform.com/document/c14cdd45-d273-45f9-b2f6-c251d51716d0/",
        "sha256": "1e3a60d4a9eee19cb5c82635afba081b8e6588fc16e40c3aa69fb4b666fbc420",
        "adapter": "susd_ap_report_pdf",
        "manifest": "additional_public_url",
    },
    {
        "document_id": "husd_voucher_batch_1058",
        "source_id": "husd_diligent_voucher_summary",
        "url": "https://husd.community.diligentoneplatform.com/document/689d0863-eeca-45c5-9d5f-46e9c061a48a/",
        "sha256": "239855d59bbf04e37de6f9ed0e3b3423d7ee8b1187af74f56c50aee6c3ad9bf0",
        "adapter": "diligent_voucher_account_summary",
        "manifest": "v2",
    },
    {
        "document_id": "qcusd_fy27_july_vouchers",
        "source_id": "qcusd_diligent_voucher_summary",
        "url": "https://qcusd.community.diligentoneplatform.com/document/a135f62d-cfb6-4d3f-857a-04be17e2ecfa/",
        "sha256": "345d6d2602aed2ac794286361ca4ebcf86f51f52d7d3dd6667288c4775a4125e",
        "adapter": "diligent_voucher_account_summary",
        "manifest": "v2",
    },
    {
        "document_id": "pvusd_fy26_vouchers_scan",
        "source_id": "pvusd_diligent_voucher_summary",
        "url": "https://pvschools.community.diligentoneplatform.com/document/e5ce46db-04b3-457d-856d-d32d5023cdd2/",
        "sha256": "56195ff643435ce2369b1d664c75ed84278ed10b0269d701bceda2e65f259e4d",
        "adapter": "diligent_voucher_account_summary",
        "manifest": "v2",
    },
    {
        "document_id": "chandler_voucher_aug2026",
        "source_id": "chandler_highbond_voucher_unverified",
        "url": "https://cusd80.community.highbond.com/document/ac3ffc57-9cef-4cc2-8373-dd59dec01e44/",
        "sha256": "f77483630293188a322d70a29c40c2c555d2f01d4c4e5af7ada48534741c45b9",
        "adapter": "diligent_voucher_account_summary",
        "manifest": "v2",
    },
]

AMOUNT_SEMANTICS = "reported_ap_or_vouchered_not_settlement"
