from __future__ import annotations

import json

import pandas as pd
import pytest
from pydantic import ValidationError

from backend import replay as replay_mod
from backend.autotrade import SymbolSnapshot, evaluate
from backend.schema import AutotradeConfig, ReplayRequest

SYMBOL = "005930"


def _stock_frame(*, stop: bool = False) -> tuple[pd.DataFrame, pd.Timestamp]:
    closes = [100.0, 99.0] * 10 + [99.0, 99.0, 101.0]
    signal_date = pd.Timestamp("2024-02-01")
    history_dates = pd.bdate_range(end=signal_date, periods=len(closes))
    future_dates = pd.bdate_range(start=signal_date + pd.Timedelta(days=1), periods=3)
    future_closes = [90.0, 90.0, 90.0] if stop else [100.0, 100.0, 100.0]
    all_dates = history_dates.append(future_dates)
    all_closes = pd.Series(closes + future_closes, index=all_dates)
    frame = pd.DataFrame(
        {
            "Open": all_closes,
            "High": all_closes + 1.0,
            "Low": all_closes - 1.0,
            "Close": all_closes,
            "Volume": 1_000.0,
        }
    )
    frame.loc[future_dates[0], "Open"] = 110.0
    return frame, signal_date


def _index_frame(last_date: pd.Timestamp) -> pd.DataFrame:
    dates = pd.bdate_range(end=last_date, periods=240)
    close = pd.Series([100.0 + i * 0.1 for i in range(len(dates))], index=dates)
    return pd.DataFrame(
        {"Open": close, "High": close + 1, "Low": close - 1, "Close": close, "Volume": 1_000}
    )


def _patch_data(
    monkeypatch: pytest.MonkeyPatch, frame: pd.DataFrame
) -> None:
    index = _index_frame(frame.index[-1])

    def fake_bars(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        del period, interval
        return index.copy() if symbol == "KS11" else frame.copy()

    monkeypatch.setattr(replay_mod, "get_ohlcv_df", fake_bars)


def _config(**updates: float | int) -> AutotradeConfig:
    values: dict[str, object] = {
        "universe": [SYMBOL],
        "capital": 1_000_000.0,
        "ma_fast": 2,
        "ma_slow": 3,
        "rsi_entry_max": 70.0,
        "rsi_exit": 80.0,
    }
    values.update(updates)
    return AutotradeConfig(**values)


def _run(monkeypatch: pytest.MonkeyPatch, *, stop: bool = False, cost_bps: float = 15.0):
    frame, signal_date = _stock_frame(stop=stop)
    _patch_data(monkeypatch, frame)
    report = replay_mod.replay(
        [SYMBOL],
        signal_date.strftime("%Y-%m-%d"),
        frame.index[-1].strftime("%Y-%m-%d"),
        _config(atr_mult=0.5 if stop else 2.0),
        cost_bps,
    )
    return report, frame, signal_date


def test_no_lookahead_future_bar_cannot_cancel_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report, frame, signal_date = _run(monkeypatch, stop=True, cost_bps=0.0)
    config = _config(atr_mult=0.5)
    leaked = evaluate(
        {SYMBOL: SymbolSnapshot(frame, float(frame["Close"].iloc[-1]), True)},
        [],
        config,
    )

    assert not any(action["rule"] == "ma_cross_up" for action in leaked)
    assert report.journal[0].entry_date > signal_date.strftime("%Y-%m-%d")
    assert report.journal[0].entry_rule == "ma_cross_up"


def test_entry_fills_at_next_open_with_side_cost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report, frame, signal_date = _run(monkeypatch)
    next_date = frame.index[frame.index.get_loc(signal_date) + 1]

    assert report.journal[0].entry_date == next_date.strftime("%Y-%m-%d")
    assert report.journal[0].entry_price == pytest.approx(110.0 * 1.00075)


def test_entry_rule_contributions_reconcile_final_equity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report, _, _ = _run(monkeypatch)
    contribution = sum(
        row.total_return_contribution for row in report.attribution.entry_rules
    )

    assert contribution == pytest.approx(report.summary.total_return)
    assert report.summary.final_equity == pytest.approx(
        report.summary.initial_capital * (1.0 + contribution / 100.0)
    )


def test_stop_loss_has_rule_and_minus_one_r(monkeypatch: pytest.MonkeyPatch) -> None:
    frame, signal_date = _stock_frame(stop=True)
    risk = 2.0714285714285716 * 0.5
    exit_date = frame.index[frame.index.get_loc(signal_date) + 2]
    frame.loc[exit_date, "Open"] = 110.0 - risk
    _patch_data(monkeypatch, frame)

    report = replay_mod.replay(
        [SYMBOL],
        signal_date.strftime("%Y-%m-%d"),
        frame.index[-1].strftime("%Y-%m-%d"),
        _config(atr_mult=0.5),
        0.0,
    )

    assert report.journal[0].exit_rule == "stop_loss"
    assert report.journal[0].r_multiple == pytest.approx(-1.0, abs=0.02)


def test_replay_is_byte_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    first, _, _ = _run(monkeypatch)
    second, _, _ = _run(monkeypatch)

    assert first.model_dump_json() == second.model_dump_json()
    assert json.dumps(first.model_dump(), ensure_ascii=False) == json.dumps(
        second.model_dump(), ensure_ascii=False
    )


def test_replay_request_validation() -> None:
    with pytest.raises(ValidationError):
        ReplayRequest(
            universe=[f"{number:06d}" for number in range(21)],
            start="2024-01-01",
            end="2024-12-31",
        )
    with pytest.raises(ValidationError):
        ReplayRequest(universe=[SYMBOL], start="2024-01-01", end="2024-01-01")
