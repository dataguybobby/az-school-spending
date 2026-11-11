"""Filesystem locations. Raw bytes stay under data/ and out of git."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def home() -> Path:
    override = os.environ.get("LEDGER_HOME")
    return Path(override) if override else ROOT / "data"


def raw_dir() -> Path:
    path = home() / "raw"
    path.mkdir(parents=True, exist_ok=True)
    return path


def public_db() -> Path:
    path = home() / "public"
    path.mkdir(parents=True, exist_ok=True)
    return path / "ledger.sqlite"


def private_db() -> Path:
    path = home() / "private"
    path.mkdir(parents=True, exist_ok=True)
    return path / "ledger.sqlite"


def log_dir() -> Path:
    path = home() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
