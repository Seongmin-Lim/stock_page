"""Market regime — a quick read on whether the broad indices are in a healthy
uptrend (risk-on) or below trend (risk-off). Key-free: last close vs prev close,
above/below the 200DMA, and the trailing ~1-month (21-bar) return, per index.

Used by the frontend as a top-of-page "market weather" banner. Cached 30 min.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from backend.cache import cache_json
from backend.indicators import sma
from backend.schema import RegimeItem, RegimeResult
from backend.sources import get_ohlcv_df

# index symbol → (market, display name). FDR resolves KS11 / US500 to daily OHLCV.
_INDICES: list[tuple[str, str, str]] = [
    ("KS11", "KR", "코스피"),
    ("US500", "US", "S&P 500"),
]


def _regime_item(symbol: str, market: str, name: str) -> RegimeItem:
    df = get_ohlcv_df(symbol, "1y", "1d")
    if df.empty or "Close" not in df.columns:
        return RegimeItem(
            market=market,
            index_name=name,
            price=None,
            change_pct=None,
            above_ma200=None,
            ret_1m=None,
        )
    close = df["Close"].dropna()
    price = float(close.iloc[-1])
    change_pct = (
        (price / float(close.iloc[-2]) - 1.0) * 100.0 if len(close) >= 2 else None
    )
    above_ma200: bool | None = None
    if len(close) >= 200:
        ma200 = sma(close, 200).iloc[-1]
        if not pd.isna(ma200):
            above_ma200 = bool(price > float(ma200))
    ret_1m = (
        (price / float(close.iloc[-22]) - 1.0) * 100.0 if len(close) >= 22 else None
    )
    return RegimeItem(
        market=market,
        index_name=name,
        price=round(price, 2),
        change_pct=round(change_pct, 2) if change_pct is not None else None,
        above_ma200=above_ma200,
        ret_1m=round(ret_1m, 2) if ret_1m is not None else None,
    )


def _build() -> dict:
    items = [_regime_item(sym, mkt, name) for sym, mkt, name in _INDICES]
    return RegimeResult(
        items=items,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    ).model_dump()


def regime() -> RegimeResult:
    data = cache_json("regime", ttl_sec=1800, producer=_build)
    return RegimeResult(**data)
