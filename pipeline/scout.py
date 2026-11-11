"""Bounded portal checks for three districts. This does not crawl without a cap.

It records what a public page or PDF actually is. Fund-total certifications and
board agendas are not ingested as vendor lines. A line-item PDF is reported
for ingest only when the paper-capture or text parser reconciles every batch.
HTTP 403 responses are recorded and not bypassed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pymupdf

from pipeline.adapters.voucher import parse_voucher_summary_pdf
from pipeline.fetch import fetch_url

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "registry" / "v2" / "portal_scout.json"
MAX_PAGES = 10
MAX_PDFS = 4

TARGETS = (
    {
        "source_id": "dysart_diligent_voucher_fund_totals",
        "entity_name": "Dysart Unified School District",
        "seeds": (
            "https://dysart.community.diligentoneplatform.com/",
            "https://dysart.community.diligentoneplatform.com/document/d2d59e07-0d1e-4115-8181-76e48450285a/",
        ),
    },
    {
        "source_id": "dvusd_agenda_voucher_approval_partial",
        "entity_name": "Deer Valley Unified School District",
        "seeds": (
            "https://dvusd.community.diligentoneplatform.com/",
            "https://dvusd.community.diligentoneplatform.com/document/3803/agenda.html",
        ),
    },
    {
        "source_id": "scout_tempe_union",
        "entity_name": "Tempe Union High School District",
        "seeds": (
            "https://tempeunion.community.diligentoneplatform.com/Portal/VirtualLibrary.aspx",
            "https://tempeunion.community.diligentoneplatform.com/",
        ),
    },
)


class _Anchors(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value:
                self.hrefs.append(value)


def scout() -> dict[str, object]:
    results = []
    for target in TARGETS:
        results.append(_one(target))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bounded_pages": MAX_PAGES,
        "bounded_pdfs": MAX_PDFS,
        "note": "Same-host links only. Not an exhaustive portal index and not a coverage rate.",
        "results": results,
    }
    LOG.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _one(target: dict[str, object]) -> dict[str, object]:
    raw_seeds = target["seeds"]
    seeds = [str(url) for url in raw_seeds] if isinstance(raw_seeds, tuple) else []
    host = urlparse(seeds[0]).netloc
    queue = list(seeds)
    seen: set[str] = set()
    pages: list[dict[str, object]] = []
    pdfs: list[dict[str, object]] = []
    work = Path("/tmp/ledger-scout")
    work.mkdir(parents=True, exist_ok=True)
    while queue and len(pages) + len(pdfs) < MAX_PAGES and len(pdfs) <= MAX_PDFS:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        dest = work / f"{target['source_id']}-{len(seen)}.bin"
        fetched = fetch_url(url, dest, timeout=25, attempts=1)
        kind = _kind(dest, str(fetched.get("content_type") or "")) if fetched.get("ok") else "fetch_failed"
        record = {
            "url": url,
            "ok": bool(fetched.get("ok")),
            "http_status": fetched.get("status"),
            "error": fetched.get("error"),
            "content_type": fetched.get("content_type"),
            "sha256": fetched.get("sha256"),
            "kind": kind,
        }
        if kind == "pdf":
            record.update(_classify_pdf(dest))
            pdfs.append(record)
        else:
            pages.append(record)
            if fetched.get("ok") and kind == "html":
                documents, other = _links(dest, url, host)
                for link in reversed(documents):
                    if link not in seen and link not in queue:
                        queue.insert(0, link)
                for link in other:
                    if link not in seen and link not in queue and len(queue) < MAX_PAGES:
                        queue.append(link)
        if dest.exists():
            dest.unlink()
        if len(pdfs) >= MAX_PDFS:
            break
    line_items = [row for row in pdfs if row.get("kind") == "pdf" and row.get("document_class") == "line_item_voucher"]
    reconciled = [row for row in line_items if row.get("reconciled") is True]
    return {
        "source_id": target["source_id"],
        "entity_name": target["entity_name"],
        "pages_fetched": len(pages),
        "pdfs_fetched": len(pdfs),
        "line_item_candidates": len(line_items),
        "reconciled_line_item_pdfs": len(reconciled),
        "ingest": reconciled[0]["url"] if reconciled else None,
        "pages": pages,
        "pdfs": pdfs,
    }


def _links(path: Path, base: str, host: str) -> tuple[list[str], list[str]]:
    parser = _Anchors()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    documents: list[str] = []
    other: list[str] = []
    skip = ("signin", "sign-in", "welcom", "meetingschedule", "meetingtypelist", "default.aspx")
    for href in parser.hrefs:
        absolute = urljoin(base, href).split("#")[0]
        parsed = urlparse(absolute)
        if parsed.netloc != host:
            continue
        lowered = absolute.lower()
        if any(token in lowered for token in skip):
            continue
        if "/document/" in lowered:
            documents.append(absolute)
        elif any(token in lowered for token in ("voucher", "agenda", "library", "portal")):
            other.append(absolute)
    return documents, other


def _kind(path: Path, content_type: str) -> str:
    if not path.exists() or path.stat().st_size == 0:
        return "empty"
    magic = path.read_bytes()[:5]
    if magic.startswith(b"%PDF") or "pdf" in content_type.lower():
        return "pdf"
    if "html" in content_type.lower() or path.read_bytes()[:1] == b"<" or b"<html" in path.read_bytes()[:200].lower():
        return "html"
    return "other"


def _classify_pdf(path: Path) -> dict[str, object]:
    document = pymupdf.open(path)
    text = "\n".join(page.get_text("text") for page in document)
    document.close()
    lowered = text.lower()
    if "vendor remit name" in lowered or ("account summary" in lowered and "grand" in lowered and "total" in lowered):
        parsed = parse_voucher_summary_pdf(str(path))
        reconciled = bool(parsed.batches) and all(batch.delta_cents == 0 for batch in parsed.batches) and all(
            batch.printed_total_cents is not None for batch in parsed.batches
        )
        return {
            "document_class": "line_item_voucher",
            "reconciled": reconciled,
            "parsed_lines": len(parsed.lines),
            "parsed_cents": sum(line.amount_cents for line in parsed.lines),
        }
    if "hereby authorized" in lowered and "vendor remit name" not in lowered:
        return {"document_class": "voucher_fund_total_cert", "reconciled": False, "parsed_lines": 0}
    if "agenda" in lowered:
        return {"document_class": "board_agenda", "reconciled": False, "parsed_lines": 0}
    return {"document_class": "unclassified_pdf", "reconciled": False, "parsed_lines": 0}
