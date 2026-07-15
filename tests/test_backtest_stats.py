"""Regression tests for decision-grade backtest trade statistics."""

from __future__ import annotations

import pandas as pd
import pytest

from backend import portfolio
from backend.schema import BacktestRequest, BacktestResult


def _run_backtest(
    monkeypatch: pytest.MonkeyPatch,
    close_values: list[float],
    position_values: list[float],
    *,
    cost_bps: float = 0.0,
) -> BacktestResult:
    index = pd.date_range("2024-01-02", periods=len(close_values), freq="B")
    close = pd.Series(close_values, index=index, dtype=float)
    frame = pd.DataFrame(
        {
            "Open": close,
            "High": close,
            "Low": close,
            "Close": close,
            "Volume": 1_000,
        },
        index=index,
    )
    position = pd.Series(position_values, index=index, dtype=float)

    def fake_get_ohlcv_df(symbol: str, period: str, interval: str) -> pd.DataFrame:
        return frame.copy()

    def fake_sma(series: pd.Series, window: int) -> pd.Series:
        return position.copy() if window == 1 else pd.Series(0.5, index=series.index)

    monkeypatch.setattr(portfolio, "get_ohlcv_df", fake_get_ohlcv_df)
    monkeypatch.setattr(portfolio, "sma", fake_sma)
    return portfolio.backtest(
        BacktestRequest(
            symbol="TEST",
            strategy="ma_cross",
            fast=1,
            slow=2,
            period="1y",
            cost_bps=cost_bps,
        )
    )


def _two_trade_case(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cost_bps: float = 0.0,
) -> BacktestResult:
    close = [100.0] * 60
    close[6:13] = [110.0] * 7
    close[14:] = [90.0] * 46
    position = [0.0] * 60
    position[4:8] = [1.0] * 4
    position[12:16] = [1.0] * 4
    return _run_backtest(monkeypatch, close, position, cost_bps=cost_bps)


def test_trades_counts_completed_round_trips(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _two_trade_case(monkeypatch)

    assert result.trades == 2


def test_win_rate_uses_profitable_completed_trades(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _two_trade_case(monkeypatch)

    assert [trade.ret_pct > 0 for trade in result.trades_list] == [True, False]
    assert result.win_rate == 50.0


def test_round_trip_cost_is_split_between_entry_and_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close = [100.0] * 60
    position = [0.0] * 60
    position[4:8] = [1.0] * 4

    result = _run_backtest(monkeypatch, close, position, cost_bps=20.0)

    assert result.equity_curve[-1].value == pytest.approx(99.8001)
    assert result.trades_list[0].ret_pct == pytest.approx(-0.1999)


def test_trade_rows_count_matches_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _two_trade_case(monkeypatch)

    assert len(result.trades_list) == result.trades


def test_open_position_is_closed_at_last_bar_for_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close = [100.0] * 60
    position = [0.0] * 4 + [1.0] * 56

    result = _run_backtest(monkeypatch, close, position, cost_bps=20.0)

    assert result.trades == 1
    assert result.trades_list[0].exit_date == result.equity_curve[-1].time
    assert result.equity_curve[-1].value == pytest.approx(99.8001)


def test_trade_returns_reconcile_with_equity_curve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _two_trade_case(monkeypatch, cost_bps=20.0)
    trade_factor = 1.0
    for trade in result.trades_list:
        trade_factor *= 1.0 + trade.ret_pct / 100.0

    assert result.equity_curve[-1].value == pytest.approx(100.0 * trade_factor)
