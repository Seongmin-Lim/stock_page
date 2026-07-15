"""Disk cache with TTL — keeps the scraping-based sources polite and the UI fast.

DataFrames are cached as parquet; small objects as JSON. A miss/expiry calls the
producer and rewrites the cache. All failures degrade gracefully (return producer result).
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

T = TypeVar("T")


def _key_path(key: str, suffix: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:20]
    return CACHE_DIR / f"{digest}{suffix}"


def _fresh(path: Path, ttl_sec: float) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < ttl_sec


def cache_df(
    key: str, ttl_sec: float, producer: Callable[[], pd.DataFrame]
) -> pd.DataFrame:
    """Return cached DataFrame if fresh, else produce + cache it."""
    path = _key_path(key, ".parquet")
    if _fresh(path, ttl_sec):
        try:
            return pd.read_parquet(path)
        except Exception:  # noqa: BLE001 - corrupt cache, fall through to re-produce
            pass
    df = producer()
    try:
        if df is not None and not df.empty:
            df.to_parquet(path)
    except Exception:  # noqa: BLE001 - caching is best-effort
        pass
    return df


def cache_json(key: str, ttl_sec: float, producer: Callable[[], T]) -> T:
    """Return cached JSON-able object if fresh, else produce + cache it."""
    path = _key_path(key, ".json")
    if _fresh(path, ttl_sec):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    obj = producer()
    try:
        path.write_text(
            json.dumps(obj, ensure_ascii=False, default=str), encoding="utf-8"
        )
    except Exception:  # noqa: BLE001
        pass
    return obj
