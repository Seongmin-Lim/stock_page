"""Unified, key-free data access: FinanceDataReader + yfinance + pykrx.

Market is auto-detected from the symbol (6-digit numeric → KR, else US).
Data is delayed/EOD (no realtime, since no API keys). Heavy calls go through cache.py.
Data libraries are imported lazily so the server still boots if a lib is missing.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from backend.cache import cache_df
from backend.schema import Bar, FinancialRow, Fundamentals, OHLCVResponse, Quote

_KR_CODE = re.compile(r"^\d{6}$")

_PERIOD_DAYS = {
    "1mo": 31,
    "3mo": 93,
    "6mo": 186,
    "1y": 366,
    "2y": 731,
    "3y": 1096,
    "5y": 1827,
    "10y": 3653,
    "max": 8000,
}
_RESAMPLE = {"1wk": "W-FRI", "1mo": "ME"}


def detect_market(symbol: str) -> str:
    return "KR" if _KR_CODE.match(symbol.strip()) else "US"


def currency_of(market: str) -> str:
    return "KRW" if market == "KR" else "USD"


def _start_for(period: str) -> str:
    days = _PERIOD_DAYS.get(period, 366)
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")


# ── OHLCV ────────────────────────────────────────────────────────────
def _raw_daily(symbol: str, start: str) -> pd.DataFrame:
    """Daily OHLCV via FinanceDataReader (works for KR codes and US tickers).

    A bad/delisted ticker (e.g. 404 from the upstream feed) must NOT crash callers — a
    failed fetch degrades to an empty frame so batch builds (recommend/cycles) skip it.
    """
    try:
        import FinanceDataReader as fdr

        df = fdr.DataReader(symbol, start)
    except Exception:  # noqa: BLE001 - upstream feed errors (404/blocked) → empty
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    keep = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
    df = df[keep].copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"
    return df.dropna(subset=["Close"])


def get_ohlcv_df(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    start = _start_for(period)
    key = f"ohlcv:{symbol}:{start}"
    df = cache_df(key, ttl_sec=3600, producer=lambda: _raw_daily(symbol, start))
    if df.empty:
        return df
    if interval in _RESAMPLE:
        agg = {
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }
        df = df.resample(_RESAMPLE[interval]).agg(agg).dropna(subset=["Close"])
    return df


def get_ohlcv(symbol: str, period: str, interval: str) -> OHLCVResponse:
    market = detect_market(symbol)
    df = get_ohlcv_df(symbol, period, interval)
    bars: list[Bar] = []
    for ts, row in df.iterrows():
        bars.append(
            Bar(
                time=ts.strftime("%Y-%m-%d"),
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=float(row.get("Volume", 0) or 0),
            )
        )
    from backend.universe import name_of

    return OHLCVResponse(
        symbol=symbol,
        market=market,
        name=name_of(symbol),
        currency=currency_of(market),
        bars=bars,
    )


# ── KR snapshot (shared by quote + screener) ─────────────────────────
def kr_listing_snapshot() -> pd.DataFrame:
    """Whole-market KR snapshot via FinanceDataReader (one reliable key-free call).

    Columns (indexed by 6-digit symbol): name, market, price, change, change_pct,
    open, high, low, volume, marketcap, shares. PER/PBR are NOT here (need pykrx, which
    can be down) — enriched best-effort by `_kr_fundamentals`.
    """

    def produce() -> pd.DataFrame:
        import FinanceDataReader as fdr

        raw = fdr.StockListing("KRX")
        if raw is None or raw.empty or "Code" not in raw.columns:
            return pd.DataFrame()
        out = pd.DataFrame(
            {
                "symbol": raw["Code"].astype(str).str.zfill(6),
                "name": raw.get("Name"),
                "market": raw.get("Market"),
                "price": pd.to_numeric(raw.get("Close"), errors="coerce"),
                "change": pd.to_numeric(raw.get("Changes"), errors="coerce"),
                "change_pct": pd.to_numeric(raw.get("ChagesRatio"), errors="coerce"),
                "open": pd.to_numeric(raw.get("Open"), errors="coerce"),
                "high": pd.to_numeric(raw.get("High"), errors="coerce"),
                "low": pd.to_numeric(raw.get("Low"), errors="coerce"),
                "volume": pd.to_numeric(raw.get("Volume"), errors="coerce"),
                "marketcap": pd.to_numeric(raw.get("Marcap"), errors="coerce"),
                "shares": pd.to_numeric(raw.get("Stocks"), errors="coerce"),
            }
        )
        return out.set_index("symbol")

    return cache_df("kr_snapshot", ttl_sec=1800, producer=produce)


def _kr_fundamentals(symbol: str) -> dict[str, float | None]:
    """Best-effort PER/PBR/EPS/BPS/DIV via pykrx. Returns empty dict if KRX is down."""
    try:
        from pykrx import stock

        bd = stock.get_nearest_business_day_in_a_week()
        for mkt in ("KOSPI", "KOSDAQ"):
            fund = stock.get_market_fundamental_by_ticker(bd, market=mkt)
            if symbol in fund.index:
                r = fund.loc[symbol]
                return {
                    "PER": _f(r.get("PER")),
                    "PBR": _f(r.get("PBR")),
                    "EPS": _f(r.get("EPS")),
                    "BPS": _f(r.get("BPS")),
                    "DIV": _f(r.get("DIV")),
                    "DPS": _f(r.get("DPS")),
                }
    except Exception:  # noqa: BLE001 - KRX fundamental endpoint frequently blocked
        pass
    return {}


# ── quote ────────────────────────────────────────────────────────────
def _quote_kr(symbol: str) -> Quote:
    from backend.universe import name_of

    snap = kr_listing_snapshot()
    row = snap.loc[symbol] if (not snap.empty and symbol in snap.index) else None
    price = _f(row["price"]) if row is not None else None
    change = _f(row["change"]) if row is not None else None
    change_pct = _f(row["change_pct"]) if row is not None else None
    prev = (price - change) if (price is not None and change is not None) else None
    f = _kr_fundamentals(symbol)
    return Quote(
        symbol=symbol,
        name=(str(row["name"]) if row is not None else name_of(symbol)),
        market="KR",
        currency="KRW",
        price=price,
        prev_close=prev,
        change=change,
        change_pct=change_pct,
        open=_f(row["open"]) if row is not None else None,
        high=_f(row["high"]) if row is not None else None,
        low=_f(row["low"]) if row is not None else None,
        volume=_f(row["volume"]) if row is not None else None,
        market_cap=_f(row["marketcap"]) if row is not None else None,
        per=f.get("PER"),
        pbr=f.get("PBR"),
        eps=f.get("EPS"),
        div_yield=f.get("DIV"),
        updated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def _quote_us(symbol: str) -> Quote:
    import yfinance as yf

    from backend.universe import name_of

    t = yf.Ticker(symbol)
    info: dict = {}
    try:
        info = t.info or {}
    except Exception:  # noqa: BLE001
        info = {}
    price = _f(info.get("currentPrice")) or _f(info.get("regularMarketPrice"))
    prev = _f(info.get("previousClose"))
    if price is None:
        try:
            fi = t.fast_info
            price = _f(getattr(fi, "last_price", None))
            prev = prev or _f(getattr(fi, "previous_close", None))
        except Exception:  # noqa: BLE001
            pass
    change = (price - prev) if (price is not None and prev is not None) else None
    change_pct = (change / prev * 100.0) if (change is not None and prev) else None
    name = info.get("shortName") or info.get("longName") or name_of(symbol)
    return Quote(
        symbol=symbol,
        name=name,
        market="US",
        currency=info.get("currency", "USD"),
        price=price,
        prev_close=prev,
        change=change,
        change_pct=change_pct,
        open=_f(info.get("open")),
        high=_f(info.get("dayHigh")),
        low=_f(info.get("dayLow")),
        volume=_f(info.get("volume")),
        market_cap=_f(info.get("marketCap")),
        per=_f(info.get("trailingPE")),
        pbr=_f(info.get("priceToBook")),
        eps=_f(info.get("trailingEps")),
        div_yield=_pct(info.get("dividendYield")),
        w52_high=_f(info.get("fiftyTwoWeekHigh")),
        w52_low=_f(info.get("fiftyTwoWeekLow")),
        updated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def get_quote(symbol: str) -> Quote:
    return _quote_kr(symbol) if detect_market(symbol) == "KR" else _quote_us(symbol)


# ── fundamentals ─────────────────────────────────────────────────────
def _statement_rows(
    df: pd.DataFrame, labels: list[str]
) -> tuple[list[str], list[FinancialRow]]:
    if df is None or df.empty:
        return [], []
    periods = [str(c)[:10] for c in df.columns][:5]
    rows: list[FinancialRow] = []
    for label in labels:
        if label in df.index:
            vals = [_f(v) for v in df.loc[label].tolist()][:5]
            rows.append(FinancialRow(label=label, values=vals))
    return periods, rows


def get_fundamentals(symbol: str) -> Fundamentals:
    market = detect_market(symbol)
    from backend.universe import name_of

    if market == "US":
        import yfinance as yf

        t = yf.Ticker(symbol)
        info = {}
        try:
            info = t.info or {}
        except Exception:  # noqa: BLE001
            info = {}
        periods, income = _statement_rows(
            _safe(t, "income_stmt"),
            [
                "Total Revenue",
                "Gross Profit",
                "Operating Income",
                "Net Income",
                "EBITDA",
            ],
        )
        _, balance = _statement_rows(
            _safe(t, "balance_sheet"),
            [
                "Total Assets",
                "Total Liabilities Net Minority Interest",
                "Stockholders Equity",
                "Total Debt",
                "Cash And Cash Equivalents",
            ],
        )
        _, cashflow = _statement_rows(
            _safe(t, "cashflow"),
            [
                "Operating Cash Flow",
                "Investing Cash Flow",
                "Financing Cash Flow",
                "Free Cash Flow",
            ],
        )
        multiples = {
            "PER": _f(info.get("trailingPE")),
            "ForwardPER": _f(info.get("forwardPE")),
            "PBR": _f(info.get("priceToBook")),
            "PSR": _f(info.get("priceToSalesTrailing12Months")),
            "ROE": _pct(info.get("returnOnEquity")),
            "ROA": _pct(info.get("returnOnAssets")),
            "OperatingMargin": _pct(info.get("operatingMargins")),
            "DividendYield": _pct(info.get("dividendYield")),
        }
        return Fundamentals(
            symbol=symbol,
            name=info.get("shortName") or name_of(symbol),
            market="US",
            currency=info.get("currency", "USD"),
            periods=periods,
            income=income,
            balance=balance,
            cashflow=cashflow,
            multiples=multiples,
        )

    # KR — pykrx ratios + DART financial statements (key in .env).
    snap = kr_listing_snapshot()
    row = snap.loc[symbol] if (not snap.empty and symbol in snap.index) else None
    multiples: dict[str, float | None] = {}
    if row is not None:
        multiples["시가총액"] = _f(row["marketcap"])
        multiples["현재가"] = _f(row["price"])
    kf = _kr_fundamentals(symbol)
    for k in ("PER", "PBR", "EPS", "BPS", "DIV", "DPS"):
        if k in kf:
            multiples[k] = kf[k]

    # DART statements + derived ratios
    from datetime import datetime as _dt

    from backend.dart import kr_financials, kr_statement_table

    periods: list[str] = []
    income: list[FinancialRow] = []
    balance: list[FinancialRow] = []
    fin_year = None
    for year in (_dt.now().year - 1, _dt.now().year - 2):
        p, tbl = kr_statement_table(symbol, year)
        if p:
            periods = p
            income = [FinancialRow(**r) for r in tbl.get("income", [])]
            balance = [FinancialRow(**r) for r in tbl.get("balance", [])]
            fin_year = year
            break
    if fin_year is not None:
        fin = kr_financials(symbol, fin_year)
        for label, key in (
            ("영업이익률", "operating_margin"),
            ("순이익률", "net_margin"),
            ("매출성장률", "revenue_growth"),
            ("부채비율", "debt_ratio"),
            ("ROE", "roe"),
        ):
            if fin.get(key) is not None:
                multiples[label] = round(fin[key], 1)

    note = "재무제표는 DART 전자공시(연결재무제표 CFS) 기준입니다."
    if fin_year is None:
        note = "DART 재무제표를 불러오지 못했습니다(키 미설정 또는 일시 오류). 기초지표만 표시합니다."
    return Fundamentals(
        symbol=symbol,
        name=(str(row["name"]) if row is not None else name_of(symbol)),
        market="KR",
        currency="KRW",
        periods=periods,
        income=income,
        balance=balance,
        cashflow=[],
        multiples=multiples,
        note=note,
    )


# ── helpers ──────────────────────────────────────────────────────────
def _safe(ticker: object, attr: str) -> pd.DataFrame:
    try:
        df = getattr(ticker, attr)
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


def _f(v: object) -> float | None:
    try:
        if v is None:
            return None
        f = float(v)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _pct(v: object) -> float | None:
    """yfinance returns ratios (0.23) for margins/yield → express as percent."""
    f = _f(v)
    return None if f is None else f * 100.0
