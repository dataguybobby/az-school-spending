"""Public HTTP fetch. Retries only transient status codes. No bypasses."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "PhoenixK12Ledger/0.1 (local research; public documents only)"
TRANSIENT = {408, 425, 429, 500, 502, 503, 504}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_url(url: str, dest: Path, timeout: float = 45.0, attempts: int = 3) -> dict[str, object]:
    last_error = "not_attempted"
    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,text/html,*/*"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
                content_type = response.headers.get("Content-Type", "")
                status = getattr(response, "status", 200)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(payload)
            return {
                "ok": True,
                "status": status,
                "content_type": content_type.split(";")[0].strip(),
                "byte_length": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        except urllib.error.HTTPError as error:
            last_error = f"http_{error.code}"
            if error.code not in TRANSIENT or attempt == attempts:
                return {"ok": False, "status": error.code, "error": last_error}
            time.sleep(attempt)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            last_error = type(error).__name__
            if attempt == attempts:
                return {"ok": False, "status": None, "error": last_error}
            time.sleep(attempt)
    return {"ok": False, "status": None, "error": last_error}


def write_sidecar(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
