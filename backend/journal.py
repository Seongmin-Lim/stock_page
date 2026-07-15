"""Trade journal — record trades, auto-compute P&L / R-multiple, and aggregate stats.

Persists to data/journal.json (git-ignored). The R-multiple uses the recorded stop:
R = realized P&L per share / initial risk per share — the trader's true scorecard.
"""

from __future__ import annotations

import uuid

from backend.schema import JournalResult, JournalStats, TradeEntry
from backend.store import load_json, save_json

_FILE = "journal.json"


def _derive(t: TradeEntry) -> TradeEntry:
    """Fill status / pnl / pnl_pct / r_multiple from the raw fields."""
    long = t.direction != "short"
    if t.exit_price is not None and t.entry_price:
        per_share = (
            (t.exit_price - t.entry_price) if long else (t.entry_price - t.exit_price)
        )
        t.status = "closed"
        t.pnl = round(per_share * t.shares, 2) if t.shares else round(per_share, 2)
        t.pnl_pct = round(per_share / t.entry_price * 100.0, 2)
        if t.stop_price is not None:
            risk = abs(t.entry_price - t.stop_price)
            t.r_multiple = round(per_share / risk, 2) if risk > 0 else None
    else:
        t.status = "open"
        t.pnl = t.pnl_pct = t.r_multiple = None
    return t


def list_trades() -> list[TradeEntry]:
    return [_derive(TradeEntry(**t)) for t in load_json(_FILE, [])]


def add_trade(entry: TradeEntry) -> JournalResult:
    raw = load_json(_FILE, [])
    entry.id = entry.id or uuid.uuid4().hex[:10]
    raw.append(entry.model_dump())
    save_json(_FILE, raw)
    return result()


def delete_trade(trade_id: str) -> JournalResult:
    raw = [t for t in load_json(_FILE, []) if t.get("id") != trade_id]
    save_json(_FILE, raw)
    return result()


def _stats(trades: list[TradeEntry]) -> JournalStats:
    closed = [t for t in trades if t.status == "closed"]
    wins = [t for t in closed if (t.pnl or 0) > 0]
    losses = [t for t in closed if (t.pnl or 0) < 0]
    rs = [t.r_multiple for t in closed if t.r_multiple is not None]
    win_pnls = [t.pnl for t in wins if t.pnl is not None]
    loss_pnls = [t.pnl for t in losses if t.pnl is not None]

    win_rate = (len(wins) / len(closed) * 100.0) if closed else None
    avg_r = (sum(rs) / len(rs)) if rs else None
    gross_win = sum(win_pnls) if win_pnls else 0.0
    gross_loss = abs(sum(loss_pnls)) if loss_pnls else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else None
    # expectancy in R: winrate*avgWinR + lossrate*avgLossR
    expectancy_r = None
    if closed and rs:
        win_rs = [r for r in rs if r > 0]
        loss_rs = [r for r in rs if r <= 0]
        p_win = len(win_rs) / len(rs)
        avg_win_r = (sum(win_rs) / len(win_rs)) if win_rs else 0.0
        avg_loss_r = (sum(loss_rs) / len(loss_rs)) if loss_rs else 0.0
        expectancy_r = round(p_win * avg_win_r + (1 - p_win) * avg_loss_r, 2)

    return JournalStats(
        total=len(trades),
        closed=len(closed),
        wins=len(wins),
        losses=len(losses),
        win_rate=round(win_rate, 1) if win_rate is not None else None,
        avg_r=round(avg_r, 2) if avg_r is not None else None,
        expectancy_r=expectancy_r,
        total_pnl=round(sum(t.pnl for t in closed if t.pnl is not None), 2),
        avg_win=round(sum(win_pnls) / len(win_pnls), 2) if win_pnls else None,
        avg_loss=round(sum(loss_pnls) / len(loss_pnls), 2) if loss_pnls else None,
        profit_factor=round(profit_factor, 2) if profit_factor is not None else None,
    )


def result() -> JournalResult:
    trades = list_trades()
    trades.sort(key=lambda t: (t.entry_date or "", t.id), reverse=True)
    return JournalResult(trades=trades, stats=_stats(trades))
