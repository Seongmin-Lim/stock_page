"""KR investor flows (foreign / institution net buying) via Naver Finance.

pykrx's KRX investor endpoint is frequently blocked, so we scrape Naver's per-stock
foreign/institution table (key-free). Cached 1h; degrades gracefully to an empty result.
"""

from __future__ import annotations

import io

import pandas as pd

from backend.cache import cache_json
from backend.schema import FlowDay, FlowResult

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _scrape(symbol: str) -> list[dict]:
    import requests

    url = f"https://finance.naver.com/item/frgn.naver?code={symbol}"
    r = requests.get(url, headers=_HEADERS, timeout=10)
    r.encoding = "euc-kr"
    tables = pd.read_html(io.StringIO(r.text))
    target = None
    for t in tables:
        if t.shape[1] >= 8 and t.shape[0] >= 5:
            target = t
            break
    if target is None:
        return []
    target.columns = [
        "date",
        "close",
        "chg",
        "chg_pct",
        "volume",
        "inst",
        "foreign_net",
        "foreign_hold",
        "foreign_pct",
    ]
    rows: list[dict] = []
    for _, r2 in target.iterrows():
        d = str(r2["date"]).strip()
        if not d or d == "nan" or "." not in d:
            continue
        rows.append(
            {
                "time": d.replace(".", "-"),
                "close": _num(r2["close"]),
                "inst": _num(r2["inst"]),
                "foreign": _num(r2["foreign_net"]),
                "foreign_hold_pct": _num(r2["foreign_pct"]),
            }
        )
    rows.reverse()  # oldest first
    return rows


def get_flows(symbol: str) -> FlowResult:
    from backend.sources import detect_market
    from backend.universe import name_of

    if detect_market(symbol) != "KR":
        return FlowResult(
            symbol=symbol,
            name=name_of(symbol),
            market="US",
            note="외국인·기관 수급은 한국 종목만 제공됩니다.",
        )

    rows = cache_json(f"flows:{symbol}", 3600, lambda: _safe_scrape(symbol))
    days = [FlowDay(**r) for r in rows]
    note = (
        None
        if days
        else "수급 데이터를 불러오지 못했습니다(네이버 응답 오류). 잠시 후 다시 시도하세요."
    )

    def _tail_sum(key: str, n: int) -> float | None:
        vals = [getattr(d, key) for d in days[-n:] if getattr(d, key) is not None]
        return float(sum(vals)) if vals else None

    return FlowResult(
        symbol=symbol,
        name=name_of(symbol),
        market="KR",
        days=days,
        inst_sum_5d=_tail_sum("inst", 5),
        foreign_sum_5d=_tail_sum("foreign", 5),
        inst_sum_20d=_tail_sum("inst", 20),
        foreign_sum_20d=_tail_sum("foreign", 20),
        note=note,
    )


def _safe_scrape(symbol: str) -> list[dict]:
    try:
        return _scrape(symbol)
    except Exception:  # noqa: BLE001 - scraping is best-effort
        return []


def _num(v: object) -> float | None:
    try:
        s = str(v).replace(",", "").replace("%", "").replace("+", "").strip()
        if s in ("", "nan"):
            return None
        return float(s)
    except (TypeError, ValueError):
        return None
