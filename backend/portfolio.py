"""Watchlist compare, portfolio analytics, and simple strategy backtests.

Risk metrics (CAGR/MDD/Sharpe/vol) follow finance/risk-metrics.md; backtest pitfalls
(signal lag, costs) follow finance/backtesting.md — signals are shifted to avoid look-ahead.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from backend.indicators import rsi as rsi_series
from backend.indicators import sma
from backend.schema import (
    BacktestRequest,
    BacktestResult,
    BtTrade,
    CompareResult,
    CompareSeries,
    LinePoint,
    PortfolioAnalysis,
    PortfolioPosition,
    PortfolioRequest,
)
from backend.sources import currency_of, detect_market, get_ohlcv_df
from backend.universe import name_of

_TRADING_DAYS = 252


# ── shared metrics ───────────────────────────────────────────────────
def _curve(series: pd.Series) -> list[LinePoint]:
    return [
        LinePoint(time=ts.strftime("%Y-%m-%d"), value=float(v))
        for ts, v in series.items()
        if pd.notna(v)
    ]


def _metrics(value: pd.Series) -> dict[str, float | None]:
    value = value.dropna()
    if len(value) < 2 or value.iloc[0] <= 0:
        return {"cagr": None, "mdd": None, "sharpe": None, "vol": None}
    ret = value.pct_change().dropna()
    years = len(value) / _TRADING_DAYS
    cagr = (value.iloc[-1] / value.iloc[0]) ** (1 / years) - 1 if years > 0 else None
    vol = float(ret.std() * math.sqrt(_TRADING_DAYS)) if ret.std() > 0 else None
    sharpe = (
        float(ret.mean() / ret.std() * math.sqrt(_TRADING_DAYS))
        if ret.std() > 0
        else None
    )
    mdd = float((value / value.cummax() - 1).min())
    return {"cagr": _pc(cagr), "mdd": _pc(mdd), "sharpe": sharpe, "vol": _pc(vol)}


# ── compare (normalized to 100) ──────────────────────────────────────
def compare(symbols: list[str], period: str) -> CompareResult:
    series: list[CompareSeries] = []
    for sym in symbols:
        df = get_ohlcv_df(sym, period, "1d")
        if df.empty:
            continue
        close = df["Close"].dropna()
        norm = close / close.iloc[0] * 100.0
        series.append(CompareSeries(symbol=sym, name=name_of(sym), data=_curve(norm)))
    return CompareResult(series=series)


# ── portfolio ────────────────────────────────────────────────────────
def analyze_portfolio(req: PortfolioRequest) -> PortfolioAnalysis:
    if not req.holdings:
        return PortfolioAnalysis(
            positions=[],
            total_value=0.0,
            currency="",
            equity_curve=[],
            note="보유 종목이 없습니다.",
        )
    markets = {detect_market(h.symbol) for h in req.holdings}
    currency = currency_of(next(iter(markets))) if len(markets) == 1 else "MIXED"

    prices: dict[str, pd.Series] = {}
    positions: list[PortfolioPosition] = []
    total = 0.0
    for h in req.holdings:
        df = get_ohlcv_df(h.symbol, req.period, "1d")
        if df.empty:
            positions.append(
                PortfolioPosition(
                    symbol=h.symbol,
                    name=name_of(h.symbol),
                    shares=h.shares,
                    price=None,
                    value=None,
                )
            )
            continue
        close = df["Close"].dropna()
        prices[h.symbol] = close
        last = float(close.iloc[-1])
        value = last * h.shares
        total += value
        ret = ((last / h.avg_price - 1) * 100.0) if h.avg_price else None
        positions.append(
            PortfolioPosition(
                symbol=h.symbol,
                name=name_of(h.symbol),
                shares=h.shares,
                price=last,
                value=value,
                ret_pct=ret,
            )
        )
    for p in positions:
        p.weight = (p.value / total * 100.0) if (p.value and total) else None

    note = (
        "여러 통화(KR+US)가 섞여 평가액은 통화 환산 없이 단순 합산입니다."
        if currency == "MIXED"
        else None
    )
    equity_curve: list[LinePoint] = []
    metrics: dict[str, float | None] = {
        "cagr": None,
        "mdd": None,
        "sharpe": None,
        "vol": None,
    }
    if prices:
        px = pd.DataFrame(prices).sort_index().ffill().dropna()
        shares = {h.symbol: h.shares for h in req.holdings}
        port_val = sum(px[s] * shares.get(s, 0) for s in px.columns)
        equity_curve = _curve(port_val)
        metrics = _metrics(port_val)

    return PortfolioAnalysis(
        positions=positions,
        total_value=total,
        currency=currency,
        equity_curve=equity_curve,
        cagr=metrics["cagr"],
        mdd=metrics["mdd"],
        sharpe=metrics["sharpe"],
        vol=metrics["vol"],
        note=note,
    )


# ── backtest ─────────────────────────────────────────────────────────
def backtest(req: BacktestRequest) -> BacktestResult:
    df = get_ohlcv_df(req.symbol, req.period, "1d")
    if df.empty or len(df) < 60:
        return BacktestResult(
            symbol=req.symbol,
            strategy=req.strategy,
            equity_curve=[],
            benchmark_curve=[],
            note="데이터가 부족합니다.",
        )
    close = df["Close"].dropna()
    ret = close.pct_change().fillna(0.0)

    if req.strategy == "buy_hold":
        position = pd.Series(1.0, index=close.index)
    elif req.strategy == "rsi_revert":
        r = rsi_series(close, 14)
        position = pd.Series(np.nan, index=close.index)
        position[r < req.rsi_buy] = 1.0
        position[r > req.rsi_sell] = 0.0
        position = position.ffill().fillna(0.0)
    else:  # ma_cross
        fast, slow = sma(close, req.fast), sma(close, req.slow)
        position = (fast > slow).astype(float)

    pos_lag = position.shift(1).fillna(0.0)  # trade next bar — no look-ahead
    trade_spans = _completed_trade_spans(pos_lag)
    transaction_sides = pd.Series(0.0, index=pos_lag.index)
    for entry_i, exit_i in trade_spans:
        transaction_sides.iloc[entry_i] += 1.0
        transaction_sides.iloc[exit_i] += 1.0
    # cost_bps is round-trip cost, so each transaction side pays half.
    cost = transaction_sides * (req.cost_bps / 20000.0)
    strat_ret = pos_lag * ret - cost

    equity = (1 + strat_ret).cumprod() * 100.0
    benchmark = (1 + ret).cumprod() * 100.0

    m = _metrics(equity)
    trades_list = _build_trades(trade_spans, close, strat_ret)
    trades = len(trades_list)
    win_rate = (
        _pc(sum(trade.ret_pct > 0 for trade in trades_list) / trades)
        if trades
        else None
    )

    return BacktestResult(
        symbol=req.symbol,
        strategy=req.strategy,
        equity_curve=_curve(equity),
        benchmark_curve=_curve(benchmark),
        cagr=m["cagr"],
        mdd=m["mdd"],
        sharpe=m["sharpe"],
        trades=trades,
        win_rate=win_rate,
        trades_list=trades_list,
    )


def _completed_trade_spans(pos_lag: pd.Series) -> list[tuple[int, int]]:
    """Pair long entries and exits, closing a final open position at the last bar."""
    spans: list[tuple[int, int]] = []
    entry_i: int | None = None
    prev = 0.0
    for i in range(len(pos_lag)):
        cur = float(pos_lag.iloc[i])
        if prev <= 0 and cur > 0:
            entry_i = i
        elif prev > 0 and cur <= 0 and entry_i is not None:
            spans.append((entry_i, i))
            entry_i = None
        prev = cur
    # An open final position counts as closed at the last bar for statistics.
    if entry_i is not None:
        spans.append((entry_i, len(pos_lag) - 1))
    return spans


def _build_trades(
    trade_spans: list[tuple[int, int]],
    close: pd.Series,
    strat_ret: pd.Series,
) -> list[BtTrade]:
    """Derive discrete long trades from position transitions (long-only strategies).

    Entry when pos_lag goes 0→>0 (buy at that bar's close), exit when >0→0 (sell at
    that bar's close). A position still open at the last bar is closed at the final
    close. An open position at the end counts as one trade closed at the last bar
    for statistics purposes. Returns compound the same net-of-cost daily returns
    used by the equity curve.
    """
    idx: list[pd.Timestamp] = list(close.index)
    return [
        _mk_trade(close, strat_ret, idx, entry_i, exit_i)
        for entry_i, exit_i in trade_spans
    ]


def _mk_trade(
    close: pd.Series,
    strat_ret: pd.Series,
    idx: list[pd.Timestamp],
    entry_i: int,
    exit_i: int,
) -> BtTrade:
    ep = float(close.iloc[entry_i])
    xp = float(close.iloc[exit_i])
    ret = float((1.0 + strat_ret.iloc[entry_i : exit_i + 1]).prod() - 1.0) * 100.0
    return BtTrade(
        entry_date=idx[entry_i].strftime("%Y-%m-%d"),
        exit_date=idx[exit_i].strftime("%Y-%m-%d"),
        entry_price=round(ep, 4),
        exit_price=round(xp, 4),
        ret_pct=ret,
    )


def _pc(v: float | None) -> float | None:
    if v is None:
        return None
    f = float(v) * 100.0
    return None if (f != f) else round(f, 2)
