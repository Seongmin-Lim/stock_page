"""Trade journal derive/stats tests — pure functions, no JSON store touched."""

from __future__ import annotations

import pytest

from backend.journal import _derive, _stats
from backend.schema import TradeEntry


def _closed_long(entry: float, exit_: float, shares: float, stop: float) -> TradeEntry:
    return _derive(
        TradeEntry(
            symbol="X",
            direction="long",
            entry_price=entry,
            exit_price=exit_,
            shares=shares,
            stop_price=stop,
        )
    )


def test_derive_long_pnl_and_r():
    t = _closed_long(100.0, 120.0, 10.0, 90.0)
    assert t.status == "closed"
    assert t.pnl == pytest.approx(200.0)  # (120-100)*10
    assert t.pnl_pct == pytest.approx(20.0)
    assert t.r_multiple == pytest.approx(2.0)  # per_share 20 / risk 10


def test_derive_short_pnl_and_r():
    t = _derive(
        TradeEntry(
            symbol="X",
            direction="short",
            entry_price=100.0,
            exit_price=80.0,
            shares=5.0,
            stop_price=110.0,
        )
    )
    # short win: price fell → profit. per_share = entry-exit = 20
    assert t.pnl == pytest.approx(100.0)
    assert t.pnl_pct == pytest.approx(20.0)
    assert t.r_multiple == pytest.approx(2.0)  # 20 / |100-110|


def test_derive_open_trade_has_no_pnl():
    t = _derive(TradeEntry(symbol="X", entry_price=100.0))
    assert t.status == "open"
    assert t.pnl is None and t.pnl_pct is None and t.r_multiple is None


def test_stats_win_rate_expectancy_profit_factor():
    trades = [
        _closed_long(100.0, 120.0, 10.0, 90.0),  # +200, +2R
        _closed_long(100.0, 110.0, 10.0, 90.0),  # +100, +1R
        _closed_long(100.0, 90.0, 10.0, 90.0),  # -100, -1R
    ]
    s = _stats(trades)
    assert s.closed == 3
    assert s.wins == 2 and s.losses == 1
    assert s.win_rate == pytest.approx(66.7, abs=0.1)
    # gross win 300 / gross loss 100
    assert s.profit_factor == pytest.approx(3.0)
    # expectancy_r: p_win*avg_win_r + p_loss*avg_loss_r = 2/3*1.5 + 1/3*(-1) = 0.67
    assert s.expectancy_r == pytest.approx(0.67, abs=0.01)


def test_stats_empty():
    s = _stats([])
    assert s.total == 0 and s.closed == 0
    assert s.win_rate is None and s.profit_factor is None
