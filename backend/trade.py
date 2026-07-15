"""Position sizing / risk calculator — the core of trade execution.

Implements R-based sizing (risk a fixed % of the account per trade) with ATR / price / %
stops, per finance/risk-management-sizing.md. Key-free: pulls price + ATR from cached OHLCV.
"""

from __future__ import annotations

import math

from fastapi import HTTPException

from backend.indicators import atr
from backend.schema import PositionRequest, PositionResult
from backend.sources import currency_of, detect_market, get_ohlcv_df


def size_position(req: PositionRequest) -> PositionResult:
    if req.account <= 0 or req.risk_pct <= 0:
        raise HTTPException(
            status_code=400, detail="계좌 크기와 리스크%는 0보다 커야 합니다."
        )

    market = detect_market(req.symbol) if req.symbol else "KR"
    currency = currency_of(market)
    atr_val: float | None = None
    entry = req.entry

    # entry & ATR from data when a symbol is given
    if req.symbol:
        df = get_ohlcv_df(req.symbol, "6mo", "1d")
        if not df.empty:
            if entry is None:
                entry = float(df["Close"].iloc[-1])
            if len(df) >= 15:
                atr_val = float(atr(df, 14).iloc[-1])
    if entry is None or entry <= 0:
        raise HTTPException(
            status_code=400,
            detail="진입가를 입력하거나, 데이터가 있는 종목을 지정하세요.",
        )

    is_long = req.direction != "short"

    # determine stop
    if req.stop_mode == "price":
        if req.stop_price is None:
            raise HTTPException(
                status_code=400, detail="손절가(stop_price)를 입력하세요."
            )
        stop = req.stop_price
    elif req.stop_mode == "pct":
        if req.stop_pct is None:
            raise HTTPException(
                status_code=400, detail="손절 %(stop_pct)를 입력하세요."
            )
        stop = (
            entry * (1 - req.stop_pct / 100.0)
            if is_long
            else entry * (1 + req.stop_pct / 100.0)
        )
    else:  # atr
        if atr_val is None:
            raise HTTPException(
                status_code=400,
                detail="ATR 손절은 데이터가 있는 종목이 필요합니다. 손절 방식을 가격/%로 바꾸세요.",
            )
        stop = (
            entry - req.atr_mult * atr_val
            if is_long
            else entry + req.atr_mult * atr_val
        )

    risk_per_share = abs(entry - stop)
    if risk_per_share <= 0:
        raise HTTPException(
            status_code=400, detail="손절가가 진입가와 같습니다. 손절 폭을 확인하세요."
        )

    risk_amount = req.account * req.risk_pct / 100.0
    shares = int(math.floor(risk_amount / risk_per_share))
    position_value = shares * entry
    target = (
        entry + req.rr * risk_per_share if is_long else entry - req.rr * risk_per_share
    )
    reward_amount = shares * abs(target - entry)

    note = None
    if position_value > req.account:
        note = (
            "계산된 투입금액이 계좌를 초과합니다 — 손절 폭이 너무 좁거나 리스크%가 큽니다. "
            "실제로는 계좌 한도 내에서만 매수하세요."
        )

    return PositionResult(
        symbol=req.symbol,
        entry=round(entry, 4),
        stop=round(stop, 4),
        target=round(target, 4),
        risk_per_share=round(risk_per_share, 4),
        shares=shares,
        position_value=round(position_value, 2),
        position_pct=round(position_value / req.account * 100.0, 1),
        risk_amount=round(risk_amount, 2),
        reward_amount=round(reward_amount, 2),
        rr=req.rr,
        atr=(round(atr_val, 4) if atr_val is not None else None),
        currency=currency,
        note=note,
    )
