"""Deterministic historical replay for the live auto-trade decision core."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from backend.autotrade import Action, OpenPosition, SymbolSnapshot, enforce_risk_limits, evaluate
from backend.portfolio import _metrics
from backend.schema import (
    AutotradeConfig,
    LinePoint,
    ReplayAttribution,
    ReplayJournalTrade,
    ReplayPeriod,
    ReplayRegimeStats,
    ReplayReport,
    ReplayRuleStats,
    ReplaySummary,
)
from backend.sources import get_ohlcv_df


@dataclass
class _Holding:
    symbol: str
    qty: int
    entry_date: str
    entry_price: float
    entry_rule: str
    entry_inputs: dict[str, float | int | bool | str]
    regime_above_ma200: bool
    risk_per_share: float


@dataclass
class _Pending:
    action: Action
    decision_date: pd.Timestamp
    regime_above_ma200: bool


@dataclass
class _Trade:
    holding: _Holding
    exit_date: str | None = None
    exit_price: float | None = None
    exit_rule: str | None = None
    exit_inputs: dict[str, float | int | bool | str] | None = None


def replay(
    universe: list[str],
    start: str,
    end: str,
    config: AutotradeConfig,
    cost_bps: float = 15.0,
) -> ReplayReport:
    """Replay live decisions with past-only snapshots and next-open fills."""
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    if start_date >= end_date:
        raise ValueError("시작일은 종료일보다 빨라야 합니다.")
    if not 1 <= len(universe) <= 20:
        raise ValueError("리플레이 종목은 1개 이상 20개 이하여야 합니다.")
    if cost_bps < 0:
        raise ValueError("거래 비용은 0 이상이어야 합니다.")
    config_values = config.model_dump()
    config_values["universe"] = list(universe)
    strategy_config = AutotradeConfig(**config_values)
    frames = {symbol: _clean_frame(get_ohlcv_df(symbol, "max", "1d")) for symbol in universe}
    index_frame = _clean_frame(get_ohlcv_df("KS11", "max", "1d"))
    days = _trading_days(frames, start_date, end_date)
    return _run(days, frames, index_frame, strategy_config, start, end, cost_bps)


def _clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    cleaned = frame.copy()
    cleaned.index = pd.to_datetime(cleaned.index).normalize()
    cleaned = cleaned[~cleaned.index.duplicated(keep="last")].sort_index()
    return cleaned


def _trading_days(
    frames: dict[str, pd.DataFrame], start: date, end: date
) -> list[pd.Timestamp]:
    dates: set[pd.Timestamp] = set()
    lower = pd.Timestamp(start)
    upper = pd.Timestamp(end)
    for frame in frames.values():
        dates.update(ts for ts in frame.index if lower <= ts <= upper)
    return sorted(dates)


def _run(
    days: list[pd.Timestamp],
    frames: dict[str, pd.DataFrame],
    index_frame: pd.DataFrame,
    config: AutotradeConfig,
    start: str,
    end: str,
    cost_bps: float,
) -> ReplayReport:
    cash = config.capital
    holdings: dict[str, _Holding] = {}
    pending: dict[str, _Pending] = {}
    trades: list[_Trade] = []
    equity_values: list[float] = []
    equity_dates: list[pd.Timestamp] = []
    gate_blocks = 0
    risk_blocks = 0
    side_cost = cost_bps / 20_000.0

    for day in days:
        cash, realized_today = _fill_pending(
            day, pending, holdings, trades, frames, cash, side_cost
        )
        regime_ok = _regime_ok(index_frame, day)
        snapshots = _snapshots(frames, day, regime_ok)
        positions = [
            OpenPosition(symbol=symbol, qty=item.qty, entry_price=item.entry_price)
            for symbol, item in sorted(holdings.items())
        ]
        today_pnl = realized_today + _daily_pnl(day, holdings, frames)
        actions = evaluate(snapshots, positions, config)
        accepted, refused, _ = enforce_risk_limits(actions, positions, config, today_pnl)
        gate_blocks += sum(action["rule"] == "regime_gate_flat" for action in refused)
        risk_blocks += sum(
            action["rule"] in {"risk_halt", "max_positions", "position_exists"}
            for action in refused
        )
        for action in accepted:
            symbol = action["symbol"]
            if symbol not in pending:
                pending[symbol] = _Pending(action, day, regime_ok)
        equity_dates.append(day)
        equity_values.append(_equity(day, cash, holdings, frames))

    final_equity = equity_values[-1] if equity_values else config.capital
    journal = _journal(trades, holdings, frames, days, config.capital)
    equity_series = pd.Series(equity_values, index=equity_dates, dtype=float)
    return _report(
        start, end, config, cost_bps, journal, equity_series, final_equity,
        gate_blocks, risk_blocks,
    )


def _fill_pending(
    day: pd.Timestamp,
    pending: dict[str, _Pending],
    holdings: dict[str, _Holding],
    trades: list[_Trade],
    frames: dict[str, pd.DataFrame],
    cash: float,
    side_cost: float,
) -> tuple[float, float]:
    realized_today = 0.0
    ready = [
        (symbol, item)
        for symbol, item in pending.items()
        if day > item.decision_date and day in frames[symbol].index
    ]
    ready.sort(key=lambda pair: (pair[1].action["side"] != "sell", pair[0]))
    for symbol, item in ready:
        action = item.action
        open_price = float(frames[symbol].at[day, "Open"])
        if action["side"] == "sell":
            holding = holdings.pop(symbol, None)
            if holding is not None:
                fill_price = open_price * (1.0 - side_cost)
                cash += holding.qty * fill_price
                previous = frames[symbol].loc[
                    frames[symbol].index < day, "Close"
                ]
                if not previous.empty:
                    realized_today += (
                        fill_price - float(previous.iloc[-1])
                    ) * holding.qty
                trades.append(
                    _Trade(
                        holding,
                        day.strftime("%Y-%m-%d"),
                        fill_price,
                        action["rule"],
                        dict(action["inputs"]),
                    )
                )
        elif symbol not in holdings and open_price > 0:
            fill_price = open_price * (1.0 + side_cost)
            qty = min(action["qty"], int(cash // fill_price))
            if qty > 0:
                cash -= qty * fill_price
                latest = float(action["inputs"].get("latest_price", 0.0))
                stop = float(action["inputs"].get("stop_price", latest))
                risk = max(latest - stop, 0.0)
                holding = _Holding(
                    symbol, qty, day.strftime("%Y-%m-%d"), fill_price,
                    action["rule"], dict(action["inputs"]), item.regime_above_ma200, risk,
                )
                holdings[symbol] = holding
        del pending[symbol]
    return cash, realized_today


def _regime_ok(index_frame: pd.DataFrame, day: pd.Timestamp) -> bool:
    history = (
        index_frame.loc[index_frame.index <= day, "Close"]
        if "Close" in index_frame
        else pd.Series(dtype=float)
    )
    history = history.dropna().astype(float)
    if len(history) < 200:
        return False
    return bool(history.iloc[-1] > history.iloc[-200:].mean())


def _snapshots(
    frames: dict[str, pd.DataFrame], day: pd.Timestamp, regime_ok: bool
) -> dict[str, SymbolSnapshot]:
    result: dict[str, SymbolSnapshot] = {}
    for symbol in sorted(frames):
        frame = frames[symbol]
        if day not in frame.index:
            continue
        history = frame.loc[frame.index <= day]
        if not history.empty and "Close" in history:
            result[symbol] = SymbolSnapshot(
                ohlcv=history,
                latest_price=float(history["Close"].iloc[-1]),
                regime_ok=regime_ok,
                price_source="historical_close",
            )
    return result


def _daily_pnl(
    day: pd.Timestamp, holdings: dict[str, _Holding], frames: dict[str, pd.DataFrame]
) -> float:
    pnl = 0.0
    for symbol, holding in holdings.items():
        history = frames[symbol].loc[frames[symbol].index <= day, "Close"]
        if len(history) >= 2:
            pnl += (float(history.iloc[-1]) - float(history.iloc[-2])) * holding.qty
    return pnl


def _equity(
    day: pd.Timestamp,
    cash: float,
    holdings: dict[str, _Holding],
    frames: dict[str, pd.DataFrame],
) -> float:
    value = cash
    for symbol, holding in holdings.items():
        close = frames[symbol].loc[frames[symbol].index <= day, "Close"]
        if not close.empty:
            value += holding.qty * float(close.iloc[-1])
    return value


def _journal(
    closed: list[_Trade],
    holdings: dict[str, _Holding],
    frames: dict[str, pd.DataFrame],
    days: list[pd.Timestamp],
    capital: float,
) -> list[ReplayJournalTrade]:
    all_trades = list(closed) + [_Trade(item) for _, item in sorted(holdings.items())]
    rows: list[ReplayJournalTrade] = []
    last_day = days[-1] if days else None
    for trade in all_trades:
        holding = trade.holding
        mark = trade.exit_price
        if mark is None and last_day is not None:
            close = frames[holding.symbol].loc[frames[holding.symbol].index <= last_day, "Close"]
            mark = float(close.iloc[-1]) if not close.empty else holding.entry_price
        pnl = holding.qty * ((mark or holding.entry_price) - holding.entry_price)
        r_multiple = None
        if trade.exit_price is not None and holding.risk_per_share > 0:
            r_multiple = (trade.exit_price - holding.entry_price) / holding.risk_per_share
        rows.append(
            ReplayJournalTrade(
                ts=holding.entry_date,
                symbol=holding.symbol,
                qty=holding.qty,
                entry_date=holding.entry_date,
                entry_price=holding.entry_price,
                exit_date=trade.exit_date,
                exit_price=trade.exit_price,
                entry_rule=holding.entry_rule,
                exit_rule=trade.exit_rule,
                r_multiple=r_multiple,
                pnl=pnl if trade.exit_price is not None else None,
                return_contribution=pnl / capital * 100.0,
                regime_above_ma200=holding.regime_above_ma200,
                inputs=holding.entry_inputs,
                exit_inputs=trade.exit_inputs or {},
            )
        )
    return sorted(rows, key=lambda row: (row.entry_date, row.symbol))


def _stats(rule: str, rows: list[ReplayJournalTrade]) -> ReplayRuleStats:
    closed = [row for row in rows if row.exit_date is not None]
    r_values = [row.r_multiple for row in closed if row.r_multiple is not None]
    return ReplayRuleStats(
        rule=rule,
        trade_count=len(rows),
        win_rate=(
            sum((row.pnl or 0.0) > 0 for row in closed) / len(closed) * 100.0
            if closed
            else None
        ),
        avg_r=sum(r_values) / len(r_values) if r_values else None,
        total_return_contribution=sum(row.return_contribution for row in rows),
    )


def _attribution(
    journal: list[ReplayJournalTrade], gate_blocks: int, risk_blocks: int
) -> ReplayAttribution:
    entry_rules = sorted({row.entry_rule for row in journal})
    exit_rules = sorted({row.exit_rule or "open_position" for row in journal})
    entry_stats = [
        _stats(rule, [row for row in journal if row.entry_rule == rule])
        for rule in entry_rules
    ]
    exit_stats = [
        _stats(rule, [row for row in journal if (row.exit_rule or "open_position") == rule])
        for rule in exit_rules
    ]
    regimes: list[ReplayRegimeStats] = []
    for above, label in ((True, "above_ma200"), (False, "below_ma200")):
        rows = [row for row in journal if row.regime_above_ma200 is above]
        stat = _stats(label, rows)
        regimes.append(
            ReplayRegimeStats(
                regime=label,
                entry_count=len(rows),
                trade_count=stat.trade_count,
                win_rate=stat.win_rate,
                avg_r=stat.avg_r,
                total_return_contribution=stat.total_return_contribution,
            )
        )
    return ReplayAttribution(
        entry_rules=entry_stats,
        exit_rules=exit_stats,
        regimes=regimes,
        regime_gate_blocks=gate_blocks,
        risk_limit_blocks=risk_blocks,
    )


def _report(
    start: str,
    end: str,
    config: AutotradeConfig,
    cost_bps: float,
    journal: list[ReplayJournalTrade],
    equity: pd.Series,
    final_equity: float,
    gate_blocks: int,
    risk_blocks: int,
) -> ReplayReport:
    metrics = _metrics(equity)
    closed = sorted(
        (row for row in journal if row.exit_date is not None),
        key=lambda row: (row.exit_date or "", row.symbol),
    )
    losses = 0
    max_losses = 0
    for row in closed:
        losses = losses + 1 if (row.pnl or 0.0) < 0 else 0
        max_losses = max(max_losses, losses)
    return ReplayReport(
        period=ReplayPeriod(start=start, end=end),
        universe=list(config.universe),
        config=config,
        cost_bps=cost_bps,
        journal=journal,
        attribution=_attribution(journal, gate_blocks, risk_blocks),
        equity_curve=[
            LinePoint(time=ts.strftime("%Y-%m-%d"), value=float(value))
            for ts, value in equity.items()
        ],
        summary=ReplaySummary(
            initial_capital=config.capital,
            final_equity=final_equity,
            total_return=(final_equity / config.capital - 1.0) * 100.0,
            cagr=metrics["cagr"],
            mdd=metrics["mdd"],
            sharpe=metrics["sharpe"],
            trade_count=len(journal),
            closed_trade_count=len(closed),
            win_rate=(
                sum((row.pnl or 0.0) > 0 for row in closed) / len(closed) * 100.0
                if closed
                else None
            ),
            max_consecutive_losses=max_losses,
        ),
        caveats=[
            "생존편향: 현재 상장 종목으로 구성한 유니버스를 사용합니다.",
            "체결 가정: 신호 다음 거래일 시가에 체결되며 왕복 비용을 양쪽에 절반씩 적용합니다.",
            "장중 손절 없음: ATR 손절은 일봉 종가로 확인하고 다음 거래일 시가에 체결합니다.",
        ],
    )
