"""Production Next build used for a later Vercel deployment. Not a deploy."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_next_production_build_succeeds():
    subprocess.check_call(["npm", "run", "build"], cwd=ROOT / "web", timeout=240)
    assert (ROOT / "web" / ".next" / "BUILD_ID").is_file()
    trace = (ROOT / "web" / ".next" / "server" / "app" / "page.js.nft.json").read_text(encoding="utf-8")
    assert "data/public/ledger.sqlite" in trace
    assert "data/raw" not in trace
    assert "data/private" not in trace
