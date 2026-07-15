"""Price / indicator alerts. Rules persist to data/alerts.json and are evaluated on demand
(no realtime feed in the key-free setup — checked when the user opens/refreshes the tab)."""

from __future__ import annotations

import uuid

from backend.indicators import rsi as rsi_series
from backend.indicators import sma
from backend.schema import AlertCheckResult, AlertHit, AlertRule
from backend.sources import get_ohlcv_df
from backend.store import load_json, save_json

_FILE = "alerts.json"


def list_alerts() -> list[AlertRule]:
    return [AlertRule(**a) for a in load_json(_FILE, [])]


def add_alert(rule: AlertRule) -> list[AlertRule]:
    rules = load_json(_FILE, [])
    rule.id = rule.id or uuid.uuid4().hex[:10]
    rules.append(rule.model_dump())
    save_json(_FILE, rules)
    return list_alerts()


def delete_alert(alert_id: str) -> list[AlertRule]:
    rules = [a for a in load_json(_FILE, []) if a.get("id") != alert_id]
    save_json(_FILE, rules)
    return list_alerts()


def _evaluate(rule: AlertRule) -> AlertHit:
    df = get_ohlcv_df(rule.symbol, "1y", "1d")
    if df.empty:
        return AlertHit(
            id=rule.id,
            symbol=rule.symbol,
            name=rule.name,
            message="데이터 없음",
            current=None,
            triggered=False,
        )
    close = df["Close"].dropna()
    last = float(close.iloc[-1])
    cur: float | None = None
    triggered = False
    msg = ""

    if rule.metric == "price":
        cur = last
        triggered = (last > rule.value) if rule.op == "gt" else (last < rule.value)
        msg = f"현재가 {last:,.2f} {'>' if rule.op == 'gt' else '<'} {rule.value:,.2f}"
    elif rule.metric == "rsi":
        cur = float(rsi_series(close).iloc[-1])
        triggered = (cur > rule.value) if rule.op == "gt" else (cur < rule.value)
        msg = f"RSI {cur:.1f} {'>' if rule.op == 'gt' else '<'} {rule.value:.0f}"
    elif rule.metric == "pct_change":
        prev = float(close.iloc[-2]) if len(close) >= 2 else last
        cur = (last / prev - 1) * 100.0 if prev else 0.0
        triggered = (cur > rule.value) if rule.op == "gt" else (cur < rule.value)
        msg = (
            f"전일대비 {cur:+.2f}% {'>' if rule.op == 'gt' else '<'} {rule.value:.1f}%"
        )
    elif rule.metric == "ma_cross":
        fast, slow = sma(close, 20), sma(close, 60)
        if len(close) >= 61:
            now = fast.iloc[-1] - slow.iloc[-1]
            prev = fast.iloc[-2] - slow.iloc[-2]
            cur = float(now)
            if rule.op == "cross_up":
                triggered = prev <= 0 < now
                msg = "MA20이 MA60을 상향 돌파" if triggered else "골든크로스 미발생"
            else:
                triggered = prev >= 0 > now
                msg = "MA20이 MA60을 하향 돌파" if triggered else "데드크로스 미발생"

    return AlertHit(
        id=rule.id,
        symbol=rule.symbol,
        name=rule.name,
        message=msg,
        current=cur,
        triggered=triggered,
    )


def check_alerts() -> AlertCheckResult:
    return AlertCheckResult(hits=[_evaluate(r) for r in list_alerts()])
