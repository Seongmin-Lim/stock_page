"""Chart / technical read — CODE detects the signals, LLM only narrates them.

Following the plotDigitizer principle (never hand a chart image to the model and let it
guess numbers): we compute every technical state in code (MA stack, MACD cross, RSI,
Bollinger position, support/resistance, 52w position) and pass that structured truth to
Gemini, which writes a plain-Korean read + breakout/breakdown scenarios. Falls back to a
code-only bias when no key.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from backend.indicators import bollinger, ema, macd, rsi, sma
from backend.schema import ChartRead, TechSignal
from backend.sources import detect_market, get_ohlcv_df
from backend.universe import name_of


def _swing_levels(close: pd.Series) -> tuple[float | None, float | None]:
    """Nearest support (below) / resistance (above) from recent swing pivots."""
    try:
        from scipy.signal import argrelextrema

        win = close.tail(180).to_numpy()
        if len(win) < 20:
            return None, None
        hi_idx = argrelextrema(win, np.greater, order=5)[0]
        lo_idx = argrelextrema(win, np.less, order=5)[0]
        price = win[-1]
        res = [win[i] for i in hi_idx if win[i] > price]
        sup = [win[i] for i in lo_idx if win[i] < price]
        resistance = min(res) if res else None
        support = max(sup) if sup else None
        return (
            float(support) if support else None,
            float(resistance) if resistance else None,
        )
    except Exception:  # noqa: BLE001 - scipy optional / short series
        return None, None


def _signals(df: pd.DataFrame) -> tuple[list[TechSignal], int]:
    close = df["Close"].dropna()
    price = float(close.iloc[-1])
    sig: list[TechSignal] = []
    net = 0

    ma20 = sma(close, 20).iloc[-1]
    ma60 = sma(close, 60).iloc[-1]
    ma120 = sma(close, 120).iloc[-1] if len(close) >= 120 else np.nan
    # MA stack / 정배열
    if not pd.isna(ma20) and not pd.isna(ma60):
        if price > ma20 > ma60 and (pd.isna(ma120) or ma60 > ma120):
            sig.append(
                TechSignal(
                    label="이동평균", state="bullish", detail="정배열(가격>MA20>MA60)"
                )
            )
            net += 1
        elif price < ma20 < ma60:
            sig.append(
                TechSignal(
                    label="이동평균", state="bearish", detail="역배열(가격<MA20<MA60)"
                )
            )
            net -= 1
        else:
            sig.append(
                TechSignal(
                    label="이동평균", state="neutral", detail="혼조(배열 불명확)"
                )
            )

    # MA cross (golden/dead) in last 5 bars
    f, s = sma(close, 20), sma(close, 60)
    if len(close) >= 61:
        diff = (f - s).dropna()
        recent = diff.tail(6)
        if recent.iloc[0] <= 0 < recent.iloc[-1]:
            sig.append(
                TechSignal(
                    label="MA 교차",
                    state="bullish",
                    detail="최근 골든크로스(MA20↑MA60)",
                )
            )
            net += 1
        elif recent.iloc[0] >= 0 > recent.iloc[-1]:
            sig.append(
                TechSignal(
                    label="MA 교차",
                    state="bearish",
                    detail="최근 데드크로스(MA20↓MA60)",
                )
            )
            net -= 1

    # MACD
    line, signal, hist = macd(close)
    if not pd.isna(hist.iloc[-1]):
        h, hp = hist.iloc[-1], hist.iloc[-2]
        if h > 0 and hp <= 0:
            sig.append(
                TechSignal(
                    label="MACD", state="bullish", detail="시그널 상향 돌파(매수 전환)"
                )
            )
            net += 1
        elif h < 0 and hp >= 0:
            sig.append(
                TechSignal(
                    label="MACD", state="bearish", detail="시그널 하향 이탈(매도 전환)"
                )
            )
            net -= 1
        else:
            sig.append(
                TechSignal(
                    label="MACD",
                    state="bullish" if h > 0 else "bearish",
                    detail=("0선 위(상승 우위)" if h > 0 else "0선 아래(하락 우위)"),
                )
            )
            net += 1 if h > 0 else -1

    # RSI
    r = rsi(close).iloc[-1]
    if not pd.isna(r):
        if r >= 70:
            sig.append(
                TechSignal(
                    label="RSI", state="bearish", detail=f"과매수({r:.0f}) — 단기 과열"
                )
            )
            net -= 1
        elif r <= 30:
            sig.append(
                TechSignal(
                    label="RSI",
                    state="bullish",
                    detail=f"과매도({r:.0f}) — 반등 가능권",
                )
            )
            net += 1
        else:
            sig.append(
                TechSignal(label="RSI", state="neutral", detail=f"중립({r:.0f})")
            )

    # Bollinger position
    up, mid, low = bollinger(close)
    if not pd.isna(up.iloc[-1]):
        if price >= up.iloc[-1]:
            sig.append(
                TechSignal(
                    label="볼린저",
                    state="bearish",
                    detail="상단 밴드 돌파(과열·되돌림 주의)",
                )
            )
            net -= 1
        elif price <= low.iloc[-1]:
            sig.append(
                TechSignal(
                    label="볼린저", state="bullish", detail="하단 밴드 터치(반등 주시)"
                )
            )
            net += 1
        else:
            sig.append(
                TechSignal(
                    label="볼린저", state="neutral", detail="밴드 내 (중심선 부근)"
                )
            )

    # 200MA trend filter
    ma200 = sma(close, 200).iloc[-1] if len(close) >= 200 else np.nan
    if not pd.isna(ma200):
        if price > ma200:
            sig.append(
                TechSignal(
                    label="장기추세", state="bullish", detail="200일선 위(상승 추세)"
                )
            )
            net += 1
        else:
            sig.append(
                TechSignal(
                    label="장기추세", state="bearish", detail="200일선 아래(하락 추세)"
                )
            )
            net -= 1

    # 52-week position
    if len(close) >= 252:
        hi52, lo52 = close.tail(252).max(), close.tail(252).min()
        pos = (price - lo52) / (hi52 - lo52) * 100 if hi52 > lo52 else 50
        if pos >= 90:
            sig.append(
                TechSignal(
                    label="52주 위치", state="bullish", detail=f"신고가권({pos:.0f}%)"
                )
            )
        elif pos <= 15:
            sig.append(
                TechSignal(
                    label="52주 위치", state="bearish", detail=f"저점권({pos:.0f}%)"
                )
            )
        else:
            sig.append(
                TechSignal(
                    label="52주 위치", state="neutral", detail=f"중간({pos:.0f}%)"
                )
            )

    return sig, net


def read_chart(symbol: str) -> ChartRead:
    market = detect_market(symbol)
    df = get_ohlcv_df(symbol, "2y", "1d")
    name = name_of(symbol)
    if df.empty or len(df) < 60:
        return ChartRead(
            symbol=symbol,
            name=name,
            market=market,
            generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
    price = float(df["Close"].iloc[-1])
    sig, net = _signals(df)
    support, resistance = _swing_levels(df["Close"].dropna())
    bias = "매수우위" if net >= 2 else "매도우위" if net <= -2 else "중립"

    llm_read = _llm_chart(name, market, price, sig, support, resistance, bias)
    return ChartRead(
        symbol=symbol,
        name=name,
        market=market,
        price=price,
        signals=sig,
        support=support,
        resistance=resistance,
        bias=bias,
        bias_score=net,
        llm_read=llm_read,
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def _llm_chart(name, market, price, sig, support, resistance, bias) -> str | None:
    from backend import llm

    if not llm.available():
        return None
    lines = "\n".join(f"- {s.label}: {s.state} ({s.detail})" for s in sig)
    lvl = []
    if support:
        lvl.append(f"지지 {support:,.0f}")
    if resistance:
        lvl.append(f"저항 {resistance:,.0f}")
    data = (
        f"종목: {name} ({market}), 현재가 {price:,.0f}\n"
        f"코드가 감지한 기술적 신호:\n{lines}\n"
        f"주요 레벨: {', '.join(lvl) or '미상'}\n"
        f"코드 종합 바이어스: {bias}"
    )
    system = (
        "너는 한국 주식 트레이더를 돕는 기술적 분석가다. 아래 '코드가 감지한 신호'만 근거로 "
        "3~4문장의 한국어 차트 해석을 써라. 규칙: (1) 주어진 신호·레벨·가격만 사용하고 새 수치를 "
        "지어내지 마라. (2) 현재 차트 상태를 한 줄로 요약한 뒤, '저항 돌파 시'와 '지지 이탈 시' "
        "두 시나리오를 제시하라. (3) 매수/매도 단정 금지, 관찰·대응 위주. (4) 마지막에 '대응: ...' "
        "한 줄로 트레이딩 대응(예: 손절 기준·관찰 레벨)을 제시."
    )
    key = f"chart:{name}:{round(price)}:{bias}:{len(sig)}"
    return llm.comment(prompt=data, system=system, cache_key=key, ttl=1800)
