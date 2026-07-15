"""AI recommendation tab — a transparent, rule-based multi-factor stock scorer.

Designed from a trader's lens: blend trend-following (momentum + stage analysis) with
value/quality (GARP). Four sub-scores (0–100): momentum, trend, value, quality — combined
with category-specific weights into three buckets the user asked for:

  1) 대형 우량 모멘텀   — famous blue-chips in strong uptrends (momentum/trend heavy)
  2) 저평가 우량주      — well-known but cheap vs quality (value/quality heavy)
  3) 독보적 강소기업    — less famous, dominant profitability (quality/momentum heavy)

Key-free: KR uses the FDR listing snapshot + best-effort pykrx ratios; US uses FDR OHLCV +
yfinance .info per ticker. Universes are curated & bounded (~10/bucket) so it stays fast,
and the whole result is cached for 6h. This is a heuristic aid, NOT investment advice.

NO LLM is involved — every score is deterministic arithmetic. All thresholds/weights live
in the CRITERIA / MOMENTUM_MIX / STAGE_POINTS / _WEIGHTS blocks below; edit those to retune.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from backend.cache import cache_json
from backend.indicators import sma
from backend.schema import RecoCategory, RecoPick, RecoResult, RecoSectorGroup
from backend.sources import _f, get_ohlcv_df, kr_listing_snapshot

# ── curated universes (symbol → display name) ────────────────────────
KR_BLUECHIP = {
    # 반도체·전자
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    # 자동차·기계
    "005380": "현대차",
    "000270": "기아",
    "012330": "현대모비스",
    # IT·소프트웨어
    "035420": "NAVER",
    "035720": "카카오",
    # 화학·소재 / 2차전지
    "051910": "LG화학",
    "006400": "삼성SDI",
    "373220": "LG에너지솔루션",
    # 제약·바이오
    "207940": "삼성바이오로직스",
    "068270": "셀트리온",
    # 철강·소재
    "005490": "POSCO홀딩스",
    # 금융
    "105560": "KB금융",
    "055550": "신한지주",
    # 방산
    "012450": "한화에어로스페이스",
    # 조선
    "009540": "HD한국조선해양",
}
KR_VALUE = {
    # 금융 (저PER·저PBR 대표)
    "105560": "KB금융",
    "055550": "신한지주",
    "086790": "하나금융지주",
    "316140": "우리금융지주",
    "024110": "기업은행",
    # 자동차
    "005380": "현대차",
    "000270": "기아",
    # 철강·소재
    "005490": "POSCO홀딩스",
    "004020": "현대제철",
    # 화학·에너지
    "010950": "S-Oil",
    "011170": "롯데케미칼",
    # 유틸리티·통신
    "015760": "한국전력",
    "030200": "KT",
    "017670": "SK텔레콤",
    # 지주·소비재
    "034730": "SK",
    "033780": "KT&G",
}
KR_NICHE = {
    # 반도체 장비·소재 (강소)
    "042700": "한미반도체",
    "058470": "리노공업",
    "240810": "원익IPS",
    "357780": "솔브레인",
    "095340": "ISC",
    "108320": "LX세미콘",
    "036930": "주성엔지니어링",
    "140860": "파크시스템스",
    "098460": "고영",
    # 2차전지 소재
    "086520": "에코프로",
    "247540": "에코프로비엠",
    "066970": "엘앤에프",
    # 제약·바이오 (독보적)
    "196170": "알테오젠",
    "328130": "루닛",
    "145020": "휴젤",
    # 방산·원전
    "079550": "LIG넥스원",
    "064350": "현대로템",
    "052690": "한전기술",
}
US_BLUECHIP = {
    # IT·기술
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "AVGO": "Broadcom",
    # 커뮤니케이션
    "GOOGL": "Alphabet",
    "META": "Meta",
    # 경기소비재
    "AMZN": "Amazon",
    "TSLA": "Tesla",
    "COST": "Costco",
    # 금융
    "JPM": "JPMorgan",
    "V": "Visa",
    "MA": "Mastercard",
    # 헬스케어
    "LLY": "Eli Lilly",
    "UNH": "UnitedHealth",
    "JNJ": "Johnson & Johnson",
    # 산업재·에너지
    "GE": "GE Aerospace",
    "XOM": "ExxonMobil",
}
US_VALUE = {
    # 금융
    "JPM": "JPMorgan",
    "BAC": "Bank of America",
    "C": "Citigroup",
    "GS": "Goldman Sachs",
    "WFC": "Wells Fargo",
    # 커뮤니케이션 (저평가 통신/미디어)
    "GOOGL": "Alphabet",
    "T": "AT&T",
    "VZ": "Verizon",
    "CMCSA": "Comcast",
    # 헬스케어
    "PFE": "Pfizer",
    "GILD": "Gilead",
    "CVS": "CVS Health",
    # 에너지·소재
    "CVX": "Chevron",
    "XOM": "ExxonMobil",
    # IT (저평가 구가치주)
    "CSCO": "Cisco",
    "INTC": "Intel",
    "IBM": "IBM",
}
US_NICHE = {
    # 반도체 장비·설계 (독보적 해자)
    "ASML": "ASML",
    "LRCX": "Lam Research",
    "KLAC": "KLA",
    "AMAT": "Applied Materials",
    "SNPS": "Synopsys",
    "CDNS": "Cadence",
    "MPWR": "Monolithic Power",
    # 소프트웨어·AI
    "NOW": "ServiceNow",
    "CRWD": "CrowdStrike",
    "PLTR": "Palantir",
    "SNOW": "Snowflake",
    # 헬스케어·산업 강소
    "ISRG": "Intuitive Surgical",
    "AXON": "Axon",
    "FICO": "Fair Isaac",
    # 핀테크·이커머스
    "MELI": "MercadoLibre",
    "SHOP": "Shopify",
}

# 턴어라운드 후보 풀 — "쭉 저평가/소외 → 사이클·실적 전환" 가능성이 있는 종목.
# 경기민감·메모리·소부장·소재·조선 등 사이클 바닥 통과형 위주 (샌디스크 패턴).
KR_TURNAROUND = {
    # 메모리·반도체 사이클
    "000660": "SK하이닉스",
    "005930": "삼성전자",
    "042700": "한미반도체",
    "403870": "HPSP",
    # 디스플레이·소재
    "034220": "LG디스플레이",
    "009830": "한화솔루션",
    "011170": "롯데케미칼",
    "010060": "OCI홀딩스",
    # 철강·조선·기계 (사이클)
    "005490": "POSCO홀딩스",
    "004020": "현대제철",
    "010140": "삼성중공업",
    "042660": "한화오션",
    "009540": "HD한국조선해양",
    "241560": "두산밥캣",
    # 2차전지 소재 (낙폭 과대 → 반등 후보)
    "247540": "에코프로비엠",
    "066970": "엘앤에프",
    "003670": "포스코퓨처엠",
    # 유통·소비 (소외 가치)
    "023530": "롯데쇼핑",
    "069960": "현대백화점",
    "139480": "이마트",
    # 엔터·미디어 (낙폭)
    "352820": "하이브",
    "035900": "JYP Ent.",
}
US_TURNAROUND = {
    # 메모리·반도체 사이클 (샌디스크 = 정확히 이 패턴)
    "SNDK": "SanDisk",
    "MU": "Micron",
    "WDC": "Western Digital",
    "INTC": "Intel",
    "STX": "Seagate",
    "GFS": "GlobalFoundries",
    "ON": "ON Semiconductor",
    "MCHP": "Microchip",
    # 소외 가치·경기민감
    "PYPL": "PayPal",
    "DIS": "Disney",
    "NKE": "Nike",
    "PFE": "Pfizer",
    "F": "Ford",
    "GM": "General Motors",
    "BA": "Boeing",
    # 에너지·소재 (사이클)
    "CVX": "Chevron",
    "DOW": "Dow",
    "MOS": "Mosaic",
    "FCX": "Freeport-McMoRan",
    # 바이오 (낙폭)
    "MRNA": "Moderna",
    "BMY": "Bristol Myers",
}

_BUCKETS = {
    "KR": [
        ("bluechip", KR_BLUECHIP),
        ("value", KR_VALUE),
        ("niche", KR_NICHE),
        ("turnaround", KR_TURNAROUND),
    ],
    "US": [
        ("bluechip", US_BLUECHIP),
        ("value", US_VALUE),
        ("niche", US_NICHE),
        ("turnaround", US_TURNAROUND),
    ],
}
_CATEGORY_META = {
    "bluechip": (
        "대형 우량 모멘텀",
        "유명 대형주 중 추세가 강한 종목 (모멘텀·정배열 중심)",
    ),
    "value": (
        "저평가 우량주",
        "유명하지만 PER·PBR이 낮아 과소평가 가능성 (가치·퀄리티 중심)",
    ),
    "niche": (
        "독보적 강소기업",
        "덜 알려졌지만 높은 수익성·해자를 가진 기업 (퀄리티·모멘텀 중심)",
    ),
    "turnaround": (
        "🐢→🚀 턴어라운드 후보",
        "쭉 저평가·소외됐다가 실적·사이클이 막 돌아서는 변곡점 종목 (샌디스크 패턴: 싸고+이익회복+반등초입+여력)",
    ),
}
# composite weights per bucket: (momentum, trend, value, quality, financial)
# financial = 재무제표 기반 건전성/성장성 (DART/yfinance 실제 재무 반영)
_WEIGHTS = {
    "bluechip": (0.35, 0.25, 0.00, 0.20, 0.20),
    "value": (0.15, 0.00, 0.40, 0.20, 0.25),
    "niche": (0.30, 0.20, 0.00, 0.25, 0.25),
}
# 턴어라운드 종합 가중 (reversal 축 포함, 합=1.0): 싸고+이익회복+막 돌아섬
TURNAROUND_WEIGHTS = {"value": 0.28, "financial": 0.30, "reversal": 0.42}

# ════════════════════════════════════════════════════════════════════════
# 평가 기준 (CRITERIA) — 추천 로직의 "어떤 기준"이 전부 여기 모여 있다.
# 이 블록만 고치면 추천 결과가 바뀐다 (함수 코드는 건드릴 필요 없음).
# 각 (lo, hi)는 선형 점수 구간: 값이 lo면 0점, hi면 100점 (그 사이는 비례).
# ════════════════════════════════════════════════════════════════════════
CRITERIA: dict[str, tuple[float, float]] = {
    # ── 모멘텀 (높을수록 가점): "강한 종목이 더 강하다"
    "ret_1y": (-20.0, 60.0),  # 12개월 수익률(%):  -20%→0점, +60%→100점
    "ret_3m": (-15.0, 30.0),  # 3개월 수익률(%)
    "above200": (-10.0, 25.0),  # 200일선 대비 이격(%): 위로 멀수록 가점
    "prox52": (60.0, 100.0),  # 52주 고가 대비 현재가 위치(%): 신고가 근접 가점
    # ── 가치 (낮을수록 가점): "쌀수록 좋다"
    "per": (5.0, 40.0),  # PER:  5배→100점, 40배→0점 (낮을수록 가점)
    "pbr": (0.5, 6.0),  # PBR:  0.5배→100점, 6배→0점
    # ── 퀄리티 (높을수록 가점): "수익성이 높을수록 좋다"
    "roe": (3.0, 25.0),  # ROE(%):  3%→0점, 25%→100점
    "margin": (5.0, 35.0),  # 순이익률(%) — 미국 종목만 (yfinance 제공)
    # ── 재무 (재무제표 기반): 성장·수익성은 높을수록, 부채는 낮을수록 가점
    "rev_growth": (-10.0, 25.0),  # 매출 성장률(%)
    "op_margin": (0.0, 25.0),  # 영업이익률(%)
    "debt_ratio": (
        200.0,
        30.0,
    ),  # 부채비율(%): 200%→0점, 30%→100점 (낮을수록 가점, 역방향)
}
# 모멘텀 하위지표 가중 (합=1.0). 장기 추세에 더 큰 비중.
MOMENTUM_MIX: dict[str, float] = {
    "ret_1y": 0.40,
    "ret_3m": 0.25,
    "above200": 0.20,
    "prox52": 0.15,
}
# 추세(정배열) 점수 배점 (합=100). 단계가 충족될수록 가점.
STAGE_POINTS = {"above_ma50": 40.0, "ma50_over_ma200": 35.0, "ma200_rising": 25.0}
# 가치·퀄리티 묶음 구성 (어떤 지표를 평균낼지)
VALUE_PARTS = ("per", "pbr")  # 둘 다 "낮을수록 가점"
QUALITY_PARTS = ("roe", "margin")  # 둘 다 "높을수록 가점"
# 비정상 벤더값 제거 범위 (이 밖이면 데이터 오류로 보고 무시)
SANE: dict[str, tuple[float, float]] = {
    "per": (0.0, 500.0),
    "pbr": (0.0, 100.0),
    "roe": (-200.0, 400.0),
    "margin": (-200.0, 100.0),
}
# 데이터가 없을 때 중립 점수 (모름 → 50점)
NEUTRAL = 50.0


# ── scoring helpers ──────────────────────────────────────────────────
def _clamp(x: float) -> float:
    return max(0.0, min(100.0, x))


def _hi(x: float | None, lo: float, hi: float) -> float | None:
    if x is None:
        return None
    return _clamp((x - lo) / (hi - lo) * 100.0)


def _lo(x: float | None, lo: float, hi: float) -> float | None:
    if x is None or x <= 0:
        return None
    return _clamp((hi - x) / (hi - lo) * 100.0)


def _avg(vals: list[float | None], default: float = NEUTRAL) -> float:
    present = [v for v in vals if v is not None]
    return sum(present) / len(present) if present else default


def _wavg(pairs: list[tuple[float | None, float]], default: float = NEUTRAL) -> float:
    """Weighted average over present sub-scores; weights renormalized over what's available."""
    present = [(v, w) for v, w in pairs if v is not None]
    tot = sum(w for _, w in present)
    return sum(v * w for v, w in present) / tot if tot > 0 else default


def _sane_all(per, pbr, roe, margin):  # noqa: ANN001 - tuple in/out of floats|None
    """Drop implausible vendor values (e.g. yfinance priceToBook=1714 for some ADRs)."""

    def s(v: float | None, key: str) -> float | None:
        lo, hi = SANE[key]
        return None if (v is None or v <= lo or v > hi) else v

    return s(per, "per"), s(pbr, "pbr"), s(roe, "roe"), s(margin, "margin")


# ── per-symbol metrics ───────────────────────────────────────────────
def _us_fundamentals(symbol: str) -> dict[str, float | None]:
    try:
        import yfinance as yf

        info = yf.Ticker(symbol).info or {}
        roe = _f(info.get("returnOnEquity"))
        margin = _f(info.get("profitMargins"))
        growth = _f(info.get("revenueGrowth"))
        opm = _f(info.get("operatingMargins"))
        d2e = _f(info.get("debtToEquity"))  # already a percent in yfinance
        return {
            "per": _f(info.get("trailingPE")),
            "pbr": _f(info.get("priceToBook")),
            "roe": roe * 100.0 if roe is not None else None,
            "margin": margin * 100.0 if margin is not None else None,
            "rev_growth": growth * 100.0 if growth is not None else None,
            "op_margin": opm * 100.0 if opm is not None else None,
            "debt_ratio": d2e,
        }
    except Exception:  # noqa: BLE001
        return {}


def _kr_financials_factor(symbol: str) -> dict[str, float | None]:
    """Latest available KR statements (DART) → growth / op-margin / debt-ratio + net income & equity."""
    from datetime import datetime

    from backend.dart import kr_financials

    for year in (datetime.now().year - 1, datetime.now().year - 2):
        f = kr_financials(symbol, year)
        if f and f.get("revenue"):
            return {
                "rev_growth": f.get("revenue_growth"),
                "op_margin": f.get("operating_margin"),
                "debt_ratio": f.get("debt_ratio"),
                "roe_dart": f.get("roe"),
                "net_income": f.get("net_income"),
                "equity": f.get("equity"),
            }
    return {}


def _metrics(
    symbol: str, market: str, kr_snap: pd.DataFrame
) -> dict[str, float | None] | None:
    df = get_ohlcv_df(symbol, "2y", "1d")
    if df.empty or len(df) < 60:
        return None
    close = df["Close"].dropna()
    price = float(close.iloc[-1])
    ma50 = sma(close, 50).iloc[-1]
    ma200 = sma(close, 200).iloc[-1] if len(close) >= 200 else None
    ma200_prev = sma(close, 200).iloc[-22] if len(close) >= 222 else None

    ret_1y = (price / close.iloc[-252] - 1) * 100.0 if len(close) >= 252 else None
    ret_3m = (price / close.iloc[-63] - 1) * 100.0 if len(close) >= 63 else None
    prox52 = price / close.tail(252).max() * 100.0
    above200 = (price / ma200 - 1) * 100.0 if ma200 and not pd.isna(ma200) else None

    # turnaround inputs: did price recently reclaim its 200DMA? is volume picking up?
    ma200_series = sma(close, 200) if len(close) >= 200 else None
    reclaimed_200 = None
    if ma200_series is not None and not pd.isna(ma200_series.iloc[-1]):
        above_now = price > ma200_series.iloc[-1]
        win = close.tail(60)
        ma_win = ma200_series.tail(60)
        was_below = bool((win < ma_win).any())
        reclaimed_200 = bool(above_now and was_below)
    vol_ratio = None
    if "Volume" in df.columns and len(df) >= 60:
        v = df["Volume"].dropna()
        recent, prior = v.tail(20).mean(), v.tail(60).mean()
        vol_ratio = float(recent / prior) if prior and prior > 0 else None

    per = pbr = roe = margin = None
    rev_growth = op_margin = debt_ratio = None
    change_pct = None
    if market == "US":
        f = _us_fundamentals(symbol)
        per, pbr, roe, margin = (
            f.get("per"),
            f.get("pbr"),
            f.get("roe"),
            f.get("margin"),
        )
        rev_growth, op_margin, debt_ratio = (
            f.get("rev_growth"),
            f.get("op_margin"),
            f.get("debt_ratio"),
        )
    else:
        marketcap = None
        if kr_snap is not None and not kr_snap.empty and symbol in kr_snap.index:
            row = kr_snap.loc[symbol]
            change_pct = _f(row.get("change_pct"))
            marketcap = _f(row.get("marketcap"))
        from backend.sources import _kr_fundamentals

        kf = _kr_fundamentals(symbol)
        per, pbr = kf.get("PER"), kf.get("PBR")
        eps, bps = kf.get("EPS"), kf.get("BPS")
        if eps and bps:
            roe = eps / bps * 100.0
        # DART financial statements → growth / margin / leverage (+ PER/PBR fallback)
        df_fin = _kr_financials_factor(symbol)
        rev_growth, op_margin, debt_ratio = (
            df_fin.get("rev_growth"),
            df_fin.get("op_margin"),
            df_fin.get("debt_ratio"),
        )
        if roe is None and df_fin.get("roe_dart") is not None:
            roe = df_fin["roe_dart"]
        # pykrx PER/PBR is frequently blocked → derive from DART + market cap
        ni, eq = df_fin.get("net_income"), df_fin.get("equity")
        if per is None and marketcap and ni and ni > 0:
            per = marketcap / ni
        if pbr is None and marketcap and eq and eq > 0:
            pbr = marketcap / eq

    # drop implausible vendor multiples (ranges in SANE)
    per, pbr, roe, margin = _sane_all(per, pbr, roe, margin)

    raw = {
        "ret_1y": ret_1y,
        "ret_3m": ret_3m,
        "above200": above200,
        "prox52": prox52,
        "per": per,
        "pbr": pbr,
        "roe": roe,
        "margin": margin,
        "rev_growth": rev_growth,
        "op_margin": op_margin,
        "debt_ratio": debt_ratio,
    }

    # ── sub-scores, all driven by CRITERIA ──────────────────────────
    momentum = _wavg(
        [(_hi(raw[k], *CRITERIA[k]), MOMENTUM_MIX[k]) for k in MOMENTUM_MIX]
    )
    trend = 0.0
    if not pd.isna(ma50):
        trend += STAGE_POINTS["above_ma50"] if price > ma50 else 0.0
    if ma200 and not pd.isna(ma200):
        trend += STAGE_POINTS["ma50_over_ma200"] if ma50 > ma200 else 0.0
        if ma200_prev and not pd.isna(ma200_prev):
            trend += STAGE_POINTS["ma200_rising"] if ma200 > ma200_prev else 0.0
    value = _avg([_lo(raw[k], *CRITERIA[k]) for k in VALUE_PARTS])
    quality = _avg([_hi(raw[k], *CRITERIA[k]) for k in QUALITY_PARTS])
    # 재무: 성장·영업이익률(높을수록)·부채비율(낮을수록, CRITERIA가 역방향이라 _hi 사용)
    financial = _avg(
        [_hi(raw[k], *CRITERIA[k]) for k in ("rev_growth", "op_margin", "debt_ratio")]
    )

    reversal = _reversal_score(
        ret_1y, ret_3m, prox52, above200, reclaimed_200, vol_ratio
    )

    return {
        "price": price,
        "change_pct": change_pct,
        "per": per,
        "pbr": pbr,
        "roe": roe,
        "rev_growth": rev_growth,
        "op_margin": op_margin,
        "debt_ratio": debt_ratio,
        "ret_1y": ret_1y,
        "ret_3m": ret_3m,
        "prox52": prox52,
        "above200": above200,
        "vol_ratio": vol_ratio,
        "reclaimed_200": reclaimed_200,
        "momentum": momentum,
        "trend": trend,
        "value": value,
        "quality": quality,
        "financial": financial,
        "reversal": reversal,
    }


def _reversal_score(
    ret_1y, ret_3m, prox52, above200, reclaimed_200, vol_ratio
) -> float:
    """0~100: how cleanly is this a *bottom-turning* setup (not already-run, not still-dead)?"""
    parts: list[float] = []
    # 1) 바닥에서 막 돌아서는 단기 반등 (3M이 살짝 +가 이상적, 너무 크면 이미 감)
    if ret_3m is not None:
        if ret_3m < 0:
            parts.append(_clamp((ret_3m + 20) / 20 * 60))  # -20%→0, 0%→60
        else:
            parts.append(_clamp(100 - (ret_3m - 8) * 2.5))  # 8%→100, 그 이상 감점
    # 2) 오래 눌려있었나 (12M이 약세/횡보일수록 '소외→전환' 매력; 이미 급등(+)이면 늦음)
    if ret_1y is not None:
        parts.append(_clamp((25 - ret_1y) / 65 * 100))  # -40%→100, +25%→0
    # 3) 200일선 회복 변곡
    if reclaimed_200 is True:
        parts.append(95.0)
    elif above200 is not None:
        parts.append(70.0 if -8 <= above200 <= 8 else (35.0 if above200 > 8 else 25.0))
    # 4) 거래량 유입 (관심 돌아옴)
    if vol_ratio is not None:
        parts.append(_clamp((vol_ratio - 0.8) / 0.7 * 100))  # 0.8→0, 1.5→100
    # 5) 아직 신고가 아님 (상승 여력)
    if prox52 is not None:
        parts.append(
            _clamp(100 - abs(prox52 - 60) * 2.2)
        )  # 60% 부근 최적, 신고가/저점 둘다 감점
    return _avg(parts) if parts else NEUTRAL


def _rationale(m: dict[str, float | None]) -> str:
    parts: list[str] = []
    if m["ret_1y"] is not None:
        parts.append(f"12M {m['ret_1y']:+.0f}%")
    if m["trend"] and m["trend"] >= 75:
        parts.append("정배열")
    elif m["trend"] and m["trend"] >= 40:
        parts.append("추세 양호")
    if m["per"] is not None:
        parts.append(f"PER {m['per']:.0f}")
    if m["pbr"] is not None:
        parts.append(f"PBR {m['pbr']:.1f}")
    if m["roe"] is not None:
        parts.append(f"ROE {m['roe']:.0f}%")
    return " · ".join(parts) if parts else "데이터 제한"


def _fin_note(m: dict[str, float | None]) -> str:
    """One-line financial-statement highlight."""
    parts: list[str] = []
    if m.get("rev_growth") is not None:
        parts.append(f"매출성장 {m['rev_growth']:+.0f}%")
    if m.get("op_margin") is not None:
        parts.append(f"영업이익률 {m['op_margin']:.0f}%")
    if m.get("debt_ratio") is not None:
        parts.append(f"부채비율 {m['debt_ratio']:.0f}%")
    return " · ".join(parts) if parts else "재무 데이터 제한"


def _turnaround_rationale(m: dict[str, float | None]) -> str:
    parts: list[str] = []
    if m.get("ret_1y") is not None:
        parts.append(f"12M {m['ret_1y']:+.0f}%")
    if m.get("ret_3m") is not None:
        parts.append(f"3M {m['ret_3m']:+.0f}%")
    if m.get("reclaimed_200"):
        parts.append("200일선 회복")
    if m.get("vol_ratio") is not None and m["vol_ratio"] > 1.1:
        parts.append(f"거래량 {m['vol_ratio']:.1f}배")
    if m.get("per") is not None:
        parts.append(f"PER {m['per']:.0f}")
    if m.get("rev_growth") is not None:
        parts.append(f"매출 {m['rev_growth']:+.0f}%")
    return " · ".join(parts) if parts else "데이터 제한"


def _turnaround_sw(m: dict[str, float | None]) -> tuple[list[str], list[str]]:
    s: list[str] = []
    w: list[str] = []
    if (m.get("value") or 0) >= 60:
        s.append("저평가(소외)")
    if (m.get("financial") or 0) >= 60:
        s.append("실적 개선")
    if m.get("reclaimed_200"):
        s.append("200일선 회복(변곡)")
    if m.get("vol_ratio") is not None and m["vol_ratio"] > 1.2:
        s.append("거래량 유입")
    if m.get("ret_3m") is not None and m["ret_3m"] > 30:
        w.append("이미 단기 급등(추격 주의)")
    if (m.get("financial") or 100) <= 35:
        w.append("실적 아직 미회복")
    if m.get("prox52") is not None and m["prox52"] >= 90:
        w.append("신고가권(여력 적음)")
    return s[:3], w[:2]


def _strengths_weaknesses(m: dict[str, float | None]) -> tuple[list[str], list[str]]:
    """Auto-summarize each pick into trader-readable strengths / weaknesses."""
    s: list[str] = []
    w: list[str] = []
    checks = [
        ("momentum", 70, 35, "강한 모멘텀", "모멘텀 약함"),
        ("trend", 75, 30, "정배열 추세", "추세 이탈"),
        ("value", 65, 30, "저평가 매력", "밸류 부담"),
        ("quality", 70, 35, "높은 수익성", "수익성 낮음"),
        ("financial", 70, 35, "탄탄한 재무", "재무 취약"),
    ]
    for key, hi, lo, good, bad in checks:
        v = m.get(key)
        if v is None:
            continue
        if v >= hi:
            s.append(good)
        elif v <= lo:
            w.append(bad)
    return s[:3], w[:3]


# ── build ────────────────────────────────────────────────────────────
def _group_by_sector(
    picks: list[RecoPick], per_sector: int = 6
) -> list[RecoSectorGroup]:
    """Group all picks by sector and keep the top `per_sector` of each (score-sorted)."""
    buckets: dict[str, list[RecoPick]] = {}
    for p in picks:
        buckets.setdefault(p.sector or "기타", []).append(p)
    groups = [
        RecoSectorGroup(
            sector=sec,
            picks=sorted(ps, key=lambda x: x.score, reverse=True)[:per_sector],
        )
        for sec, ps in buckets.items()
    ]
    # sectors ordered by their best pick's score
    groups.sort(key=lambda g: g.picks[0].score if g.picks else 0, reverse=True)
    return groups


def _build(market: str) -> dict:
    from backend.universe import sector_of

    kr_snap = kr_listing_snapshot() if market == "KR" else pd.DataFrame()
    categories: list[dict] = []
    for key, universe in _BUCKETS[market]:
        is_turn = key == "turnaround"
        if not is_turn:
            wm, wt, wv, wq, wf = _WEIGHTS[key]
        picks: list[RecoPick] = []
        for symbol, name in universe.items():
            m = _metrics(symbol, market, kr_snap)
            if m is None:
                continue
            if is_turn:
                tw = TURNAROUND_WEIGHTS
                score = (
                    tw["value"] * m["value"]
                    + tw["financial"] * m["financial"]
                    + tw["reversal"] * m["reversal"]
                )
                rationale = _turnaround_rationale(m)
                strengths, weaknesses = _turnaround_sw(m)
            else:
                score = (
                    wm * m["momentum"]
                    + wt * m["trend"]
                    + wv * m["value"]
                    + wq * m["quality"]
                    + wf * m["financial"]
                )
                rationale = _rationale(m)
                strengths, weaknesses = _strengths_weaknesses(m)
            picks.append(
                RecoPick(
                    symbol=symbol,
                    name=name,
                    market=market,
                    category=key,
                    sector=sector_of(symbol, market),
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
                    rationale=rationale,
                    fin_note=_fin_note(m),
                    strengths=strengths,
                    weaknesses=weaknesses,
                )
            )
        picks.sort(key=lambda p: p.score, reverse=True)
        title, subtitle = _CATEGORY_META[key]
        categories.append(
            RecoCategory(
                key=key,
                title=title,
                subtitle=subtitle,
                picks=picks,  # full list (flat, score-sorted)
                sectors=_group_by_sector(picks),  # grouped, up to 6 per sector
            ).model_dump()
        )

    return RecoResult(
        market=market,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        categories=[RecoCategory(**c) for c in categories],
        note="규칙 기반 점수(모멘텀·추세·가치·퀄리티·재무)로 큐레이션된 유니버스를 분야(섹터)별로 분류·정렬했습니다. "
        "'턴어라운드 후보'는 저평가+실적회복+반등초입(reversal) 조합으로 별도 산정합니다. "
        "재무는 실제 재무제표(KR: DART, US: yfinance) 반영. 투자 권유가 아닌 참고용입니다.",
    ).model_dump()


def recommend(market: str) -> RecoResult:
    market = "US" if market.upper() == "US" else "KR"
    data = cache_json(
        f"reco:{market}", ttl_sec=6 * 3600, producer=lambda: _build(market)
    )
    return RecoResult(**data)
