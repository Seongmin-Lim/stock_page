"""Rule-based screener (robust, key-light).

Three tiers of fields:
  • cheap  (whole-market, instant): price, marketcap, change_pct — from the FDR snapshot.
  • fundamental (per-candidate): per, pbr, roe — computed for a *capped* candidate pool.
      KR  → from DART statements + market cap  (PER=시총/순이익, PBR=시총/자본, ROE=순이익/자본).
            This bypasses the often-blocked pykrx ratio endpoint entirely.
      US  → from yfinance .info (trailingPE / priceToBook / returnOnEquity).
  • technical (per-candidate): above_ma200, rsi, ret_1y — from cached OHLCV.

The candidate pool is pre-narrowed by cheap filters (and sorted by market cap), then capped,
so per-candidate work stays bounded. Results are cached. Pattern: finance/tool-architecture.md.
"""

from __future__ import annotations

import re

import pandas as pd

from backend.cache import cache_df
from backend.indicators import rsi as rsi_series
from backend.indicators import sma
from backend.schema import ScreenFilter, ScreenResult, ScreenRow, ScreenSpec
from backend.sources import _f, get_ohlcv_df

_SNAP_TTL = 60 * 60 * 12
_POOL_CAP = 120  # max candidates to compute per-stock fundamentals/technicals for

_CHEAP_FIELDS = {"marketcap", "price", "change_pct"}
_FUNDAMENTAL_FIELDS = {"per", "pbr", "roe"}
_TECHNICAL_FIELDS = {"above_ma200", "rsi", "ret_1y"}


# ── universe snapshots (cheap, whole-market) ─────────────────────────
def _kr_snapshot() -> pd.DataFrame:
    """Whole-market KR cheap snapshot (symbol/name/price/marketcap/change_pct)."""

    def produce() -> pd.DataFrame:
        from backend.sources import kr_listing_snapshot

        base = kr_listing_snapshot()
        if base.empty:
            return pd.DataFrame()
        out = base.reset_index()[
            ["symbol", "name", "price", "marketcap", "change_pct"]
        ].copy()
        out["market"] = "KR"
        from backend.universe import _kr_sectors

        secmap = _kr_sectors()
        out["sector"] = out["symbol"].map(lambda s: secmap.get(s, "기타"))
        return out

    return cache_df("snapshot:KR", _SNAP_TTL, produce)


def _us_snapshot() -> pd.DataFrame:
    """US universe (S&P500) — symbol/name/sector; price/marketcap filled per-candidate."""

    def produce() -> pd.DataFrame:
        import FinanceDataReader as fdr

        raw = fdr.StockListing("S&P500")
        sym = "Symbol" if "Symbol" in raw.columns else raw.columns[0]
        name = "Name" if "Name" in raw.columns else sym
        out = pd.DataFrame(
            {"symbol": raw[sym].astype(str), "name": raw[name].astype(str)}
        )
        if "Sector" in raw.columns:
            from backend.universe import US_SECTOR_KO

            out["sector"] = (
                raw["Sector"].astype(str).map(lambda s: US_SECTOR_KO.get(s, s))
            )
        else:
            out["sector"] = "기타"
        out["market"] = "US"
        return out

    return cache_df("snapshot:US", _SNAP_TTL, produce)


# ── per-candidate fundamentals ───────────────────────────────────────
def _kr_fund_row(symbol: str, marketcap: float | None) -> dict[str, float | None]:
    """PER/PBR/ROE for one KR stock from DART statements + market cap."""
    from datetime import datetime

    from backend.dart import kr_financials

    if not marketcap:
        return {}
    for year in (datetime.now().year - 1, datetime.now().year - 2):
        fin = kr_financials(symbol, year)
        ni = fin.get("net_income") if fin else None
        eq = fin.get("equity") if fin else None
        if ni or eq:
            return {
                "per": (marketcap / ni) if (ni and ni > 0) else None,
                "pbr": (marketcap / eq) if (eq and eq > 0) else None,
                "roe": fin.get("roe"),
            }
    return {}


def _us_fund_row(symbol: str) -> dict[str, float | None]:
    try:
        import yfinance as yf

        info = yf.Ticker(symbol).info or {}
        roe = _f(info.get("returnOnEquity"))
        return {
            "per": _f(info.get("trailingPE")),
            "pbr": _f(info.get("priceToBook")),
            "roe": roe * 100.0 if roe is not None else None,
            "price": _f(info.get("currentPrice")) or _f(info.get("regularMarketPrice")),
            "marketcap": _f(info.get("marketCap")),
        }
    except Exception:  # noqa: BLE001
        return {}


# ── filter evaluation ────────────────────────────────────────────────
def _passes(value: float | None, f: ScreenFilter) -> bool:
    if f.op == "true":
        return bool(value)
    if value is None:
        return False
    if f.op == "lt":
        return value < (f.value or 0)
    if f.op == "lte":
        return value <= (f.value or 0)
    if f.op == "gt":
        return value > (f.value or 0)
    if f.op == "gte":
        return value >= (f.value or 0)
    if f.op == "between":
        return (f.value or 0) <= value <= (f.value2 or 0)
    return False


def _num(v: object) -> float | None:
    try:
        if v is None:
            return None
        x = float(v)
        return None if (x != x) else x  # NaN check
    except (TypeError, ValueError):
        return None


def _apply(df: pd.DataFrame, filters: list[ScreenFilter]) -> pd.DataFrame:
    """Row-filter that is safe on empty frames (preserves columns)."""
    for f in filters:
        if f.field not in df.columns or df.empty:
            if df.empty:
                break
            continue
        mask = df[f.field].map(lambda v, f=f: _passes(_num(v), f)).astype(bool)
        df = df.loc[mask]
    return df


# ── main ─────────────────────────────────────────────────────────────
def run_screen(spec: ScreenSpec) -> ScreenResult:
    notes: list[str] = []
    cheap_f = [f for f in spec.filters if f.field in _CHEAP_FIELDS]
    fund_f = [f for f in spec.filters if f.field in _FUNDAMENTAL_FIELDS]
    tech_f = [f for f in spec.filters if f.field in _TECHNICAL_FIELDS]

    df = _kr_snapshot() if spec.market == "KR" else _us_snapshot()
    if df.empty:
        return ScreenResult(
            rows=[],
            scanned=0,
            note="데이터를 불러오지 못했습니다. 잠시 후 다시 시도하세요.",
        )
    scanned = len(df)

    # 0) sector filter (whole universe, cheap — both markets carry a 'sector' column)
    if spec.sector and "sector" in df.columns:
        key = spec.sector.strip()
        matched = df[df["sector"].astype(str).str.contains(key, na=False)]
        if matched.empty:  # loose fallback: match on any keyword token
            tok = re.split(r"[·/\s]", key)[0]
            matched = df[df["sector"].astype(str).str.contains(tok, na=False)]
        if not matched.empty:
            df = matched
        else:
            notes.append(f"'{key}' 섹터와 일치하는 종목이 없어 전체에서 검색했습니다.")

    # 1) cheap filters on the whole market (only KR has cheap cols pre-filled)
    if spec.market == "KR":
        df = _apply(df, cheap_f)

    # 2) narrow to a bounded candidate pool (by market cap when available)
    if "marketcap" in df.columns and df["marketcap"].notna().any():
        df = df.sort_values("marketcap", ascending=False)
    pool = df.head(_POOL_CAP).copy()
    if len(df) > _POOL_CAP and (fund_f or tech_f):
        notes.append(
            f"재무·기술 지표는 시총 상위 {_POOL_CAP}종목 후보군에 대해 계산했습니다."
        )

    # 3) per-candidate fundamentals (PER/PBR/ROE), if needed
    if fund_f or spec.market == "US":
        per, pbr, roe, price_u, mcap_u = [], [], [], [], []
        for _, r in pool.iterrows():
            sym = str(r["symbol"])
            if spec.market == "KR":
                d = _kr_fund_row(sym, _num(r.get("marketcap")))
            else:
                d = _us_fund_row(sym)
            per.append(d.get("per"))
            pbr.append(d.get("pbr"))
            roe.append(d.get("roe"))
            price_u.append(d.get("price"))
            mcap_u.append(d.get("marketcap"))
        pool["per"], pool["pbr"], pool["roe"] = per, pbr, roe
        if spec.market == "US":
            pool["price"] = price_u
            pool["marketcap"] = mcap_u
        pool = _apply(pool, fund_f)

    # 4) per-candidate technicals
    if tech_f:
        pool = _add_technical(pool, {f.field for f in tech_f})
        pool = _apply(pool, tech_f)

    # 5) rank
    if spec.mode == "score" and spec.filters:
        score = pd.Series(0.0, index=pool.index)
        for f in spec.filters:
            if f.field in pool.columns:
                score += (
                    pool[f.field].map(
                        lambda v, f=f: 1.0 if _passes(_num(v), f) else 0.0
                    )
                    * f.weight
                )
        pool = pool.assign(__score=score).sort_values("__score", ascending=False)
    elif "marketcap" in pool.columns and pool["marketcap"].notna().any():
        pool = pool.sort_values("marketcap", ascending=False)

    rows: list[ScreenRow] = []
    for _, r in pool.head(spec.limit).iterrows():
        rows.append(
            ScreenRow(
                symbol=str(r["symbol"]),
                name=str(r.get("name", r["symbol"])),
                market=spec.market,
                price=_num(r.get("price")),
                per=_num(r.get("per")),
                pbr=_num(r.get("pbr")),
                roe=_num(r.get("roe")),
                score=_num(r.get("__score")),
            )
        )
    return ScreenResult(rows=rows, scanned=scanned, note=" ".join(notes) or None)


def _add_technical(df: pd.DataFrame, need: set[str]) -> pd.DataFrame:
    """Compute above_ma200 / rsi / ret_1y for candidate rows from cached OHLCV."""
    above, rsi_vals, ret1y = [], [], []
    for sym in df["symbol"]:
        try:
            hist = get_ohlcv_df(str(sym), "2y", "1d")
            close = hist["Close"] if not hist.empty else pd.Series(dtype=float)
        except Exception:  # noqa: BLE001
            close = pd.Series(dtype=float)
        if len(close) >= 200:
            above.append(1.0 if close.iloc[-1] > sma(close, 200).iloc[-1] else 0.0)
        else:
            above.append(None)
        rsi_vals.append(float(rsi_series(close).iloc[-1]) if len(close) >= 15 else None)
        ret1y.append(
            float(close.iloc[-1] / close.iloc[-252] - 1.0) * 100.0
            if len(close) >= 252
            else None
        )
    if "above_ma200" in need:
        df["above_ma200"] = above
    if "rsi" in need:
        df["rsi"] = rsi_vals
    if "ret_1y" in need:
        df["ret_1y"] = ret1y
    return df
