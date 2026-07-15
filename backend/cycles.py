"""Industry / economic-cycle (sector-rotation) analysis — key-free, price-driven.

For each industry theme (반도체·조선·2차전지·방산 …) we build an equal-weight price index
from a small basket, then read its cycle phase the way a trend trader does:

  phase = f(가격 vs 200일선, 모멘텀 가속/감속)
    • 확장(Expansion) : 가격>200MA & 모멘텀 가속  🟢
    • 둔화(Slowdown)  : 가격>200MA & 모멘텀 감속  🟡
    • 회복(Recovery)  : 가격<200MA & 모멘텀 가속  🔵
    • 침체(Contraction): 가격<200MA & 모멘텀 감속  🔴

We also compute relative strength vs the market (KOSPI / S&P500) so you can see which
industry is leading the rotation. NO LLM, NO API key — just FDR OHLCV + arithmetic.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd

from backend.cache import cache_json
from backend.indicators import sma
from backend.schema import CyclePoint, CycleResult, CycleTheme
from backend.sources import get_ohlcv_df

_BENCH = {"KR": "KS11", "US": "US500"}
_BENCH_NAME = {"KR": "KOSPI", "US": "S&P500"}

# ── industry theme baskets (대표 종목, 동일가중) ──────────────────────
KR_THEMES: list[tuple[str, str, list[str]]] = [
    ("semi", "반도체", ["005930", "000660", "042700", "240810", "357780", "058470"]),
    ("ship", "조선", ["009540", "010140", "042660", "010620", "075580"]),
    ("battery", "2차전지", ["373220", "006400", "247540", "086520", "066970"]),
    ("auto", "자동차", ["005380", "000270", "012330", "161390"]),
    ("defense", "방산", ["012450", "047810", "079550", "064350"]),
    ("bio", "제약·바이오", ["207940", "068270", "196170", "145020"]),
    ("steel", "철강·소재", ["005490", "004020", "103140"]),
    ("chem", "화학", ["051910", "011170", "010950", "285130"]),
    ("internet", "인터넷·게임", ["035420", "035720", "251270", "036570"]),
    ("finance", "금융", ["105560", "055550", "086790", "316140"]),
    ("nuclear", "원전·에너지", ["034020", "051600", "052690"]),
    ("entertainment", "엔터·미디어", ["352820", "041510", "122870"]),
]
US_THEMES: list[tuple[str, str, list[str]]] = [
    ("semi", "반도체", ["NVDA", "AVGO", "AMD", "ASML", "LRCX", "KLAC", "AMAT"]),
    ("bigtech", "빅테크", ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]),
    ("ai_soft", "AI·소프트웨어", ["NOW", "CRWD", "PLTR", "SNOW", "PANW"]),
    ("ev", "전기차·모빌리티", ["TSLA", "RIVN", "GM", "F"]),
    ("defense", "방산", ["LMT", "RTX", "NOC", "GD"]),
    ("bio", "제약·바이오", ["LLY", "PFE", "GILD", "AMGN", "MRK"]),
    ("energy", "에너지", ["XOM", "CVX", "COP", "SLB"]),
    ("finance", "금융", ["JPM", "BAC", "GS", "MS", "WFC"]),
    ("consumer", "소비재", ["COST", "WMT", "MCD", "NKE"]),
    ("healthcare", "헬스케어", ["UNH", "JNJ", "ABBV", "TMO"]),
]
_THEMES = {"KR": KR_THEMES, "US": US_THEMES}

_PHASE = {
    "expansion": ("확장", "🟢"),
    "slowdown": ("둔화", "🟡"),
    "recovery": ("회복", "🔵"),
    "contraction": ("침체", "🔴"),
}


def _ret(close: pd.Series, days: int) -> float | None:
    if len(close) <= days:
        return None
    return float(close.iloc[-1] / close.iloc[-days - 1] - 1.0) * 100.0


def _theme_index(members: list[str], max_workers: int = 5) -> pd.Series:
    """Equal-weight, normalized-to-100 price index across the basket (inner-joined dates)."""
    frames: dict[str, pd.DataFrame] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(get_ohlcv_df, sym, "2y", "1d"): sym for sym in members
        }
        for future in as_completed(futures):
            sym = futures[future]
            try:
                frames[sym] = future.result()
            except Exception:  # noqa: BLE001
                continue
    cols = {
        sym: frames[sym]["Close"]
        for sym in members
        if sym in frames and not frames[sym].empty and len(frames[sym]) >= 60
    }
    if not cols:
        return pd.Series(dtype=float)
    px = pd.DataFrame(cols).dropna()
    if px.empty:
        return pd.Series(dtype=float)
    norm = px / px.iloc[0] * 100.0
    return norm.mean(axis=1)


def _classify(close: pd.Series, bench_ret_3m: float | None) -> dict:
    price = float(close.iloc[-1])
    ma200 = sma(close, 200).iloc[-1] if len(close) >= 200 else None
    above = bool(price > ma200) if (ma200 is not None and not pd.isna(ma200)) else None

    ret_1m, ret_3m, ret_6m, ret_12m = (_ret(close, d) for d in (21, 63, 126, 252))
    # momentum acceleration: 최근 1M 추세 vs 그 이전 1M 추세
    prev_1m = None
    if len(close) > 42:
        prev_1m = float(close.iloc[-22] / close.iloc[-43] - 1.0) * 100.0
    accel = (ret_1m - prev_1m) if (ret_1m is not None and prev_1m is not None) else None
    accelerating = (accel is not None and accel > 0) or (
        ret_3m is not None and ret_3m > 0 and accel is None
    )

    if above is True and accelerating:
        phase = "expansion"
    elif above is True and not accelerating:
        phase = "slowdown"
    elif above is False and accelerating:
        phase = "recovery"
    else:
        phase = "contraction"

    rs_3m = (
        (ret_3m - bench_ret_3m)
        if (ret_3m is not None and bench_ret_3m is not None)
        else None
    )
    return {
        "phase": phase,
        "above_ma200": above,
        "accel": accel,
        "ret_1m": ret_1m,
        "ret_3m": ret_3m,
        "ret_6m": ret_6m,
        "ret_12m": ret_12m,
        "rs_3m": rs_3m,
    }


def _price_score(c: dict) -> float:
    base = {"expansion": 75, "recovery": 65, "slowdown": 45, "contraction": 25}[
        c["phase"]
    ]
    rs = c.get("rs_3m") or 0.0
    base += max(-15.0, min(15.0, rs * 0.5))  # relative strength tilt
    if c.get("ret_3m") is not None:
        base += max(-10.0, min(10.0, c["ret_3m"] * 0.2))
    return max(0.0, min(100.0, base))


def _theme_fundamentals(
    members: list[str], market: str, max_workers: int = 5
) -> dict:
    """Aggregate member fundamentals → earnings-momentum & valuation axes (reuses _metrics)."""
    import backend.recommend as R
    from backend.sources import kr_listing_snapshot

    snap = kr_listing_snapshot() if market == "KR" else None
    metrics: dict[str, dict[str, float | None] | None] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(R._metrics, sym, market, snap): sym for sym in members
        }
        for future in as_completed(futures):
            sym = futures[future]
            try:
                metrics[sym] = future.result()
            except Exception:  # noqa: BLE001
                metrics[sym] = None

    rev, opm, per, pbr = [], [], [], []
    for sym in members:
        m = metrics.get(sym)
        if not m:
            continue
        if m.get("rev_growth") is not None:
            rev.append(m["rev_growth"])
        if m.get("op_margin") is not None:
            opm.append(m["op_margin"])
        if m.get("per") is not None:
            per.append(m["per"])
        if m.get("pbr") is not None:
            pbr.append(m["pbr"])

    def _avg(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    avg_rev, avg_opm, avg_per, avg_pbr = _avg(rev), _avg(opm), _avg(per), _avg(pbr)
    # earnings momentum score: 매출성장(-10~30%) + 영업이익률(0~25%)
    e_parts = []
    if avg_rev is not None:
        e_parts.append(max(0.0, min(100.0, (avg_rev + 10) / 40 * 100)))
    if avg_opm is not None:
        e_parts.append(max(0.0, min(100.0, avg_opm / 25 * 100)))
    earnings_score = sum(e_parts) / len(e_parts) if e_parts else None
    # valuation attractiveness: cheaper PER/PBR → higher (mean-reversion / cycle position)
    v_parts = []
    if avg_per is not None and avg_per > 0:
        v_parts.append(max(0.0, min(100.0, (40 - avg_per) / 35 * 100)))
    if avg_pbr is not None and avg_pbr > 0:
        v_parts.append(max(0.0, min(100.0, (6 - avg_pbr) / 5.5 * 100)))
    valuation_score = sum(v_parts) / len(v_parts) if v_parts else None
    return {
        "earnings_score": earnings_score,
        "valuation_score": valuation_score,
        "avg_per": avg_per,
        "avg_op_margin": avg_opm,
        "avg_rev_growth": avg_rev,
    }


def _composite_score(price_s: float, f: dict) -> float:
    """Blend price (0.45) + earnings (0.35) + valuation (0.20), renormalized over available."""
    pairs = [
        (price_s, 0.45),
        (f.get("earnings_score"), 0.35),
        (f.get("valuation_score"), 0.20),
    ]
    present = [(v, w) for v, w in pairs if v is not None]
    tot = sum(w for _, w in present)
    return round(sum(v * w for v, w in present) / tot, 1) if tot else round(price_s, 1)


def _comment(name: str, c: dict, f: dict) -> str:
    label, _ = _PHASE[c["phase"]]
    bits = [f"{name} {label} 국면"]
    if c.get("rs_3m") is not None:
        bits.append(
            "시장 대비 강세"
            if c["rs_3m"] > 2
            else "시장 대비 약세"
            if c["rs_3m"] < -2
            else "시장과 동행"
        )
    # earnings support / drag
    es = f.get("earnings_score")
    if es is not None:
        if es >= 65:
            bits.append("이익이 추세를 뒷받침")
        elif es <= 35:
            bits.append("이익 모멘텀 약화(가격이 펀더멘털을 앞섬)")
    # valuation nuance — expensive + slowdown = late-cycle warning
    vs = f.get("valuation_score")
    if vs is not None and vs <= 25 and c["phase"] in ("expansion", "slowdown"):
        bits.append("밸류에이션 부담(사이클 후반 주의)")
    elif vs is not None and vs >= 70 and c["phase"] in ("recovery", "contraction"):
        bits.append("밸류 저평가(저점 매력)")
    return " · ".join(bits)


def _fund_note(f: dict) -> str:
    parts = []
    if f.get("avg_rev_growth") is not None:
        parts.append(f"평균 매출성장 {f['avg_rev_growth']:+.0f}%")
    if f.get("avg_op_margin") is not None:
        parts.append(f"영업이익률 {f['avg_op_margin']:.0f}%")
    if f.get("avg_per") is not None:
        parts.append(f"평균 PER {f['avg_per']:.0f}")
    return " · ".join(parts) if parts else "재무 데이터 제한"


def _leaders(members: list[str], market: str, max_workers: int = 5) -> list[str]:
    from backend.universe import name_of

    frames: dict[str, pd.DataFrame] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(get_ohlcv_df, sym, "1y", "1d"): sym for sym in members
        }
        for future in as_completed(futures):
            sym = futures[future]
            try:
                frames[sym] = future.result()
            except Exception:  # noqa: BLE001
                continue
    scored: list[tuple[float, str]] = []
    for sym in members:
        df = frames.get(sym)
        if df is not None and not df.empty and len(df) >= 63:
            scored.append((_ret(df["Close"], 63) or -999, name_of(sym)))
    scored.sort(reverse=True)
    return [n for _, n in scored[:3]]


def _build(market: str, max_workers: int = 5) -> dict:
    bench_close = get_ohlcv_df(_BENCH[market], "2y", "1d")
    bench_ret_3m = _ret(bench_close["Close"], 63) if not bench_close.empty else None

    themes: list[CycleTheme] = []
    for key, name, members in _THEMES[market]:
        idx = _theme_index(members, max_workers=max_workers)
        if idx.empty or len(idx) < 60:
            continue
        c = _classify(idx, bench_ret_3m)
        f = _theme_fundamentals(members, market, max_workers=max_workers)
        price_s = _price_score(c)
        label, emoji = _PHASE[c["phase"]]
        curve = [
            CyclePoint(time=ts.strftime("%Y-%m-%d"), value=round(float(v), 2))
            for ts, v in idx.tail(252).items()
        ]
        themes.append(
            CycleTheme(
                key=key,
                name=name,
                phase=label,
                phase_emoji=emoji,
                ret_1m=_r(c["ret_1m"]),
                ret_3m=_r(c["ret_3m"]),
                ret_6m=_r(c["ret_6m"]),
                ret_12m=_r(c["ret_12m"]),
                rs_3m=_r(c["rs_3m"]),
                above_ma200=c["above_ma200"],
                momentum_accel=_r(c["accel"]),
                price_score=round(price_s, 1),
                earnings_score=_r(f.get("earnings_score")),
                valuation_score=_r(f.get("valuation_score")),
                avg_per=_r(f.get("avg_per")),
                avg_op_margin=_r(f.get("avg_op_margin")),
                avg_rev_growth=_r(f.get("avg_rev_growth")),
                score=_composite_score(price_s, f),
                leaders=_leaders(members, market, max_workers=max_workers),
                index_curve=curve,
                comment=_comment(name, c, f),
                fund_note=_fund_note(f),
                members=members,
            )
        )
    themes.sort(key=lambda t: t.score, reverse=True)
    return CycleResult(
        market=market,
        benchmark=_BENCH_NAME[market],
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        themes=themes,
        note="산업 테마를 4축으로 진단합니다 — 가격 모멘텀(추세·200일선·상대강도) + 이익 모멘텀(매출성장·영업이익률) "
        "+ 밸류에이션 위치(PER·PBR). 가격은 후행지표라 이익·밸류로 사이클 후반/저점을 보정합니다. 투자 권유가 아닙니다.",
    ).model_dump()


def _r(v: float | None) -> float | None:
    return None if v is None else round(v, 1)


def cycles(market: str) -> CycleResult:
    market = "US" if market.upper() == "US" else "KR"
    data = cache_json(
        f"cycles:{market}", ttl_sec=6 * 3600, producer=lambda: _build(market)
    )
    return CycleResult(**data)
