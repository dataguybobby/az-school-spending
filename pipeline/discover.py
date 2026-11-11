"""Bounded public-page discovery. It records anchors. It does not ingest them."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from pipeline.fetch import fetch_url
from pipeline.paths import log_dir

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry" / "v2" / "sources.json"
MAX_SOURCES = 8
TIMEOUT = 20.0


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


def discover() -> dict[str, object]:
    sources = json.loads(REGISTRY.read_text(encoding="utf-8"))["sources"]
    chosen = [row for row in sources if row.get("discovery_url")][:MAX_SOURCES]
    results = []
    for source in chosen:
        url = str(source["discovery_url"])
        dest = log_dir() / f"discover-{source['source_id']}.bin"
        fetched = fetch_url(url, dest, timeout=TIMEOUT, attempts=1)
        anchors: list[str] = []
        if fetched.get("ok") and "html" in str(fetched.get("content_type") or ""):
            parser = _Anchors()
            parser.feed(dest.read_text(encoding="utf-8", errors="replace"))
            host = urlparse(url).netloc
            for href in parser.hrefs:
                absolute = urljoin(url, href)
                if urlparse(absolute).netloc == host:
                    anchors.append(absolute)
        results.append({
            "source_id": source["source_id"],
            "source_status": source.get("source_status"),
            "discovery_url": url,
            "ok": bool(fetched.get("ok")),
            "http_status": fetched.get("status"),
            "error": fetched.get("error"),
            "same_host_anchors": len(set(anchors)),
            "note": "Anchors are unreviewed. This command does not add ledger rows or claim a complete census.",
        })
        if dest.exists():
            dest.unlink()
    report = {"bounded_to": MAX_SOURCES, "results": results}
    (log_dir() / "discovery.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
