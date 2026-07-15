"""Tiny JSON persistence for user state (watchlist, portfolio, alerts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from backend.cache import DATA_DIR

T = TypeVar("T")


def load_json(name: str, default: T) -> T:
    path = DATA_DIR / name
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - corrupt file → fall back to default
        return default


def save_json(name: str, obj: object) -> None:
    path = DATA_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
