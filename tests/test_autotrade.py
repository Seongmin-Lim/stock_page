from __future__ import annotations

import asyncio

import pandas as pd
import pytest

from backend import autotrade
from backend.indicators import atr
from backend.schema import AutotradeConfig, PositionRequest
from backend.trade import size_position

_CROSS_UP = [
    100, 102, 104, 103, 106, 108, 107, 104, 105, 107, 108, 106, 108, 107,
    109, 110, 109, 110, 108, 106, 103, 101, 104, 103, 105, 108, 109, 111,
    108, 106, 108, 105, 102, 101, 99, 102, 100, 97, 96, 98, 101, 102, 101,
    98, 97, 95, 97, 100, 98, 99, 96, 94, 93, 95, 96, 93, 96, 98, 101,
    98, 99, 97, 99, 102, 99, 101, 104, 101, 102, 99, 102, 103, 100, 97,
    99, 102, 100, 99, 102, 103,
]


def _frame(close: list[float]) -> pd.DataFrame:
    values = [float(value) for value in close]
    return pd.DataFrame(
        {
            "Open": values,
            "High": [value + 1.0 for value in values],
            "Low": [value - 1.0 for value in values],
            "Close": values,
            "Volume": [1_000.0] * len(values),
        },
        index=pd.date_range("2025-01-01", periods=len(values), freq="D"),
    )


def _snapshot(*, regime_ok: bool = True, price: float = 103.0) -> dict[str, autotrade.SymbolSnapshot]:
    return {
        "005930": autotrade.SymbolSnapshot(
            ohlcv=_frame([float(value) for value in _CROSS_UP]),
            latest_price=price,
            regime_ok=regime_ok,
            price_source="test",
        )
    }


def test_golden_cross_buys_with_existing_r_sizing() -> None:
    strategy = AutotradeConfig(universe=["005930"])
    snapshot = _snapshot()

    actions = autotrade.evaluate(snapshot, [], strategy)

    atr_value = float(atr(snapshot["005930"].ohlcv, 14).iloc[-1])
    expected = size_position(
        PositionRequest(
            account=strategy.capital,
            risk_pct=strategy.risk_pct,
            entry=103.0,
            stop_mode="price",
            stop_price=103.0 - strategy.atr_mult * atr_value,
        )
    )
    assert len(actions) == 1
    assert actions[0]["side"] == "buy"
    assert actions[0]["rule"] == "ma_cross_up"
    assert actions[0]["qty"] == expected.shares


def test_regime_gate_returns_tagged_non_ordering_decision() -> None:
    actions = autotrade.evaluate(
        _snapshot(regime_ok=False), [], AutotradeConfig(universe=["005930"])
    )

    assert len(actions) == 1
    assert actions[0]["qty"] == 0
    assert actions[0]["rule"] == "regime_gate_flat"


def test_open_position_cross_down_sells() -> None:
    frame = _frame([200.0 - value for value in _CROSS_UP])
    snapshot = {
        "005930": autotrade.SymbolSnapshot(frame, 97.0, True, "test")
    }
    position = autotrade.OpenPosition("005930", 7, 90.0)

    actions = autotrade.evaluate(
        snapshot, [position], AutotradeConfig(universe=["005930"])
    )

    assert len(actions) == 1
    assert actions[0]["side"] == "sell"
    assert actions[0]["qty"] == 7
    assert actions[0]["rule"] == "ma_cross_down"


def test_open_position_stop_loss_has_priority() -> None:
    position = autotrade.OpenPosition("005930", 4, 110.0)

    actions = autotrade.evaluate(
        _snapshot(price=90.0), [position], AutotradeConfig(universe=["005930"])
    )

    assert len(actions) == 1
    assert actions[0]["side"] == "sell"
    assert actions[0]["rule"] == "stop_loss"


def test_risk_limits_block_max_positions_and_daily_loss() -> None:
    strategy = AutotradeConfig(max_positions=1, capital=10_000_000.0)
    buy = autotrade.evaluate(_snapshot(), [], strategy)[0]
    existing = [autotrade.OpenPosition("000660", 1, 100.0)]

    accepted, refused, halted = autotrade.enforce_risk_limits(
        [buy], existing, strategy, today_pnl=0.0
    )
    assert accepted == []
    assert refused[0]["rule"] == "max_positions"
    assert halted is False

    accepted, refused, halted = autotrade.enforce_risk_limits(
        [buy], [], strategy, today_pnl=-300_000.0
    )
    assert accepted == []
    assert refused[0]["rule"] == "risk_halt"
    assert halted is True


def test_start_refuses_real_mode_without_creating_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: dict[str, object] = {"enabled": True}
    monkeypatch.setattr(autotrade.app_config, "KIS_MOCK", False)
    monkeypatch.setattr(autotrade, "_task", None)
    monkeypatch.setattr(autotrade, "load_state", lambda: dict(state))
    monkeypatch.setattr(autotrade, "_save_state", lambda value: None)
    monkeypatch.setattr(autotrade, "_log_event", lambda rule, reason, now: None)

    result = asyncio.run(autotrade.start())

    assert result["ok"] is False
    assert result["message"] == "자동매매는 모의투자(KIS_MOCK=true)에서만 동작합니다."
    assert autotrade._task is None


def test_evaluate_is_deterministic_for_fixed_inputs() -> None:
    snapshot = _snapshot()
    strategy = AutotradeConfig(universe=["005930"])

    first = autotrade.evaluate(snapshot, [], strategy)
    second = autotrade.evaluate(snapshot, [], strategy)

    assert first == second
