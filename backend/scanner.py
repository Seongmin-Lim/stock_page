"""Whole-market turnaround scanner — find the *next* SanDisk BEFORE it runs.

Two stages so a several-hundred-symbol sweep stays affordable:

  • Stage 1 (price-only, cheap): pull cached daily OHLCV for every symbol in the
    universe pool and compute only the reversal inputs (ret_1y / ret_3m / prox52 /
    above200 / reclaimed_200 / vol_ratio) — the same quantities recommend._metrics
    derives. Rank by recommend._reversal_score, drop names that already ran
    (ret_3m > 60), and keep the top ~60 finalists.

  • Stage 2 (fundamentals, expensive): for the finalists only, call
    recommend._metrics (DART for KR / yfinance for US) to add value/financial and a
    clean reversal score, blend with TURNAROUND_WEIGHTS, and emit RecoPick rows.

The result (top 40) is cached 12h; `limit` is applied AFTER the cache so one warm
cache serves any limit ≤ stored. The first scan can take several minutes.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd

from backend.cache import cache_json
from backend.indicators import sma
from backend.recommend import (
    TURNAROUND_WEIGHTS,
    _fin_note,
    _metrics,
    _reversal_score,
    _turnaround_rationale,
    _turnaround_sw,
)
from backend.schema import RecoPick, TurnScanResult
from backend.sources import get_ohlcv_df, kr_listing_snapshot
from backend.universe import name_of, sector_of

# Stage-1 pool caps and finalist count — module-level so tests can shrink them.
_POOL_KR = 350  # top KR names by market cap taken into stage 1
_KR_MIN_MARKETCAP = 1e11  # 1000억: skip micro-caps (illiquid, noisy)
_FINALISTS = 60  # survivors of stage 1 that get full fundamentals
_STORE_TOP = 40  # rows persisted in cache (limit applied after)
_RAN_RET_3M = 60.0  # drop obvious "already ran" names before ranking

_MIN_ROWS = 120  # need enough history for a meaningful reversal read


# ── stage 1: price-only reversal inputs (mirrors recommend._metrics) ──
def _reversal_inputs(symbol: str) -> dict[str, float | bool | None] | None:
    df = get_ohlcv_df(symbol, "2y", "1d")
    if df.empty or len(df) < _MIN_ROWS:
        return None
    close = df["Close"].dropna()
    if len(close) < _MIN_ROWS:
        return None
    price = float(close.iloc[-1])

    ret_1y = (price / close.iloc[-252] - 1) * 100.0 if len(close) >= 252 else None
    ret_3m = (price / close.iloc[-63] - 1) * 100.0 if len(close) >= 63 else None
    prox52 = price / close.tail(252).max() * 100.0

    ma200_series = sma(close, 200) if len(close) >= 200 else None
    above200 = None
    reclaimed_200: bool | None = None
    if ma200_series is not None and not pd.isna(ma200_series.iloc[-1]):
        ma200 = float(ma200_series.iloc[-1])
        above200 = (price / ma200 - 1) * 100.0 if ma200 else None
        # price > 200DMA now AND was below it within the last 60 bars
        win = close.tail(60)
        ma_win = ma200_series.tail(60)
        was_below = bool((win < ma_win).any())
        reclaimed_200 = bool(price > ma200 and was_below)

    vol_ratio = None
    if "Volume" in df.columns and len(df) >= 60:
        v = df["Volume"].dropna()
        recent, prior = v.tail(20).mean(), v.tail(60).mean()
        vol_ratio = float(recent / prior) if prior and prior > 0 else None

    return {
        "ret_1y": ret_1y,
        "ret_3m": ret_3m,
        "prox52": prox52,
        "above200": above200,
        "reclaimed_200": reclaimed_200,
        "vol_ratio": vol_ratio,
    }


def _stage1_pool(market: str, kr_snap: pd.DataFrame) -> list[str]:
    """Universe → stage-1 candidate symbols."""
    if market == "KR":
        if kr_snap is None or kr_snap.empty:
            return []
        df = kr_snap[kr_snap["marketcap"].fillna(0) >= _KR_MIN_MARKETCAP]
        df = df.sort_values("marketcap", ascending=False)
        return [str(s) for s in df.index[:_POOL_KR]]
    # US: whole S&P500 snapshot is the stage-1 pool
    from backend.screener import _us_snapshot

    snap = _us_snapshot()
    if snap is None or snap.empty:
        return []
    return [str(s) for s in snap["symbol"].tolist()]


def _build(market: str, max_workers: int = 5) -> dict:
    kr_snap = kr_listing_snapshot() if market == "KR" else pd.DataFrame()
    pool = _stage1_pool(market, kr_snap)
    pool_n = len(pool)

    # ── stage 1: rank the pool by reversal score (price-only) ─────────
    stage1: dict[str, dict[str, float | bool | None] | None] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_reversal_inputs, sym): sym for sym in pool}
        for future in as_completed(futures):
            sym = futures[future]
            try:
                stage1[sym] = future.result()
            except Exception:  # noqa: BLE001 - batch builds skip failed symbols
                stage1[sym] = None

    ranked: list[tuple[str, float]] = []
    scanned = 0
    for sym in pool:
        inp = stage1.get(sym)
        if inp is None:
            continue
        scanned += 1
        # drop obvious "already ran" names before ranking
        if inp["ret_3m"] is not None and inp["ret_3m"] > _RAN_RET_3M:
            continue
        rs = _reversal_score(
            inp["ret_1y"],
            inp["ret_3m"],
            inp["prox52"],
            inp["above200"],
            inp["reclaimed_200"],
            inp["vol_ratio"],
        )
        ranked.append((sym, rs))
    ranked.sort(key=lambda x: x[1], reverse=True)
    finalists = [sym for sym, _ in ranked[:_FINALISTS]]

    # ── stage 2: full fundamentals for finalists only ────────────────
    stage2: dict[str, dict[str, float | None] | None] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_metrics, sym, market, kr_snap): sym for sym in finalists
        }
        for future in as_completed(futures):
            sym = futures[future]
            try:
                stage2[sym] = future.result()
            except Exception:  # noqa: BLE001 - batch builds skip failed symbols
                stage2[sym] = None

    picks: list[RecoPick] = []
    for sym in finalists:
        m = stage2.get(sym)
        if m is None:
            continue
        tw = TURNAROUND_WEIGHTS
        score = (
            tw["value"] * m["value"]
            + tw["financial"] * m["financial"]
            + tw["reversal"] * m["reversal"]
        )
        strengths, weaknesses = _turnaround_sw(m)
        picks.append(
            RecoPick(
                symbol=sym,
                name=name_of(sym),
                market=market,
                category="turnaround_scan",
                sector=sector_of(sym, market),
                score=round(score, 1),
                price=m["price"],
                change_pct=m["change_pct"],
                per=m["per"],
                pbr=m["pbr"],
                roe=(round(m["roe"], 1) if m["roe"] is not None else None),
                ret_1y=(round(m["ret_1y"], 1) if m["ret_1y"] is not None else None),
                momentum=round(m["momentum"], 0),
                trend=round(m["trend"], 0),
                value=round(m["value"], 0),
                quality=round(m["quality"], 0),
                financial=round(m["financial"], 0),
                rationale=_turnaround_rationale(m),
                fin_note=_fin_note(m),
                strengths=strengths,
                weaknesses=weaknesses,
            )
        )
    picks.sort(key=lambda p: p.score, reverse=True)
    picks = picks[:_STORE_TOP]

    note = (
        f"전 시장 스캔: 유니버스 {pool_n}종목 중 {scanned}종목의 가격 데이터를 분석해 "
        f"반등 초입 시그널로 상위 {len(finalists)}종목을 추린 뒤, 이들만 재무제표"
        f"(KR: DART, US: yfinance)까지 반영해 최종 {len(picks)}종목을 선정했습니다. "
        "저평가·소외됐다가 실적·사이클이 막 돌아서는 변곡점 종목(샌디스크 패턴)을 겨냥합니다. "
        "최초 스캔은 수 분 걸릴 수 있으며(이후 12시간 캐시), 투자 권유가 아닌 참고용입니다."
    )
    return TurnScanResult(
        picks=picks,
        scanned=scanned,
        pool=pool_n,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        note=note,
    ).model_dump()


def scan_turnaround(market: str, limit: int = 24) -> TurnScanResult:
    market = "US" if market.upper() == "US" else "KR"
    data = cache_json(
        f"turnscan:{market}", ttl_sec=12 * 3600, producer=lambda: _build(market)
    )
    result = TurnScanResult(**data)
    # limit applied AFTER cache so one cache serves any limit ≤ stored
    result.picks = result.picks[: max(1, limit)]
    return result
