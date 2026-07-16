"""Deterministic paper-trading strategy and KIS mock-account runner."""

from __future__ import annotations

import asyncio
import contextlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, time
from typing import Literal, TypedDict
from zoneinfo import ZoneInfo

import pandas as pd

from backend import config as app_config
from backend import kis, kis_trade, regime
from backend.cache import DATA_DIR
from backend.indicators import atr, rsi, sma
from backend.schema import AutotradeConfig, AutotradeConfigUpdate, PositionRequest
from backend.sources import get_ohlcv_df
from backend.store import load_json, save_json
from backend.trade import size_position

_CONFIG_FILE = "autotrade_config.json"
_STATE_FILE = "autotrade_state.json"
_LOG_FILE = "autotrade_log.jsonl"
_SEOUL = ZoneInfo("Asia/Seoul")
_MOCK_ONLY_MESSAGE = "자동매매는 모의투자(KIS_MOCK=true)에서만 동작합니다."

InputValue = float | int | bool | str


class Action(TypedDict):
    symbol: str
    side: Literal["buy", "sell"]
    qty: int
    reason: str
    rule: str
    inputs: dict[str, InputValue]


@dataclass(frozen=True)
class SymbolSnapshot:
    ohlcv: pd.DataFrame
    latest_price: float
    regime_ok: bool
    price_source: str = "unknown"


@dataclass(frozen=True)
class OpenPosition:
    symbol: str
    qty: int
    entry_price: float
    current_price: float = 0.0
    pnl: float = 0.0


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def evaluate(
    snapshot: dict[str, SymbolSnapshot],
    positions: list[OpenPosition],
    config: AutotradeConfig,
) -> list[Action]:
    """Return deterministic actions without clock, network, or filesystem access."""
    actions: list[Action] = []
    position_by_symbol = {position.symbol: position for position in positions}

    for symbol in sorted(snapshot):
        item = snapshot[symbol]
        frame = item.ohlcv
        required = {"High", "Low", "Close"}
        if not required.issubset(frame.columns) or len(frame) < config.ma_slow + 1:
            continue

        close = frame["Close"].astype(float)
        fast = sma(close, config.ma_fast)
        slow = sma(close, config.ma_slow)
        rsi_series = rsi(close, 14)
        atr_series = atr(frame, 14)
        values = {
            "ma_fast_prev": _finite(fast.iloc[-2]),
            "ma_slow_prev": _finite(slow.iloc[-2]),
            "ma_fast": _finite(fast.iloc[-1]),
            "ma_slow": _finite(slow.iloc[-1]),
            "rsi": _finite(rsi_series.iloc[-1]),
            "atr": _finite(atr_series.iloc[-1]),
        }
        if any(value is None for value in values.values()):
            continue
        ma_fast_prev = float(values["ma_fast_prev"])
        ma_slow_prev = float(values["ma_slow_prev"])
        ma_fast = float(values["ma_fast"])
        ma_slow = float(values["ma_slow"])
        rsi_value = float(values["rsi"])
        atr_value = float(values["atr"])
        cross_up = ma_fast_prev <= ma_slow_prev and ma_fast > ma_slow
        cross_down = ma_fast_prev >= ma_slow_prev and ma_fast < ma_slow
        indicator_inputs: dict[str, InputValue] = {
            "ma_fast_prev": ma_fast_prev,
            "ma_slow_prev": ma_slow_prev,
            "ma_fast": ma_fast,
            "ma_slow": ma_slow,
            "rsi14": rsi_value,
            "atr14": atr_value,
            "latest_price": item.latest_price,
        }

        position = position_by_symbol.get(symbol)
        if position is not None:
            stop_price = position.entry_price - config.atr_mult * atr_value
            exit_inputs = dict(indicator_inputs)
            exit_inputs.update(
                {"entry_price": position.entry_price, "stop_price": stop_price}
            )
            if item.latest_price <= stop_price:
                actions.append(
                    _action(symbol, "sell", position.qty, "ATR 손절가 도달", "stop_loss", exit_inputs)
                )
            elif cross_down:
                actions.append(
                    _action(symbol, "sell", position.qty, "단기 이동평균 하향 돌파", "ma_cross_down", exit_inputs)
                )
            elif rsi_value > config.rsi_exit:
                actions.append(
                    _action(symbol, "sell", position.qty, "RSI 과열 청산", "rsi_exit", exit_inputs)
                )
            continue

        if not cross_up or rsi_value >= config.rsi_entry_max:
            continue
        if not item.regime_ok:
            gate_inputs = dict(indicator_inputs)
            gate_inputs["regime_ok"] = False
            actions.append(
                _action(symbol, "buy", 0, "시장 국면 진입 차단", "regime_gate_flat", gate_inputs)
            )
            continue
        if atr_value <= 0 or item.latest_price <= 0:
            continue
        stop_price = item.latest_price - config.atr_mult * atr_value
        sizing = size_position(
            PositionRequest(
                account=config.capital,
                risk_pct=config.risk_pct,
                entry=item.latest_price,
                stop_mode="price",
                stop_price=stop_price,
                direction="long",
            )
        )
        buy_inputs = dict(indicator_inputs)
        buy_inputs.update(
            {
                "regime_ok": True,
                "stop_price": stop_price,
                "risk_pct": config.risk_pct,
                "capital": config.capital,
            }
        )
        actions.append(
            _action(symbol, "buy", sizing.shares, "단기 이동평균 상향 돌파", "ma_cross_up", buy_inputs)
        )
    return actions


def _action(
    symbol: str,
    side: Literal["buy", "sell"],
    qty: int,
    reason: str,
    rule: str,
    inputs: dict[str, InputValue],
) -> Action:
    return {
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "reason": reason,
        "rule": rule,
        "inputs": inputs,
    }


def enforce_risk_limits(
    actions: list[Action],
    positions: list[OpenPosition],
    config: AutotradeConfig,
    today_pnl: float,
) -> tuple[list[Action], list[Action], bool]:
    """Filter entries while always preserving strategy-driven exits."""
    loss_limit = config.capital * config.daily_loss_limit_pct / 100.0
    halted = today_pnl <= -loss_limit
    open_symbols = {position.symbol for position in positions}
    position_count = len(open_symbols)
    accepted: list[Action] = []
    refused: list[Action] = []
    for action in actions:
        if action["side"] == "sell":
            accepted.append(action)
        elif action["qty"] <= 0:
            refused.append(action)
        elif halted:
            refused.append(_refusal(action, "risk_halt", "일일 손실 한도 도달"))
        elif action["symbol"] in open_symbols:
            refused.append(_refusal(action, "position_exists", "종목별 보유 한도 도달"))
        elif position_count >= config.max_positions:
            refused.append(_refusal(action, "max_positions", "최대 보유 종목 수 도달"))
        else:
            accepted.append(action)
            open_symbols.add(action["symbol"])
            position_count += 1
    return accepted, refused, halted


def _refusal(action: Action, rule: str, reason: str) -> Action:
    return _action(
        action["symbol"], action["side"], action["qty"], reason, rule, dict(action["inputs"])
    )


def load_config() -> AutotradeConfig:
    raw = load_json(_CONFIG_FILE, {})
    try:
        return AutotradeConfig(**raw)
    except (TypeError, ValueError):
        return AutotradeConfig()


def update_config(update: AutotradeConfigUpdate) -> AutotradeConfig:
    current = load_config()
    merged = current.model_dump()
    merged.update(update.model_dump(exclude_none=True))
    validated = AutotradeConfig(**merged)
    save_json(_CONFIG_FILE, validated.model_dump())
    return validated


def _default_state() -> dict[str, object]:
    return {
        "enabled": False,
        "positions": [],
        "today_pnl": 0.0,
        "realized_today": 0.0,
        "pnl_date": "",
        "last_run": None,
        "halt": False,
        "message": "자동매매가 중지되어 있습니다.",
    }


def load_state() -> dict[str, object]:
    state = _default_state()
    raw = load_json(_STATE_FILE, {})
    if isinstance(raw, dict):
        state.update(raw)
    return state


def _save_state(state: dict[str, object]) -> None:
    save_json(_STATE_FILE, state)


def _append_log(
    action: Action,
    order_result: dict[str, object],
    price_source: str,
    now: datetime,
) -> None:
    row: dict[str, object] = {
        "ts": now.isoformat(),
        **action,
        "order_result": order_result,
        "price_source": price_source,
    }
    path = DATA_DIR / _LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def _log_event(rule: str, reason: str, now: datetime) -> None:
    _append_log(
        _action("", "buy", 0, reason, rule, {}),
        {"ok": False, "message": reason},
        "none",
        now,
    )


def recent_logs(limit: int = 20) -> list[dict[str, object]]:
    path = DATA_DIR / _LOG_FILE
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def status() -> dict[str, object]:
    return {"state": load_state(), "config": load_config().model_dump(), "logs": recent_logs()}


def _positions_from_account(account: dict[str, object]) -> list[OpenPosition]:
    raw_positions = account.get("positions")
    if not isinstance(raw_positions, list):
        return []
    positions: list[OpenPosition] = []
    for raw in raw_positions:
        if not isinstance(raw, dict):
            continue
        symbol = raw.get("symbol")
        qty = _finite(raw.get("qty"))
        entry = _finite(raw.get("avg_price"))
        if not isinstance(symbol, str) or qty is None or entry is None or qty <= 0:
            continue
        positions.append(
            OpenPosition(
                symbol=symbol,
                qty=int(qty),
                entry_price=entry,
                current_price=_finite(raw.get("current_price")) or 0.0,
                pnl=_finite(raw.get("pnl")) or 0.0,
            )
        )
    return positions


def _kr_regime_ok() -> bool:
    for item in regime.regime().items:
        if item.market == "KR":
            return item.above_ma200 is True
    return False


def _build_snapshot(
    strategy_config: AutotradeConfig, now: datetime
) -> dict[str, SymbolSnapshot]:
    regime_ok = _kr_regime_ok()
    snapshots: dict[str, SymbolSnapshot] = {}
    for symbol in strategy_config.universe:
        try:
            frame = get_ohlcv_df(symbol, "1y", "1d")
            if frame.empty or "Close" not in frame.columns:
                _log_event("data_error", f"{symbol} 일봉 데이터가 없습니다.", now)
                continue
            quote = kis.quote(symbol)
            quote_price = _finite(quote.get("price")) if quote is not None else None
            if quote_price is not None and quote_price > 0:
                price = quote_price
                source = "kis_quote"
            else:
                price = float(frame["Close"].iloc[-1])
                source = "fdr_close"
            snapshots[symbol] = SymbolSnapshot(frame, price, regime_ok, source)
        except Exception as exc:  # noqa: BLE001 - one symbol must not stop the loop
            _log_event("data_error", f"{symbol} 데이터 조회 실패: {exc}", now)
    return snapshots


def _market_phase(now: datetime) -> Literal["closed", "entry", "exit_only"]:
    local = now.astimezone(_SEOUL)
    if local.weekday() >= 5 or local.time() < time(9, 0) or local.time() > time(15, 20):
        return "closed"
    return "entry" if local.time() <= time(15, 0) else "exit_only"


def run_once(now: datetime | None = None) -> dict[str, object]:
    """Run one synchronous broker cycle; intended for ``asyncio.to_thread``."""
    current = (now or datetime.now(_SEOUL)).astimezone(_SEOUL)
    strategy_config = load_config()
    state = load_state()
    if not strategy_config.universe:
        _log_event("universe_empty", "자동매매 종목 목록이 비어 있습니다.", current)
        state.update({"last_run": current.isoformat(), "message": "종목 목록이 비어 대기 중입니다."})
        _save_state(state)
        return state

    account = kis_trade.account()
    if account.get("message") != "KIS 잔고를 조회했습니다.":
        message_value = account.get("message")
        message = (
            message_value if isinstance(message_value, str) else "KIS 잔고 조회에 실패했습니다."
        )
        _log_event("account_error", message, current)
        state.update({"last_run": current.isoformat(), "message": message})
        _save_state(state)
        return state
    positions = _positions_from_account(account)
    date_text = current.date().isoformat()
    if state.get("pnl_date") != date_text:
        state["pnl_date"] = date_text
        state["realized_today"] = 0.0
    snapshots = _build_snapshot(strategy_config, current)
    realized = _finite(state.get("realized_today")) or 0.0
    unrealized_today = 0.0
    for position in positions:
        item = snapshots.get(position.symbol)
        if item is not None and len(item.ohlcv) >= 2:
            previous_close = float(item.ohlcv["Close"].iloc[-2])
            unrealized_today += (item.latest_price - previous_close) * position.qty
    today_pnl = realized + unrealized_today
    actions = evaluate(snapshots, positions, strategy_config)
    accepted, refused, halted = enforce_risk_limits(
        actions, positions, strategy_config, today_pnl
    )
    if halted:
        _log_event("risk_halt", "일일 손실 한도 도달", current)
    if _market_phase(current) == "exit_only":
        late_entries = [action for action in accepted if action["side"] == "buy"]
        accepted = [action for action in accepted if action["side"] == "sell"]
        refused.extend(_refusal(action, "entry_cutoff", "15시 이후 신규 진입 차단") for action in late_entries)
    for action in refused:
        source = snapshots.get(action["symbol"])
        _append_log(
            action,
            {"ok": False, "message": action["reason"]},
            source.price_source if source is not None else "none",
            current,
        )
    for action in accepted:
        source = snapshots.get(action["symbol"])
        result = kis_trade.order_cash(
            action["symbol"], action["qty"], None, "market", action["side"]
        )
        _append_log(
            action,
            result,
            source.price_source if source is not None else "none",
            current,
        )
        if result.get("ok") is True and action["side"] == "sell":
            position = next((item for item in positions if item.symbol == action["symbol"]), None)
            if position is not None and source is not None and len(source.ohlcv) >= 2:
                previous_close = float(source.ohlcv["Close"].iloc[-2])
                realized += (source.latest_price - previous_close) * action["qty"]
    state.update(
        {
            "positions": [position.__dict__ for position in positions],
            "today_pnl": today_pnl,
            "realized_today": realized,
            "last_run": current.isoformat(),
            "halt": halted,
            "message": "일일 손실 한도로 신규 진입이 중단되었습니다." if halted else "자동매매 실행 완료",
        }
    )
    _save_state(state)
    return state


_task: asyncio.Task[None] | None = None


async def _runner_loop() -> None:
    while True:
        strategy_config = load_config()
        now = datetime.now(_SEOUL)
        if _market_phase(now) != "closed":
            await asyncio.to_thread(run_once, now)
        await asyncio.sleep(strategy_config.interval_sec)


async def start() -> dict[str, object]:
    """Start the runner only in KIS mock mode."""
    global _task
    if not app_config.KIS_MOCK:
        state = load_state()
        state.update({"enabled": False, "message": _MOCK_ONLY_MESSAGE})
        _save_state(state)
        _log_event("mock_only", _MOCK_ONLY_MESSAGE, datetime.now(_SEOUL))
        return {"ok": False, "message": _MOCK_ONLY_MESSAGE, "state": state}
    if _task is None or _task.done():
        _task = asyncio.create_task(_runner_loop(), name="autotrade-runner")
    state = load_state()
    state.update({"enabled": True, "message": "자동매매를 시작했습니다."})
    _save_state(state)
    return {"ok": True, "message": "자동매매를 시작했습니다.", "state": state}


async def stop() -> dict[str, object]:
    global _task
    if _task is not None and not _task.done():
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _task
    _task = None
    state = load_state()
    state.update({"enabled": False, "message": "자동매매를 중지했습니다."})
    _save_state(state)
    return {"ok": True, "message": "자동매매를 중지했습니다.", "state": state}


async def start_on_startup() -> None:
    state = load_state()
    if state.get("enabled") is True and app_config.KIS_MOCK:
        await start()
    elif state.get("enabled") is True:
        state.update({"enabled": False, "message": _MOCK_ONLY_MESSAGE})
        _save_state(state)
